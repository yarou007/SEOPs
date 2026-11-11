"""Compact, JSON-safe summary of one site's stored data, sent to the LLM as its only facts."""

import json
from decimal import Decimal

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.orm import Session

from app import metrics
from app.analysis import web_analytics as wa
from app.analysis.weekly import DATA_NOTES
from app.models import AhrefsWebAnalytics, GscDaily, Site, WeeklyReport

TOP_ROWS = 25
TOP_COUNTRIES = 10
DEVICES = ["MOBILE", "DESKTOP", "TABLET"]
# Trimmed from the end, in this order, until the rendered context fits.
TRIM_ORDER = ["top_queries", "top_pages", "daily"]
AHREFS_TOP = 10
AHREFS_COLUMNS = [
    "item",
    "visitors",
    "views",
    "entrances",
    "exits",
    "count",
    "exit_rate",
    "bounce_rate",
    "visit_duration",
    "time_on_page",
    "conversion_rate",
]


def gsc_countries(db: Session, domain: str, window: metrics.Window) -> list[dict]:
    impressions = func.sum(GscDaily.impressions)
    statement = (
        select(
            GscDaily.country,
            func.sum(GscDaily.clicks).label("clicks"),
            impressions.label("impressions"),
            (cast(func.sum(GscDaily.clicks), Numeric) / func.nullif(impressions, 0)).label("ctr"),
            (
                func.sum(GscDaily.position * GscDaily.impressions) / func.nullif(impressions, 0)
            ).label("avg_position"),
        )
        .where(
            GscDaily.site == domain,
            GscDaily.data_date.between(window.start, window.end),
            GscDaily.page == "",
            GscDaily.query == "",
            GscDaily.device == "",
            GscDaily.country != "all",
        )
        .group_by(GscDaily.country)
        .order_by(impressions.desc(), GscDaily.country)
        .limit(TOP_COUNTRIES)
    )
    return [dict(row) for row in db.execute(statement).mappings()]


def build_context(db: Session, site: Site, window: metrics.Window) -> dict:
    domain = site.domain
    previous = window.previous()
    totals = {
        "current": metrics.period_totals(db, domain, window),
        "previous": metrics.period_totals(db, domain, previous),
    }
    report = db.scalar(
        select(WeeklyReport.report)
        .where(WeeklyReport.site == domain)
        .order_by(WeeklyReport.report_date.desc())
        .limit(1)
    )
    devices = []
    for device in DEVICES:
        device_totals = metrics.gsc_totals(db, domain, window, device)
        if device_totals:
            devices.append({"device": device, **device_totals})
    has_data = any(totals[period][source] for period in totals for source in ("gsc", "ga4"))
    context = {
        "site": {"domain": domain, "name": site.display_name},
        "window": {"start": window.start, "end": window.end},
        "previous_window": {"start": previous.start, "end": previous.end},
        "has_data": has_data,
        "totals": totals,
        "daily": metrics.timeseries(db, domain, window),
        "top_pages": metrics.gsc_pages(db, domain, window, limit=TOP_ROWS),
        "top_queries": metrics.gsc_queries(db, domain, window, limit=TOP_ROWS),
        "devices": devices,
        "countries": gsc_countries(db, domain, window),
        "weekly_flags": {
            key: (report or {}).get(key)
            for key in ["report_date", "top_pages", "query_candidates", "warnings"]
        },
        "sync_status": {
            source: {key: (log or {}).get(key) for key in ["last_loaded_date", "status"]}
            for source, log in metrics.sync_status(db, domain).items()
        },
        "data_notes": DATA_NOTES,
    }
    ahrefs = ahrefs_block(db, domain)
    if ahrefs:
        context["ahrefs_web_analytics"] = ahrefs
    return metrics.public(context)


def _ahrefs_rows(db: Session, snapshot_id, report: str) -> list[dict]:
    statement = (
        select(*(getattr(AhrefsWebAnalytics, name) for name in AHREFS_COLUMNS))
        .where(AhrefsWebAnalytics.snapshot_id == snapshot_id, AhrefsWebAnalytics.report == report)
        .order_by(AhrefsWebAnalytics.visitors.desc().nulls_last(), AhrefsWebAnalytics.id)
        .limit(AHREFS_TOP)
    )
    # Keep only the columns this report has.
    return [
        {key: value for key, value in row.items() if value is not None}
        for row in db.execute(statement).mappings()
    ]


def ahrefs_block(db: Session, domain: str) -> dict | None:
    """Latest Ahrefs Web Analytics import from the database, with the previous one and changes."""
    latest = wa.latest_web_analytics(db, domain)
    if latest is None:
        return None
    previous = wa.previous_web_analytics(db, domain, latest)

    def period(snapshot):
        return {"start": snapshot.start_date, "end": snapshot.end_date}

    return {
        "source": "Ahrefs Web Analytics (separate visitor tracker; counts differ from GA4)",
        "period": period(latest),
        "totals": latest.data["totals"],
        **{
            report: _ahrefs_rows(db, latest.id, report)
            for report in ["top_pages", "entry_pages", "channels", "sources", "devices", "events"]
        },
        "previous": {"period": period(previous), "totals": previous.data["totals"]}
        if previous
        else None,
        "changes": wa.compare_imports(latest.data, previous.data if previous else None),
        "history": wa.history(db, domain),
    }


def render_context(context: dict, limit: int = 30_000) -> str:
    context = {**context, **{key: list(context.get(key) or []) for key in TRIM_ORDER}}
    rendered = json.dumps(context, separators=(",", ":"), default=str)
    for key in TRIM_ORDER:
        while len(rendered) > limit and context[key]:
            # Drop roughly the share of rows needed, at least one row per pass.
            excess = len(rendered) - limit
            per_row = max(1, len(json.dumps(context[key], default=str)) // len(context[key]))
            drop = max(1, excess // per_row)
            context[key] = context[key][:-drop] if drop < len(context[key]) else []
            rendered = json.dumps(context, separators=(",", ":"), default=str)
    return rendered


def normalize_number(value) -> str:
    text = format(Decimal(str(value)).quantize(Decimal("0.0001")), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def context_numbers(context) -> set[str]:
    if isinstance(context, dict):
        return set().union(*(context_numbers(item) for item in context.values()))
    if isinstance(context, (list, tuple)):
        return set().union(*(context_numbers(item) for item in context))
    if isinstance(context, bool) or not isinstance(context, (int, float, Decimal)):
        return set()
    return {normalize_number(context)}
