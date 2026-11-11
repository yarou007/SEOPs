"""Analyst instructions and the JSON shapes the LLM must return."""

import json
from typing import Literal

from pydantic import BaseModel, Field

SYSTEM_PROMPT = """You are a senior SEO and conversion analyst for a small team that manages \
local-service websites. You answer in English.

Rules:
- The DATA CONTEXT below is your only source of facts. Use only figures that appear in it, \
and cite them (with their period) when you use them. Never invent or estimate numbers.
- If the data cannot answer the question, say "The data does not show this" and say which \
data would answer it.
- Present causes as hypotheses ("likely", "possibly"), not facts.
- Give concrete, page-level advice: which URL, what to change, and which KPI should move.
- Respect the data notes (hidden queries, lag days, partial query data).
- "ahrefs_web_analytics", when present, is a separate visitor tracker: its counts differ from GA4. \
Use its "changes" and "history" to describe how visitors and phone clicks evolved between periods.
- Always suggest sharper follow-up questions the team should ask next.
- Be concise: summaries of at most 120 words; every insight field at most two sentences.
- Reply with one JSON object that matches the JSON SCHEMA exactly. No text outside the JSON.
"""


class Evidence(BaseModel):
    metric: str = Field(max_length=200)
    value: str | float
    period: str = Field(max_length=200)


class InsightDraft(BaseModel):
    title: str = Field(max_length=200)
    problem: str
    evidence: list[Evidence] = Field(min_length=1)
    advice: str
    target_url: str | None = None
    target_kpi: str = Field(max_length=200)
    priority: Literal["high", "medium", "low"]


class ChatReply(BaseModel):
    answer_markdown: str
    suggested_questions: list[str] = Field(min_length=2, max_length=3)
    insights: list[InsightDraft] = Field(default_factory=list, max_length=5)


class WeeklyReply(BaseModel):
    summary_markdown: str
    insights: list[InsightDraft] = Field(min_length=1, max_length=5)
    suggested_questions: list[str] = Field(min_length=3, max_length=3)


def _system(context_json: str, schema: type[BaseModel], task: str) -> dict:
    return {
        "role": "system",
        "content": f"{SYSTEM_PROMPT}\nTASK: {task}\n\n"
        f"JSON SCHEMA:\n{json.dumps(schema.model_json_schema())}\n\n"
        f"DATA CONTEXT:\n{context_json}",
    }


def chat_messages(context_json: str, history: list, question: str) -> list[dict]:
    """History items are AiMessage rows (role, content), oldest first."""
    return [
        _system(
            context_json,
            ChatReply,
            "Answer the team's question. Add 0-5 insights only for problems the data shows.",
        ),
        *({"role": message.role, "content": message.content} for message in history),
        {"role": "user", "content": question},
    ]


def weekly_messages(context_json: str, report: dict) -> list[dict]:
    return [
        _system(
            context_json,
            WeeklyReply,
            "Write the weekly analysis: a short Markdown summary of what changed and why it "
            "matters, then the 1-5 most valuable insights, highest priority first.",
        ),
        {
            "role": "user",
            "content": "Weekly report (rule-based flags) for this period:\n"
            + json.dumps(report, default=str)[:20_000],
        },
    ]
