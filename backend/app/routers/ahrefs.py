"""Ahrefs data: Web Analytics "all stats" import, latest data with changes, other uploads."""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from app.access import AccessibleSite
from app.analysis import web_analytics as wa
from app.auth import CurrentUser, check_auth_origin
from app.db import DbSession
from app.models import AhrefsCsvRow, AxisSnapshot
from app.routers.analytics import no_store
from app.routers.sites import require_manager

router = APIRouter(
    prefix="/api/sites/{slug}/ahrefs", tags=["ahrefs"], dependencies=[Depends(no_store)]
)


class WebAnalyticsImport(BaseModel):
    period_start: date
    period_end: date
    files: list[wa.WebAnalyticsFile] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def ordered(self):
        if self.period_end < self.period_start:
            raise ValueError("The period must end on or after its start")
        return self


class WebAnalyticsOut(BaseModel):
    id: UUID
    period_start: date
    period_end: date
    imported_at: datetime
    totals: dict
    reports: dict
    files: dict


class PeriodOut(BaseModel):
    period_start: date
    period_end: date
    totals: dict


class UploadInfo(BaseModel):
    imported_at: datetime
    rows: int


class AhrefsOut(BaseModel):
    web_analytics: WebAnalyticsOut | None
    previous: PeriodOut | None
    changes: dict
    history: list[dict]
    backlinks: UploadInfo | None
    internal_links: UploadInfo | None


def _out(snapshot: AxisSnapshot) -> WebAnalyticsOut:
    return WebAnalyticsOut(
        id=snapshot.id,
        period_start=snapshot.start_date,
        period_end=snapshot.end_date,
        imported_at=snapshot.collected_at,
        totals=snapshot.data["totals"],
        reports=snapshot.data["reports"],
        files=snapshot.data["files"],
    )


def _upload(db, domain: str, kind: str) -> UploadInfo | None:
    snapshot = db.scalar(
        select(AxisSnapshot)
        .where(AxisSnapshot.site == domain, AxisSnapshot.kind == kind)
        .order_by(AxisSnapshot.collected_at.desc())
        .limit(1)
    )
    if snapshot is None:
        return None
    rows = db.scalar(
        select(func.count())
        .select_from(AhrefsCsvRow)
        .where(AhrefsCsvRow.snapshot_id == snapshot.id)
    )
    return UploadInfo(imported_at=snapshot.collected_at, rows=rows)


@router.post(
    "/web-analytics",
    status_code=201,
    response_model=WebAnalyticsOut,
    dependencies=[Depends(check_auth_origin)],
)
def import_web_analytics(
    payload: WebAnalyticsImport, site: AccessibleSite, user: CurrentUser, db: DbSession
) -> WebAnalyticsOut:
    require_manager(site, user)
    try:
        snapshot = wa.import_web_analytics(
            db, site, payload.period_start, payload.period_end, payload.files
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    db.refresh(snapshot)
    return _out(snapshot)


@router.get("", response_model=AhrefsOut)
def ahrefs_data(site: AccessibleSite, db: DbSession) -> AhrefsOut:
    latest = wa.latest_web_analytics(db, site.domain)
    previous = wa.previous_web_analytics(db, site.domain, latest) if latest else None
    return AhrefsOut(
        web_analytics=_out(latest) if latest else None,
        previous=PeriodOut(
            period_start=previous.start_date,
            period_end=previous.end_date,
            totals=previous.data["totals"],
        )
        if previous
        else None,
        changes=wa.compare_imports(latest.data, previous.data if previous else None)
        if latest
        else {},
        history=wa.history(db, site.domain),
        backlinks=_upload(db, site.domain, "backlinks"),
        internal_links=_upload(db, site.domain, "internal-links"),
    )
