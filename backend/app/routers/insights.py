"""AI insights: chat per website, stored advice and its status, weekly AI analysis."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app import metrics
from app.access import AccessibleSite
from app.auth import CurrentUser, check_auth_origin
from app.config import Settings, get_settings
from app.db import DbSession
from app.insights.llm import ChatClient, LlmError, OpenRouterClient, UsageInfo, usage_today
from app.insights.service import ask, generate_weekly
from app.models import AiConversation, AiInsight, AiMessage
from app.routers.analytics import no_store
from app.routers.sites import require_manager

router = APIRouter(
    prefix="/api/sites/{slug}/insights", tags=["insights"], dependencies=[Depends(no_store)]
)
Status = Literal["new", "accepted", "dismissed", "done"]
LLM_STATUS = {"not_configured": 503, "quota_exhausted": 429}


def get_llm_settings() -> Settings:
    return get_settings()


def get_chat_client(settings: Annotated[Settings, Depends(get_llm_settings)]) -> ChatClient:
    return OpenRouterClient(settings)


LlmSettings = Annotated[Settings, Depends(get_llm_settings)]
Client = Annotated[ChatClient, Depends(get_chat_client)]


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    suggested_questions: list[str]
    model: str | None
    created_at: datetime


class InsightOut(BaseModel):
    id: UUID
    source: str
    report_date: date | None
    message_id: UUID | None
    title: str
    problem: str
    evidence: list[dict]
    advice: str
    target_url: str | None
    target_kpi: str
    priority: str
    status: str
    model: str
    created_at: datetime
    updated_at: datetime


class AskInput(BaseModel):
    question: str = Field(min_length=1, max_length=4_000)
    conversation_id: UUID | None = None
    start: date | None = None
    end: date | None = None


class StatusInput(BaseModel):
    status: Status


def _llm_failure(error: LlmError) -> HTTPException:
    return HTTPException(status_code=LLM_STATUS.get(error.code, 502), detail=error.message)


def _insights(db, site, **filters) -> list[AiInsight]:
    statement = select(AiInsight).where(AiInsight.site == site.domain)
    for column, value in filters.items():
        if value is not None:
            statement = statement.where(getattr(AiInsight, column) == value)
    return statement.order_by(AiInsight.created_at.desc(), AiInsight.id)


@router.get("/status", response_model=UsageInfo)
def status(site: AccessibleSite, db: DbSession, settings: LlmSettings) -> UsageInfo:
    return usage_today(db, settings)


@router.get("/conversations")
def conversations(site: AccessibleSite, db: DbSession) -> list[dict]:
    last = (
        select(AiMessage.conversation_id, func.max(AiMessage.created_at).label("last"))
        .group_by(AiMessage.conversation_id)
        .subquery()
    )
    rows = db.execute(
        select(AiConversation, last.c.last)
        .outerjoin(last, last.c.conversation_id == AiConversation.id)
        .where(AiConversation.site == site.domain)
        .order_by(func.coalesce(last.c.last, AiConversation.created_at).desc())
        .limit(100)
    ).all()
    return [
        {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "last_message_at": last_at,
        }
        for conversation, last_at in rows
    ]


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: UUID, site: AccessibleSite, db: DbSession) -> dict:
    found = db.get(AiConversation, conversation_id)
    if found is None or found.site != site.domain:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = db.scalars(
        select(AiMessage)
        .where(AiMessage.conversation_id == found.id)
        .order_by(AiMessage.created_at)
    ).all()
    return {
        "id": found.id,
        "title": found.title,
        "messages": [MessageOut.model_validate(m, from_attributes=True) for m in messages],
    }


@router.post("/ask", dependencies=[Depends(check_auth_origin)])
def ask_question(
    payload: AskInput,
    site: AccessibleSite,
    user: CurrentUser,
    db: DbSession,
    settings: LlmSettings,
    client: Client,
) -> dict:
    require_manager(site, user)
    try:
        window = metrics.resolve_window(payload.start, payload.end)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if settings.openrouter_api_key is None:
        raise _llm_failure(LlmError("not_configured"))
    totals = [metrics.period_totals(db, site.domain, w) for w in (window, window.previous())]
    if not any(period[source] for period in totals for source in ("gsc", "ga4")):
        raise HTTPException(
            status_code=409, detail="No data stored for this website yet. Run an import first."
        )
    try:
        message = ask(
            db, site, user, payload.question, payload.conversation_id, window, client, settings
        )
    except LlmError as error:
        raise _llm_failure(error) from None
    except LookupError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    insights = db.scalars(_insights(db, site, message_id=message.id)).all()
    return {
        "conversation_id": message.conversation_id,
        "message": MessageOut.model_validate(message, from_attributes=True),
        "insights": [InsightOut.model_validate(i, from_attributes=True) for i in insights],
    }


@router.get("", response_model=list[InsightOut])
def list_insights(
    site: AccessibleSite,
    db: DbSession,
    status: Status | None = None,
    source: Literal["weekly", "chat"] | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AiInsight]:
    statement = _insights(db, site, status=status, source=source).limit(limit).offset(offset)
    return list(db.scalars(statement))


@router.patch("/{insight_id}", response_model=InsightOut, dependencies=[Depends(check_auth_origin)])
def update_insight(
    insight_id: UUID,
    payload: StatusInput,
    site: AccessibleSite,
    user: CurrentUser,
    db: DbSession,
) -> AiInsight:
    require_manager(site, user)
    insight = db.get(AiInsight, insight_id)
    if insight is None or insight.site != site.domain:
        raise HTTPException(status_code=404, detail="Insight not found")
    insight.status = payload.status
    db.commit()
    db.refresh(insight)
    return insight


@router.post("/weekly", dependencies=[Depends(check_auth_origin)])
def weekly(
    site: AccessibleSite,
    user: CurrentUser,
    db: DbSession,
    settings: LlmSettings,
    client: Client,
) -> dict:
    require_manager(site, user)
    try:
        report = generate_weekly(db, site, client, settings)
    except LlmError as error:
        raise _llm_failure(error) from None
    except LookupError:
        raise HTTPException(
            status_code=404, detail="No weekly report stored for this website yet."
        ) from None
    insights = db.scalars(
        _insights(db, site, source="weekly", report_date=report.report_date)
    ).all()
    return {
        "report_date": report.report_date,
        "ai_summary": report.ai_summary,
        "insights": [InsightOut.model_validate(i, from_attributes=True) for i in insights],
    }
