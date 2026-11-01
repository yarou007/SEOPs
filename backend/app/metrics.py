"""Read-only SQL aggregations shared by the API and weekly analysis."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Ga4Daily, Ga4SyncLog, GscDaily, GscSyncLog
from app.sync.common import today_in


@dataclass(frozen=True)
class Window:
    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def previous(self) -> "Window":
        return Window(self.start - timedelta(days=self.days), self.start - timedelta(days=1))


def default_end(settings: Settings | None = None) -> date:
    settings = settings or get_settings()
    return today_in(settings.sync_timezone) - timedelta(days=settings.sync_lag_days)


def resolve_window(start: date | None = None, end: date | None = None) -> Window:
    end = end or default_end()
    start = start or end - timedelta(days=27)
    # Calendar months, clamping month-end dates (e.g. June 30 -> February 28).
    month = end.year * 12 + end.month - 1 - 16
    year, zero_month = divmod(month, 12)
    if year < 1:
        earliest = date.min
    else:
        earliest = date(year, zero_month + 1, min(end.day, monthrange(year, zero_month + 1)[1]))
    if start > end:
        raise ValueError("start must be on or before end")
    if start < earliest:
        raise ValueError("range must not exceed 16 calendar months")
    if start.toordinal() <= (end - start).days + 1:
        raise ValueError("range must allow an equal-length previous window")
    return Window(start, end)


def public(value, key: str = ""):
    """Round only at the presentation boundary; analysis keeps exact Decimal ratios."""
    if isinstance(value, dict):
        return {name: public(item, name) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [public(item, key) for item in value]
    if isinstance(value, Decimal):
        quantum = (
            "0.01" if key in {"avg_position", "impressions_lost", "drop_percent"} else "0.0001"
        )
        return float(value.quantize(Decimal(quantum), rounding=ROUND_HALF_UP))
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _gsc_filters(
    domain: str, window: Window, device: str | None = None, grain: str = "property"
) -> list:
    filters = [GscDaily.site == domain, GscDaily.data_date.between(window.start, window.end)]
    filters.append(GscDaily.country == "all")
    if grain == "query":
        filters.extend([GscDaily.query != "", GscDaily.page != "", GscDaily.device != ""])
        if device is not None:
            filters.append(GscDaily.device == device)
    else:
        filters.extend([GscDaily.query == "", GscDaily.device == (device or "")])
        filters.append(GscDaily.page != "" if grain == "page" else GscDaily.page == "")
    return filters


def _gsc_columns() -> list:
    impressions = func.sum(GscDaily.impressions)
    return [
        func.sum(GscDaily.clicks).label("clicks"),
        impressions.label("impressions"),
        (cast(func.sum(GscDaily.clicks), Numeric) / func.nullif(impressions, 0)).label("ctr"),
        (func.sum(GscDaily.position * GscDaily.impressions) / func.nullif(impressions, 0)).label(
            "avg_position"
        ),
    ]


def gsc_totals(db: Session, domain: str, window: Window, device: str | None = None) -> dict | None:
    result = dict(
        db.execute(select(*_gsc_columns()).where(*_gsc_filters(domain, window, device)))
        .mappings()
        .one()
    )
    return result if result["clicks"] is not None else None


def ga4_totals(db: Session, domain: str, window: Window) -> dict | None:
    result = dict(
        db.execute(
            select(
                func.sum(Ga4Daily.sessions).label("sessions"),
                func.sum(Ga4Daily.total_users).label("total_users"),
                func.sum(Ga4Daily.conversions).label("conversions"),
            ).where(Ga4Daily.site == domain, Ga4Daily.data_date.between(window.start, window.end))
        )
        .mappings()
        .one()
    )
    return result if result["sessions"] is not None else None


def period_totals(db: Session, domain: str, window: Window) -> dict:
    return {"gsc": gsc_totals(db, domain, window), "ga4": ga4_totals(db, domain, window)}


def gsc_pages(
    db: Session,
    domain: str,
    window: Window,
    device: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    statement = select(GscDaily.page, *_gsc_columns()).where(
        *_gsc_filters(domain, window, device, "page")
    )
    statement = (
        statement.group_by(GscDaily.page)
        .order_by(func.sum(GscDaily.impressions).desc(), GscDaily.page)
        .offset(offset)
    )
    if limit is not None:
        statement = statement.limit(limit)
    return [dict(row) for row in db.execute(statement).mappings()]


def gsc_queries(
    db: Session,
    domain: str,
    window: Window,
    device: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    min_impressions: int | None = None,
    position_range: tuple[float, float] | None = None,
) -> list[dict]:
    filters = _gsc_filters(domain, window, device, "query")
    page_totals = (
        select(
            GscDaily.query,
            GscDaily.page,
            func.sum(GscDaily.impressions).label("impressions"),
            func.sum(GscDaily.clicks).label("clicks"),
        )
        .where(*filters)
        .group_by(GscDaily.query, GscDaily.page)
        .subquery()
    )
    ranked = select(
        page_totals.c.query,
        page_totals.c.page,
        func.row_number()
        .over(
            partition_by=page_totals.c.query,
            order_by=[
                page_totals.c.impressions.desc(),
                page_totals.c.clicks.desc(),
                page_totals.c.page,
            ],
        )
        .label("rank"),
    ).subquery()
    aggregates = select(GscDaily.query, *_gsc_columns()).where(*filters).group_by(GscDaily.query)
    if min_impressions is not None:
        aggregates = aggregates.having(func.sum(GscDaily.impressions) >= min_impressions)
    if position_range is not None:
        position = func.sum(GscDaily.position * GscDaily.impressions) / func.nullif(
            func.sum(GscDaily.impressions),
            0,
        )
        aggregates = aggregates.having(position.between(*position_range))
    totals = aggregates.subquery()
    statement = (
        select(totals, ranked.c.page.label("top_page"))
        .join(
            ranked,
            (totals.c.query == ranked.c.query) & (ranked.c.rank == 1),
        )
        .order_by(totals.c.impressions.desc(), totals.c.query)
        .offset(offset)
    )
    if limit is not None:
        statement = statement.limit(limit)
    return [dict(row) for row in db.execute(statement).mappings()]


def ga4_pages(db: Session, domain: str, window: Window, limit: int, offset: int) -> list[dict]:
    sessions = func.sum(Ga4Daily.sessions)
    statement = select(
        Ga4Daily.page_path,
        sessions.label("sessions"),
        func.sum(Ga4Daily.total_users).label("total_users"),
        func.sum(Ga4Daily.conversions).label("conversions"),
        (func.sum(Ga4Daily.engagement_rate * Ga4Daily.sessions) / func.nullif(sessions, 0)).label(
            "engagement_rate"
        ),
    ).where(Ga4Daily.site == domain, Ga4Daily.data_date.between(window.start, window.end))
    statement = statement.group_by(Ga4Daily.page_path).order_by(sessions.desc(), Ga4Daily.page_path)
    return [dict(row) for row in db.execute(statement.limit(limit).offset(offset)).mappings()]


def timeseries(db: Session, domain: str, window: Window) -> list[dict]:
    gsc = {
        row.data_date: row
        for row in db.execute(
            select(
                GscDaily.data_date,
                func.sum(GscDaily.clicks).label("clicks"),
                func.sum(GscDaily.impressions).label("impressions"),
            )
            .where(*_gsc_filters(domain, window))
            .group_by(GscDaily.data_date)
        )
    }
    ga4 = {
        row.data_date: row
        for row in db.execute(
            select(
                Ga4Daily.data_date,
                func.sum(Ga4Daily.sessions).label("sessions"),
                func.sum(Ga4Daily.total_users).label("users"),
            )
            .where(Ga4Daily.site == domain, Ga4Daily.data_date.between(window.start, window.end))
            .group_by(Ga4Daily.data_date)
        )
    }
    result = []
    for i in range(window.days):
        day = window.start + timedelta(days=i)
        result.append(
            {
                "data_date": day,
                "gsc_clicks": gsc[day].clicks if day in gsc else None,
                "gsc_impressions": gsc[day].impressions if day in gsc else None,
                "ga4_sessions": ga4[day].sessions if day in ga4 else None,
                "ga4_users": ga4[day].users if day in ga4 else None,
            }
        )
    return result


def sync_status(db: Session, domain: str) -> dict:
    result = {}
    for source, model in [("gsc", GscSyncLog), ("ga4", Ga4SyncLog)]:
        log = db.get(model, domain)
        result[source] = (
            {
                key: getattr(log, key)
                for key in [
                    "site",
                    "last_loaded_date",
                    "last_run_at",
                    "status",
                    "rows_loaded",
                    "error",
                ]
            }
            if log
            else None
        )
    return result
