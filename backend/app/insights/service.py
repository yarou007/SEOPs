"""Chat answers and weekly analysis, stored only after the LLM succeeds."""

import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import metrics
from app.config import Settings
from app.insights.context import build_context, context_numbers, normalize_number, render_context
from app.insights.llm import ChatClient, generate_json
from app.insights.prompts import (
    ChatReply,
    Evidence,
    InsightDraft,
    WeeklyReply,
    chat_messages,
    weekly_messages,
)
from app.models import AiConversation, AiInsight, AiMessage, Site, User, WeeklyReport

MAX_QUESTION = 2_000
HISTORY = 6
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_question(text: str) -> str:
    question = CONTROL.sub("", text).strip()
    if not question:
        raise ValueError("Enter a question.")
    if len(question) > MAX_QUESTION:
        raise ValueError(f"Questions must be at most {MAX_QUESTION:,} characters.")
    return question


def _number(value) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("%", "").strip())
    except InvalidOperation:
        return None


def ground(evidence: list[Evidence], numbers: set[str]) -> list[dict]:
    """Mark each evidence value as grounded when it matches a context figure."""
    accepted = set(numbers)
    for text in numbers:
        value = Decimal(text)
        # Accept the usual roundings, and ratios quoted as percentages.
        for candidate in (value, value * 100):
            accepted.update(normalize_number(round(candidate, places)) for places in (0, 1, 2))
    result = []
    for item in evidence:
        value = _number(item.value)
        grounded = value is None or normalize_number(value) in accepted
        result.append({**item.model_dump(), "grounded": grounded})
    return result


def _insight(site: Site, draft: InsightDraft, numbers: set[str], model: str, **extra) -> AiInsight:
    return AiInsight(
        site=site.domain,
        title=draft.title,
        problem=draft.problem,
        evidence=ground(draft.evidence, numbers),
        advice=draft.advice,
        target_url=draft.target_url,
        target_kpi=draft.target_kpi,
        priority=draft.priority,
        model=model,
        **extra,
    )


def ask(
    db: Session,
    site: Site,
    user: User,
    question: str,
    conversation_id: UUID | None,
    window: metrics.Window,
    client: ChatClient,
    settings: Settings,
) -> AiMessage:
    question = clean_question(question)
    if conversation_id is None:
        conversation = AiConversation(
            site=site.domain, created_by_user_id=user.id, title=question[:80]
        )
        history = []
    else:
        conversation = db.get(AiConversation, conversation_id)
        if conversation is None or conversation.site != site.domain:
            raise LookupError("Conversation not found")
        history = list(
            reversed(
                db.scalars(
                    select(AiMessage)
                    .where(AiMessage.conversation_id == conversation.id)
                    .order_by(AiMessage.created_at.desc())
                    .limit(HISTORY)
                ).all()
            )
        )
    context = build_context(db, site, window)
    reply, model = generate_json(
        db, client, settings, chat_messages(render_context(context), history, question), ChatReply
    )
    numbers = context_numbers(context)
    asked_at = datetime.now(UTC)
    db.add(conversation)
    db.flush()
    db.add(
        AiMessage(
            conversation_id=conversation.id, role="user", content=question, created_at=asked_at
        )
    )
    answer = AiMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=reply.answer_markdown,
        suggested_questions=reply.suggested_questions,
        context_summary={"window": context["window"], "has_data": context["has_data"]},
        model=model,
        created_at=asked_at + timedelta(microseconds=1),
    )
    db.add(answer)
    db.flush()
    db.add_all(
        _insight(site, draft, numbers, model, source="chat", message_id=answer.id)
        for draft in reply.insights
    )
    db.commit()
    db.refresh(answer)
    return answer


def generate_weekly(
    db: Session, site: Site, client: ChatClient, settings: Settings
) -> WeeklyReport:
    stored = db.scalar(
        select(WeeklyReport)
        .where(WeeklyReport.site == site.domain)
        .order_by(WeeklyReport.report_date.desc())
        .limit(1)
    )
    if stored is None:
        raise LookupError("No weekly report stored for this website yet")
    current = stored.report["windows"]["current"]
    window = metrics.Window(
        date.fromisoformat(current["start"]), date.fromisoformat(current["end"])
    )
    context = build_context(db, site, window)
    reply, model = generate_json(
        db,
        client,
        settings,
        weekly_messages(render_context(context), stored.report),
        WeeklyReply,
    )
    numbers = context_numbers(context)
    db.execute(
        delete(AiInsight).where(
            AiInsight.site == site.domain,
            AiInsight.source == "weekly",
            AiInsight.report_date == stored.report_date,
        )
    )
    db.add_all(
        _insight(site, draft, numbers, model, source="weekly", report_date=stored.report_date)
        for draft in reply.insights
    )
    stored.ai_summary = reply.summary_markdown
    db.commit()
    db.refresh(stored)
    return stored
