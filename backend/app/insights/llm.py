"""OpenAI-compatible chat client with model fallback, JSON validation and a daily budget."""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import LlmUsage

logger = logging.getLogger(__name__)

ErrorCode = Literal["not_configured", "quota_exhausted", "unavailable", "invalid_output"]
SAFE_MESSAGES: dict[str, str] = {
    "not_configured": "AI is not configured on the server.",
    "quota_exhausted": "Today's AI request limit is used up. It resets at midnight UTC.",
    "unavailable": "The AI could not answer right now. Try again later.",
    "invalid_output": "The AI could not answer right now. Try again later.",
}


class LlmError(Exception):
    def __init__(self, code: ErrorCode):
        super().__init__(SAFE_MESSAGES[code])
        self.code = code
        self.message = SAFE_MESSAGES[code]


class TransportError(Exception):
    def __init__(self, status: int | None):
        super().__init__(f"LLM request failed (status {status})")
        self.status = status


class ChatClient(Protocol):
    def complete(self, model: str, messages: list[dict], max_tokens: int) -> str | None: ...


class OpenRouterClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        key = settings.openrouter_api_key
        self._client = httpx.Client(
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
            transport=transport,
            headers={
                "Authorization": f"Bearer {key.get_secret_value() if key else ''}",
                "X-Title": "SEOPs",
            },
        )

    def complete(self, model: str, messages: list[dict], max_tokens: int) -> str | None:
        try:
            response = self._client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
            )
        except httpx.HTTPError:
            raise TransportError(None) from None
        if response.status_code >= 400:
            raise TransportError(response.status_code)
        try:
            return response.json()["choices"][0]["message"].get("content")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise TransportError(response.status_code) from None


class UsageInfo(BaseModel):
    configured: bool
    model: str
    used: int
    budget: int
    remaining: int
    exhausted: bool


def _today():
    return datetime.now(UTC).date()


def usage_today(db: Session, settings: Settings) -> UsageInfo:
    row = db.execute(select(LlmUsage).where(LlmUsage.day == _today())).scalar_one_or_none()
    used = row.requests if row else 0
    exhausted = bool(row and row.quota_exhausted) or used >= settings.llm_daily_request_budget
    return UsageInfo(
        configured=settings.openrouter_api_key is not None,
        model=settings.llm_model,
        used=used,
        budget=settings.llm_daily_request_budget,
        remaining=0 if exhausted else settings.llm_daily_request_budget - used,
        exhausted=exhausted,
    )


def _reserve(db: Session, budget: int) -> None:
    """Count one request in its own committed transaction, or refuse atomically."""
    if budget < 1:
        raise LlmError("quota_exhausted")
    statement = (
        insert(LlmUsage)
        .values(day=_today(), requests=1)
        .on_conflict_do_update(
            index_elements=[LlmUsage.day],
            set_={"requests": LlmUsage.requests + 1},
            where=text("NOT llm_usage.quota_exhausted AND llm_usage.requests < :budget"),
        )
        .returning(LlmUsage.requests)
    )
    with db.get_bind().begin() as connection:
        reserved = connection.execute(statement, {"budget": budget}).scalar_one_or_none()
    if reserved is None:
        raise LlmError("quota_exhausted")


def _record_failure(db: Session, exhausted: bool = False) -> None:
    values = {"failures": LlmUsage.failures + 1}
    if exhausted:
        values["quota_exhausted"] = True
    with db.get_bind().begin() as connection:
        connection.execute(update(LlmUsage).where(LlmUsage.day == _today()).values(**values))


def _parse[T: BaseModel](content: str | None, schema: type[T]) -> T:
    if content is None:
        raise ValueError("The reply was empty.")
    body = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content)
    return schema.model_validate(json.loads(body))


def generate_json[T: BaseModel](
    db: Session,
    client: ChatClient,
    settings: Settings,
    messages: list[dict],
    schema: type[T],
) -> tuple[T, str]:
    """Return the validated reply and the model that produced it."""
    if settings.openrouter_api_key is None:
        raise LlmError("not_configured")
    last: ErrorCode = "unavailable"
    budget = settings.llm_daily_request_budget
    for model in [settings.llm_model, *settings.llm_fallback_models][:2]:
        _reserve(db, budget)
        conversation = list(messages)
        try:
            content = client.complete(model, conversation, settings.llm_max_tokens)
        except TransportError as error:
            if error.status == 429:
                _record_failure(db, exhausted=True)
                raise LlmError("quota_exhausted") from None
            logger.warning("LLM model %s failed with status %s", model, error.status)
            _record_failure(db)
            last = "unavailable"
            continue
        for attempt in (1, 2):
            try:
                return _parse(content, schema), model
            except (ValueError, ValidationError) as error:
                if attempt == 2:
                    break
                _reserve(db, budget)
                conversation += [
                    {"role": "assistant", "content": content or ""},
                    {
                        "role": "user",
                        "content": "Your reply was not valid JSON for the schema: "
                        f"{str(error)[:500]}. Reply with JSON only.",
                    },
                ]
                try:
                    content = client.complete(model, conversation, settings.llm_max_tokens)
                except TransportError as transport_error:
                    if transport_error.status == 429:
                        _record_failure(db, exhausted=True)
                        raise LlmError("quota_exhausted") from None
                    content = None
        logger.warning("LLM model %s returned invalid output", model)
        _record_failure(db)
        last = "invalid_output"
    raise LlmError(last)
