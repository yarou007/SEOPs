"""Weekly opportunities, using page totals and exact ratios until presentation."""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app import metrics
from app.config import Settings, get_settings
from app.models import Site
from app.sync.common import today_in

ANALYSIS_THRESHOLDS = {
    "low_ctr_min_impressions": 200,
    "low_ctr_median_ratio": 0.5,
    "mobile_min_impressions": 100,
    "mobile_desktop_ctr_ratio": 0.7,
    "query_min_position": 8,
    "query_max_position": 20,
    "query_min_impressions": 50,
    "weekly_click_ratio": 0.6,
    "weekly_min_previous_clicks": 20,
    "zero_click_min_impressions": 100,
    "trend_drop_fraction": 0.3,
    "trend_min_previous_clicks": 20,
    "page_limit": 3,
    "query_limit": 10,
    "stale_extra_days": 2,
    "position_bands": [
        ("1–3", 1, 4),
        ("4–7", 4, 8),
        ("8–10", 8, 11),
        ("11–20", 11, 21),
        ("21+", 21, None),
    ],
    "flag_priority": {
        "zero_clicks": 5,
        "trend": 4,
        "clicks_dropping": 3,
        "low_ctr": 2,
        "mobile_gap": 1,
    },
}

DATA_NOTES = [
    "GSC hides some queries, so query totals will be lower than page totals. "
    "Always use page totals as the main figure.",
    "Page totals sum the available stored query-level GSC rows; hidden-query traffic "
    "cannot be reconstructed from this schema. Blank queries are omitted from query tables.",
    "GA4 total_users sums daily/page counts; it is not a deduplicated count "
    "of people across the window.",
    "Missing source/day data is unknown. Missing pages in an available GSC window count as zero "
    "for trend checks. Pages without both mobile and desktop data are not compared.",
]


def position_band(position: Decimal | float | None) -> str | None:
    if position is None:
        return None
    for label, lower, upper in ANALYSIS_THRESHOLDS["position_bands"]:
        if position >= lower and (upper is None or position < upper):
            return label
    return None


def band_medians(pages: list[dict]) -> dict[str, Decimal]:
    bands: dict[str, list[Decimal]] = {}
    for page in pages:
        band = position_band(page["avg_position"])
        if band and page["impressions"] > 0 and page["ctr"] is not None:
            bands.setdefault(band, []).append(page["ctr"])
    return {band: median(values) for band, values in bands.items()}


def _decimal(value) -> Decimal:
    return Decimal(str(value))


def _add_candidate(candidates: list[dict], check: str, reason: str, **numbers) -> None:
    candidates.append({"check": check, "reason": reason, **numbers})


def find_page_flags(
    current: list[dict],
    previous: list[dict],
    last7: list[dict],
    prev7: list[dict],
    mobile: list[dict],
    desktop: list[dict],
) -> list[dict]:
    """Return all distinct flagged pages, ranked before the display cap is applied."""
    if not current:
        return []  # A wholly missing current source is not evidence of zero traffic.
    threshold = ANALYSIS_THRESHOLDS
    medians = band_medians(current)
    now, before, recent, prior_week, phones, computers = [
        {row["page"]: row for row in rows}
        for rows in [current, previous, last7, prev7, mobile, desktop]
    ]
    flags = []
    for page in now.keys() | before.keys() | recent.keys() | prior_week.keys():
        row = now.get(
            page, {"page": page, "clicks": 0, "impressions": 0, "ctr": None, "avg_position": None}
        )
        band = position_band(row["avg_position"])
        benchmark = medians.get(band)
        lost = (
            max(Decimal(0), row["impressions"] * (benchmark - row["ctr"]))
            if (benchmark is not None and row["ctr"] is not None)
            else Decimal(0)
        )
        candidates = []

        if (
            row["impressions"] >= threshold["low_ctr_min_impressions"]
            and benchmark is not None
            and row["ctr"] is not None
            and row["ctr"] < benchmark * _decimal(threshold["low_ctr_median_ratio"])
        ):
            _add_candidate(candidates, "low_ctr", "high impressions, CTR below band median")
        phone, computer = phones.get(page), computers.get(page)
        if (
            phone
            and computer
            and phone["impressions"] >= threshold["mobile_min_impressions"]
            and computer["impressions"] >= threshold["mobile_min_impressions"]
            and phone["ctr"] is not None
            and computer["ctr"] is not None
            and phone["ctr"] < computer["ctr"] * _decimal(threshold["mobile_desktop_ctr_ratio"])
        ):
            _add_candidate(
                candidates,
                "mobile_gap",
                "mobile CTR gap",
                mobile_ctr=phone["ctr"],
                desktop_ctr=computer["ctr"],
                mobile_impressions=phone["impressions"],
                desktop_impressions=computer["impressions"],
            )
        recent_clicks = recent.get(page, {}).get("clicks", 0)
        prior_clicks = prior_week.get(page, {}).get("clicks", 0)
        if prior_clicks >= threshold[
            "weekly_min_previous_clicks"
        ] and recent_clicks < prior_clicks * _decimal(threshold["weekly_click_ratio"]):
            drop = (Decimal(1) - Decimal(recent_clicks) / prior_clicks) * 100
            _add_candidate(
                candidates,
                "clicks_dropping",
                f"clicks down {metrics.public(drop, 'drop_percent'):g}% week over week",
                last7_clicks=recent_clicks,
                prev7_clicks=prior_clicks,
                drop_percent=drop,
            )
        if row["impressions"] >= threshold["zero_click_min_impressions"] and row["clicks"] == 0:
            _add_candidate(
                candidates,
                "zero_clicks",
                f"{threshold['zero_click_min_impressions']}+ impressions, no clicks",
            )
        previous_clicks = before.get(page, {}).get("clicks", 0)
        if previous_clicks >= threshold["trend_min_previous_clicks"] and row[
            "clicks"
        ] < previous_clicks * (1 - _decimal(threshold["trend_drop_fraction"])):
            drop = (Decimal(1) - Decimal(row["clicks"]) / previous_clicks) * 100
            _add_candidate(
                candidates,
                "trend",
                f"clicks down {metrics.public(drop, 'drop_percent'):g}% vs previous 28 days",
                previous_clicks=previous_clicks,
                drop_percent=drop,
            )
        if candidates:
            for candidate in candidates:
                candidate.update(
                    row,
                    position_band=band,
                    median_ctr_for_band=benchmark,
                    impressions_lost=lost
                    if candidate["check"] in {"low_ctr", "zero_clicks", "trend"}
                    else Decimal(0),
                )
            flags.append(
                max(
                    candidates,
                    key=lambda flag: (
                        flag["impressions_lost"],
                        threshold["flag_priority"][flag["check"]],
                    ),
                )
            )
    return sorted(
        flags, key=lambda flag: (-flag["impressions_lost"], -flag["impressions"], flag["page"])
    )


def query_candidates(db: Session, domain: str, window: metrics.Window) -> list[dict]:
    threshold = ANALYSIS_THRESHOLDS
    return [
        {**row, "reason": "position 8–20, close to page 1"}
        for row in metrics.gsc_queries(
            db,
            domain,
            window,
            limit=threshold["query_limit"],
            min_impressions=threshold["query_min_impressions"],
            position_range=(threshold["query_min_position"], threshold["query_max_position"]),
        )
    ]


def source_health(
    db: Session, domain: str, today: date, settings: Settings
) -> tuple[dict, list[str]]:
    status = metrics.sync_status(db, domain)
    warnings = []
    result = {}
    for source, log in status.items():
        checkpoint = log["last_loaded_date"] if log else None
        stale = checkpoint is None or (today - checkpoint).days > (
            settings.sync_lag_days + ANALYSIS_THRESHOLDS["stale_extra_days"]
        )
        if checkpoint is None:
            warnings.append(f"{source.upper()}: no successful sync checkpoint")
        elif stale:
            warnings.append(f"{source.upper()}: stale sync; last loaded {checkpoint.isoformat()}")
        if log and log["status"] == "error":
            warnings.append(
                f"{source.upper()}: last sync failed: {log['error'] or 'unknown error'}"
            )
        result[source] = {"log": log, "stale": stale}
    return result, warnings


def build_report(
    db: Session,
    site: Site,
    *,
    settings: Settings | None = None,
    as_of: date | None = None,
) -> dict:
    settings = settings or get_settings()
    today = as_of or today_in(settings.sync_timezone)
    end = today - timedelta(days=settings.sync_lag_days)
    current = metrics.Window(end - timedelta(days=27), end)
    last7 = metrics.Window(end - timedelta(days=6), end)
    windows = {
        "current": current,
        "previous": current.previous(),
        "last7": last7,
        "prev7": last7.previous(),
    }
    pages = {name: metrics.gsc_pages(db, site.domain, window) for name, window in windows.items()}
    mobile = metrics.gsc_pages(db, site.domain, current, "MOBILE")
    desktop = metrics.gsc_pages(db, site.domain, current, "DESKTOP")
    flags = find_page_flags(
        pages["current"], pages["previous"], pages["last7"], pages["prev7"], mobile, desktop
    )
    status, warnings = source_health(db, site.domain, today, settings)
    return metrics.public(
        {
            "site": {"slug": site.slug, "domain": site.domain, "display_name": site.display_name},
            "report_date": today,
            "generated_at": datetime.now(ZoneInfo(settings.sync_timezone)),
            "windows": {
                name: {"start": window.start, "end": window.end} for name, window in windows.items()
            },
            "sync_status": status,
            "warnings": warnings,
            "totals": {
                name: metrics.period_totals(db, site.domain, windows[name])
                for name in ["current", "previous"]
            },
            "flagged_pages_count": len(flags),
            "top_pages": flags[: ANALYSIS_THRESHOLDS["page_limit"]],
            "device_split": {
                device: metrics.gsc_totals(db, site.domain, current, device)
                for device in ["MOBILE", "DESKTOP"]
            },
            "query_candidates": query_candidates(db, site.domain, current),
            "data_notes": DATA_NOTES,
        }
    )


def _text(value) -> str:
    return str(value).replace("\n", " ").replace("\r", " ").replace("|", "\\|").replace("`", "\\`")


def render_markdown(report: dict) -> str:
    site = report["site"]
    lines = [
        f"# Weekly SEO review: {_text(site['display_name'])}",
        "",
        f"Site: `{_text(site['slug'])}` · `{_text(site['domain'])}`",
        "",
        f"Report date: {report['report_date']} · Generated: {report['generated_at']}",
        "",
        "## Windows",
        "",
    ]
    for name, window in report["windows"].items():
        lines.append(f"- {name}: {window['start']} to {window['end']}")
    lines.extend(
        [
            "",
            "## Sync status",
            "",
            "| Source | Last loaded | Last run | Status | Rows loaded | Error | Stale |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for source, health in report["sync_status"].items():
        log = health["log"] or {}
        values = [
            source.upper(),
            log.get("last_loaded_date"),
            log.get("last_run_at"),
            log.get("status"),
            log.get("rows_loaded"),
            log.get("error"),
            health["stale"],
        ]
        lines.append(
            "| " + " | ".join(_text(value) if value is not None else "—" for value in values) + " |"
        )
    for warning in report["warnings"]:
        lines.append(f"- Warning: {_text(warning)}")
    lines.extend(["", "## Totals", "", "| Metric | Current | Previous |", "| --- | ---: | ---: |"])
    for source, fields in [
        ("gsc", ["clicks", "impressions", "ctr", "avg_position"]),
        ("ga4", ["sessions", "total_users", "conversions"]),
    ]:
        for field in fields:
            values = [
                (report["totals"][period][source] or {}).get(field)
                for period in ["current", "previous"]
            ]
            lines.append(
                f"| {source.upper()} {field} | "
                + " | ".join(str(value) if value is not None else "—" for value in values)
                + " |"
            )
    lines.extend(
        [
            "",
            "## Flagged pages",
            "",
            f"Showing {len(report['top_pages'])} of {report['flagged_pages_count']} flagged pages.",
        ]
    )
    for flag in report["top_pages"]:
        lines.extend(
            [
                "",
                f"- `{_text(flag['page'])}`: {_text(flag['reason'])}",
                "  "
                + "; ".join(
                    f"{key}: {_text(value)}"
                    for key, value in flag.items()
                    if key not in {"page", "reason"}
                ),
            ]
        )
    lines.extend(["", "## Device split", ""])
    for device, values in report["device_split"].items():
        detail = (
            "; ".join(f"{key}: {value}" for key, value in values.items()) if values else "no data"
        )
        lines.append(f"- {device}: {detail}")
    lines.extend(["", "## Query candidates", ""])
    if not report["query_candidates"]:
        lines.append("No query candidates.")
    for query in report["query_candidates"]:
        lines.extend(
            [
                f"- `{_text(query['query'])}` → `{_text(query['top_page'])}`: "
                f"{_text(query['reason'])}",
                "  "
                + "; ".join(
                    f"{key}: {_text(value)}"
                    for key, value in query.items()
                    if key not in {"query", "top_page", "reason"}
                ),
            ]
        )
    lines.extend(["", "## Data notes", "", *[f"- {note}" for note in report["data_notes"]]])
    return "\n".join(lines) + "\n"


def write_report(report: dict, reports_dir: Path) -> tuple[Path, Path]:
    root = reports_dir.resolve()
    directory = (root / report["site"]["slug"]).resolve()
    if directory.parent != root:
        raise ValueError("Site slug must name a direct child of REPORTS_DIR")
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / report["report_date"]
    json_path, md_path = base.with_suffix(".json"), base.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
