import json
import threading

import httpx
import pytest
from insights_support import FakeChatClient, llm_settings
from pydantic import BaseModel

from app.db import SessionLocal
from app.insights.llm import (
    LlmError,
    OpenRouterClient,
    TransportError,
    generate_json,
    usage_today,
)


class Reply(BaseModel):
    answer: str


VALID = json.dumps({"answer": "ok"})


settings = llm_settings


MESSAGES = [{"role": "user", "content": "hi"}]


def test_not_configured_raises_without_key(db):
    client = FakeChatClient([VALID])
    with pytest.raises(LlmError) as error:
        generate_json(db, client, settings(openrouter_api_key=None), MESSAGES, Reply)
    assert error.value.code == "not_configured"
    assert client.calls == []


def test_valid_json_returns_model_and_counts_one_request(db):
    result, model = generate_json(db, FakeChatClient([VALID]), settings(), MESSAGES, Reply)
    assert result.answer == "ok" and model == "primary:free"
    assert usage_today(db, settings()).used == 1


def test_fenced_json_is_accepted(db):
    client = FakeChatClient([f"```json\n{VALID}\n```"])
    assert generate_json(db, client, settings(), MESSAGES, Reply)[0].answer == "ok"


def test_invalid_json_retries_once_with_error_message(db):
    client = FakeChatClient(["not json", VALID])
    result, model = generate_json(db, client, settings(), MESSAGES, Reply)
    assert result.answer == "ok" and model == "primary:free"
    assert "not valid JSON" in client.calls[1][1][-1]["content"]
    assert usage_today(db, settings()).used == 2


def test_null_content_falls_back(db):
    client = FakeChatClient([None, None, VALID])
    _, model = generate_json(db, client, settings(), MESSAGES, Reply)
    assert model == "fallback:free"
    assert [call[0] for call in client.calls] == ["primary:free", "primary:free", "fallback:free"]


def test_transport_error_falls_back_then_unavailable(db):
    client = FakeChatClient([TransportError(500), TransportError(502)])
    with pytest.raises(LlmError) as error:
        generate_json(db, client, settings(), MESSAGES, Reply)
    assert error.value.code == "unavailable"


def test_always_invalid_raises_invalid_output(db):
    client = FakeChatClient(["x", "y", "z", "w"])
    with pytest.raises(LlmError) as error:
        generate_json(db, client, settings(), MESSAGES, Reply)
    assert error.value.code == "invalid_output"


DAILY_CAP = TransportError(429, "Rate limit exceeded: free-models-per-day. Add credits.")


def test_daily_cap_429_marks_quota_exhausted(db):
    client = FakeChatClient([DAILY_CAP])
    with pytest.raises(LlmError) as error:
        generate_json(db, client, settings(), MESSAGES, Reply)
    assert error.value.code == "quota_exhausted"
    assert usage_today(db, settings()).exhausted is True
    later = FakeChatClient([VALID])
    with pytest.raises(LlmError):
        generate_json(db, later, settings(), MESSAGES, Reply)
    assert later.calls == []


def test_upstream_429_falls_back_without_blocking_the_day(db):
    busy = TransportError(429, "google/x:free is temporarily rate-limited upstream.")
    client = FakeChatClient([busy, VALID])
    _, model = generate_json(db, client, settings(), MESSAGES, Reply)
    assert model == "fallback:free"
    assert usage_today(db, settings()).exhausted is False


def test_budget_exhausted_refuses_without_calling(db):
    generate_json(
        db, FakeChatClient([VALID]), settings(llm_daily_request_budget=1), MESSAGES, Reply
    )
    client = FakeChatClient([VALID])
    with pytest.raises(LlmError) as error:
        generate_json(db, client, settings(llm_daily_request_budget=1), MESSAGES, Reply)
    assert error.value.code == "quota_exhausted"
    assert client.calls == []
    info = usage_today(db, settings(llm_daily_request_budget=1))
    assert (info.used, info.remaining) == (1, 0)


def test_budget_reserved_atomically(db):
    barrier = threading.Barrier(2)
    outcomes = []

    class SlowClient(FakeChatClient):
        def complete(self, model, messages, max_tokens):
            barrier.wait(timeout=5)
            return VALID

    def run():
        with SessionLocal() as session:
            try:
                generate_json(
                    session,
                    SlowClient([]),
                    settings(llm_daily_request_budget=1),
                    MESSAGES,
                    Reply,
                )
                outcomes.append("ok")
            except LlmError as error:
                outcomes.append(error.code)
            except threading.BrokenBarrierError:
                outcomes.append("ok")

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert sorted(outcomes) == ["ok", "quota_exhausted"]


def test_openrouter_client_sends_key_and_reads_content():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        if seen["body"]["model"] == "broken":
            return httpx.Response(500, json={"error": "boom"})
        if seen["body"]["model"] == "capped":
            return httpx.Response(
                429, json={"error": {"message": "Rate limit exceeded: free-models-per-day"}}
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": VALID}}]})

    client = OpenRouterClient(settings(), transport=httpx.MockTransport(handler))
    assert client.complete("primary:free", MESSAGES, 100) == VALID
    assert seen["auth"] == "Bearer sk-test-key"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["max_tokens"] == 100
    assert seen["body"]["reasoning"] == {"effort": "low"}
    with pytest.raises(TransportError) as error:
        client.complete("broken", MESSAGES, 100)
    assert error.value.status == 500
    assert "sk-test-key" not in str(error.value)
    with pytest.raises(TransportError) as capped:
        client.complete("capped", MESSAGES, 100)
    assert "free-models-per-day" in capped.value.detail
