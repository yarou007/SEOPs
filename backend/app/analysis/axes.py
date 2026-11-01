"""Eight analysis views over stored evidence, with explicit availability limits."""

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import metrics
from app.config import get_settings, zones
from app.models import AxisSnapshot, GscDaily, GscIndexStatus, Site, User, UserSite

QUERY_LIMIT = 1000
QUERY_REASON = (
    "Visible queries are partial: Google hides queries; page-summed "
    "queries can count multiple URLs."
)


def answer(status: str, data: dict, reason: str | None = None) -> dict:
    return metrics.public({"status": status, "reason": reason, "data": data})


def snapshot(
    db: Session, domain: str, kind: str, window: metrics.Window | None = None
) -> AxisSnapshot | None:
    statement = select(AxisSnapshot).where(AxisSnapshot.site == domain, AxisSnapshot.kind == kind)
    if window:
        statement = statement.where(
            AxisSnapshot.start_date == window.start, AxisSnapshot.end_date == window.end
        )
    return db.scalar(
        statement.order_by(AxisSnapshot.collected_at.desc(), AxisSnapshot.id.desc()).limit(1)
    )


def _queries(db: Session, domain: str, window: metrics.Window) -> list[dict]:
    return metrics.gsc_queries(db, domain, window, limit=QUERY_LIMIT)


def _flag(row: dict) -> dict:
    return {**row, "high_impressions_zero_clicks": row["impressions"] >= 100 and row["clicks"] == 0}


def impressions_clicks(db: Session, site: Site, window: metrics.Window) -> dict:
    pages = metrics.gsc_pages(db, site.domain, window, limit=QUERY_LIMIT)
    queries = _queries(db, site.domain, window)
    data = {
        "pages": [_flag(row) for row in pages],
        "queries": [_flag(row) for row in queries],
        "limit": QUERY_LIMIT,
        "explanation": (
            "Low CTR can reflect position or search intent; these numbers do not prove why."
        ),
    }
    if not pages and not queries:
        return answer(
            "needs_setup", data, "Sync GSC and replay query-free totals for this date range."
        )
    reason = QUERY_REASON
    if not pages:
        reason += " Query-free page totals are missing; replay this date range."
    return answer("partial", data, reason + " Tables show up to 1,000 rows each.")


def funnel(db: Session, site: Site, window: metrics.Window) -> dict:
    gsc = metrics.gsc_totals(db, site.domain, window)
    ga4 = metrics.ga4_totals(db, site.domain, window)
    calls = snapshot(db, site.domain, "calls", window)
    event = get_settings().ga4_call_click_events.get(site.slug)
    call_count = calls.data.get("count") if calls and calls.data.get("event") == event else None
    values = [
        gsc["impressions"] if gsc else None,
        gsc["clicks"] if gsc else None,
        ga4["sessions"] if ga4 else None,
        call_count,
    ]
    steps = [
        {
            "name": name,
            "value": value,
            "rate_from_previous": (
                Decimal(value) / values[i - 1]
                if i and value is not None and values[i - 1]
                else None
            ),
        }
        for i, (name, value) in enumerate(
            zip(["Impressions", "Clicks", "Visits", "Call clicks"], values, strict=True)
        )
    ]
    data = {
        "steps": steps,
        "call_event": event,
        "note": (
            "Cross-source directional ratios, not a matched-user funnel. GA4 "
            "includes all traffic; time zones may differ."
        ),
    }
    if not event or call_count is None:
        return answer(
            "needs_setup",
            data,
            (
                "Call clicks are not tracked yet. Configure an existing GA4 call "
                "event and collect this range."
            ),
        )
    if gsc is None or ga4 is None:
        return answer(
            "partial", data, "GSC property totals or GA4 sessions are missing for this range."
        )
    return answer("ready", data)


def devices(db: Session, site: Site, window: metrics.Window) -> dict:
    gsc = [
        {"device": device, **totals}
        for device in ["MOBILE", "DESKTOP", "TABLET"]
        if (totals := metrics.gsc_totals(db, site.domain, window, device)) is not None
    ]
    os = snapshot(db, site.domain, "os", window)
    data = {
        "devices": gsc,
        "operating_systems": os.data["rows"] if os else [],
        "os_scope": "site-level",
    }
    if not gsc and not os:
        return answer(
            "needs_setup",
            data,
            "Sync GSC device totals and collect a GA4 OS report for this range.",
        )
    reason = "OS data is site-level only; it cannot be linked to a GSC query or page."
    if not os:
        reason += " Collect the GA4 OS report for this range."
    if not gsc:
        reason += " GSC device totals need a replay for this range."
    return answer("partial", data, reason)


def geography(db: Session, site: Site, window: metrics.Window) -> dict:
    if not zones.ZONES:
        return answer(
            "needs_setup", {"zones": []}, "Configure your service cities and neighborhoods first."
        )
    # Aggregate all matches in SQL, not just the displayed top queries.
    rows = []
    for zone in zones.ZONES:
        pattern = r"\m" + re.escape(zone.strip().lower()) + r"\M"
        if not zone.strip():
            continue
        statement = select(*metrics._gsc_columns()).where(
            *metrics._gsc_filters(site.domain, window, grain="query"),
            func.lower(GscDaily.query).op("~")(pattern),
            func.lower(GscDaily.query).op("~")(r"\memergency\s+locksmith\M"),
        )
        values = dict(db.execute(statement).mappings().one())
        if values["clicks"] is not None:
            rows.append({"zone": zone, **values})
    return answer(
        "partial",
        {"zones": rows},
        "Query wording indicates zones, not visitor location. Hidden queries are excluded."
        + (" No matching emergency locksmith queries in this range." if not rows else ""),
    )


def sitemaps(db: Session, site: Site, window: metrics.Window) -> dict:
    evidence = snapshot(db, site.domain, "sitemaps")
    latest = evidence.data if evidence else {}
    inspected = list(
        db.scalars(
            select(GscIndexStatus)
            .where(GscIndexStatus.site == site.domain)
            .order_by(GscIndexStatus.url)
        )
    )
    urls = [
        {
            "url": row.url,
            "verdict": row.verdict,
            "reason": row.coverage_state,
            "indexing_state": row.indexing_state,
            "inspected_at": row.inspected_at,
        }
        for row in inspected
    ]
    indexed = sum(row.verdict == "PASS" for row in inspected)
    not_indexed = sum(row.verdict in {"FAIL", "NEUTRAL"} for row in inspected)
    data = {
        "sitemaps": latest.get("sitemaps", []),
        "submitted": latest.get("submitted"),
        "note": latest.get("submitted_note"),
        "indexed": indexed,
        "not_indexed": not_indexed,
        "unknown": len(inspected) - indexed - not_indexed,
        "inspected": len(inspected),
        "urls": urls,
        "collected_at": evidence.collected_at if evidence else None,
        "scope": "Latest inspection snapshot, not historical date-range data",
    }
    if not evidence:
        return answer(
            "needs_setup",
            data,
            "Collect sitemap metadata and inspect up to 200 submitted URLs per run.",
        )
    reason = "Inspection is a bounded sample, not a site-wide indexed-page count."
    if not inspected:
        reason = "Sitemaps collected; run the first URL inspection (up to 200 URLs)."
    if evidence.collected_at < datetime.now(UTC) - timedelta(days=7) or any(
        row.inspected_at < datetime.now(UTC) - timedelta(days=7) for row in inspected
    ):
        reason += " Snapshot is older than seven days; collect it again."
    return answer("partial", data, reason)


def internal_links(db: Session, site: Site, window: metrics.Window) -> dict:
    evidence = snapshot(db, site.domain, "internal-links")
    data = (
        evidence.data
        if evidence
        else {"orphans": [], "broken_links": [], "inbound_distribution": []}
    )
    if not evidence:
        return answer(
            "needs_setup",
            data,
            "Upload an Ahrefs Site Audit CSV with URL, inbound links and HTTP status columns.",
        )
    return answer(
        "ready",
        {
            **data,
            "collected_at": evidence.collected_at,
            "scope": "Latest uploaded crawl; date filter does not change this snapshot",
        },
    )


def site_links(db: Session, site: Site, window: metrics.Window, user: User) -> dict:
    statement = select(Site).where(Site.active.is_(True)).order_by(Site.slug)
    if user.role != "admin":
        statement = statement.join(UserSite).where(UserSite.user_id == user.id)
    configured = get_settings().portfolio_site_slugs
    if configured:
        statement = statement.where(Site.slug.in_(configured))
    visible = list(db.scalars(statement))
    # Show only authorized sites, never disclose an inaccessible portfolio member.
    portfolio = ([site] + [row for row in visible if row.id != site.id])[:5]
    imports = {row.domain: snapshot(db, row.domain, "backlinks") for row in portfolio}
    matrix = []
    for source in portfolio:
        for target in portfolio:
            upload = imports[target.domain]  # backlinks export belongs to the target site
            count = (
                None
                if upload is None
                else sum(
                    link.get("links", 1)
                    for link in upload.data["links"]
                    if link["source_domain"] == source.domain
                    and link["target_domain"] == target.domain
                )
            )
            matrix.append({"source": source.domain, "target": target.domain, "links": count})
    data = {
        "sites": [{"slug": row.slug, "domain": row.domain} for row in portfolio],
        "matrix": matrix,
        "scope": "Latest uploaded backlinks, not historical date-range data",
    }
    if not any(imports.values()):
        return answer(
            "needs_setup",
            data,
            "Upload backlinks CSVs for the five real portfolio sites. Unknown cells are not zero.",
        )
    complete = (
        len(portfolio) == 5
        and all(imports.values())
        and all(not row.domain.endswith(".example") for row in portfolio)
    )
    return answer(
        "ready" if complete else "partial",
        data,
        None
        if complete
        else (
            "Upload exports for all five accessible real sites; replace "
            "placeholder domains. Unknown cells are not zero."
        ),
    )


def search_requests(db: Session, site: Site, window: metrics.Window) -> dict:
    queries = _queries(db, site.domain, window)
    rows = [
        {
            **row,
            "opportunity": row["impressions"] * (1 - row["ctr"])
            if row["avg_position"] is not None
            and 4 <= row["avg_position"] <= 20
            and row["ctr"] is not None
            else None,
            "volume": None,
            "difficulty": None,
        }
        for row in queries
    ]
    return answer(
        "partial" if rows else "needs_setup",
        {
            "queries": rows,
            "keyword_provider": {"status": "needs_setup", "reason": "Needs keyword provider"},
            "limit": QUERY_LIMIT,
        },
        QUERY_REASON
        + " Volume and difficulty need a keyword provider; showing up to 1,000 queries."
        if rows
        else "Sync GSC query detail. Volume and difficulty need a keyword provider.",
    )
