from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app import metrics
from app.access import AccessibleSite
from app.db import DbSession

router = APIRouter(prefix="/api/sites/{slug}", tags=["analytics"])
Device = Literal["MOBILE", "DESKTOP", "TABLET"]
Limit = Annotated[int, Query(ge=1, le=1000)]
Offset = Annotated[int, Query(ge=0)]


def date_window(start: date | None = None, end: date | None = None) -> metrics.Window:
    try:
        return metrics.resolve_window(start, end)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


DateWindow = Annotated[metrics.Window, Depends(date_window)]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router.dependencies.append(Depends(no_store))


class GscMetrics(BaseModel):
    clicks: int
    impressions: int
    ctr: float | None
    avg_position: float | None


class Ga4Metrics(BaseModel):
    sessions: int
    total_users: int
    conversions: int


class PeriodTotals(BaseModel):
    gsc: GscMetrics | None
    ga4: Ga4Metrics | None


class Summary(BaseModel):
    current_window: metrics.Window
    previous_window: metrics.Window
    current: PeriodTotals
    previous: PeriodTotals


class DayMetrics(BaseModel):
    data_date: date
    gsc_clicks: int | None
    gsc_impressions: int | None
    ga4_sessions: int | None
    ga4_users: int | None


class GscPage(GscMetrics):
    page: str


class GscQuery(GscMetrics):
    query: str
    top_page: str


class Ga4Page(Ga4Metrics):
    page_path: str
    engagement_rate: float | None


class SyncLog(BaseModel):
    site: str
    last_loaded_date: date | None
    last_run_at: datetime | None
    status: str | None
    rows_loaded: int | None
    error: str | None


class SourceStatus(BaseModel):
    gsc: SyncLog | None
    ga4: SyncLog | None


@router.get("/summary", response_model=Summary)
def summary(site: AccessibleSite, db: DbSession, window: DateWindow) -> dict:
    previous = window.previous()
    return {
        "current_window": window,
        "previous_window": previous,
        "current": metrics.public(metrics.period_totals(db, site.domain, window)),
        "previous": metrics.public(metrics.period_totals(db, site.domain, previous)),
    }


@router.get("/timeseries", response_model=list[DayMetrics])
def timeseries(site: AccessibleSite, db: DbSession, window: DateWindow) -> list[dict]:
    return metrics.timeseries(db, site.domain, window)


@router.get("/gsc/pages", response_model=list[GscPage])
def gsc_pages(
    site: AccessibleSite,
    db: DbSession,
    window: DateWindow,
    device: Device | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
) -> list[dict]:
    return metrics.public(metrics.gsc_pages(db, site.domain, window, device, limit, offset))


@router.get("/gsc/queries", response_model=list[GscQuery])
def gsc_queries(
    site: AccessibleSite,
    db: DbSession,
    window: DateWindow,
    device: Device | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
) -> list[dict]:
    return metrics.public(metrics.gsc_queries(db, site.domain, window, device, limit, offset))


@router.get("/ga4/pages", response_model=list[Ga4Page])
def ga4_pages(
    site: AccessibleSite,
    db: DbSession,
    window: DateWindow,
    limit: Limit = 100,
    offset: Offset = 0,
) -> list[dict]:
    return metrics.public(metrics.ga4_pages(db, site.domain, window, limit, offset))


@router.get("/status", response_model=SourceStatus)
def status(site: AccessibleSite, db: DbSession) -> dict:
    return metrics.sync_status(db, site.domain)
