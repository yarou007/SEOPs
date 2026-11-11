"""Shared fakes for insights tests; the suite never calls a real LLM."""

from pydantic import SecretStr

from app.config import get_settings


class FakeChatClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, model, messages, max_tokens):
        self.calls.append((model, [dict(message) for message in messages]))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def llm_settings(**update):
    values = {
        "openrouter_api_key": SecretStr("sk-test-key"),
        "llm_model": "primary:free",
        "llm_fallback_models": ["fallback:free"],
        "llm_daily_request_budget": 45,
    }
    return get_settings().model_copy(update=values | update)
