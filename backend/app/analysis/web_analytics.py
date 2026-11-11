"""Ahrefs Web Analytics "all stats" export: recognise, parse, store and compare imports.

The export is a folder of tab-separated, quoted files (the browser decodes UTF-16 to text).
Files carry no dates, so the import period comes from the user. No external requests.
"""

import csv
import io
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.analysis.csv_sources import _header, domain
from app.models import AhrefsCsvRow, AhrefsWebAnalytics, AxisSnapshot, Site

KIND = "web-analytics"
MAX_BYTES = 2_000_000
MAX_ROWS = 20_000

# Report key -> normalised header row. The header identifies the report, not the file name.
REPORTS: dict[str, tuple[str, ...]] = {
    "top_pages": ("page", "visitors", "views", "bouncerate", "timeonpage"),
    "entry_pages": ("entrypage", "visitors", "entrances", "visitduration"),
    "exit_pages": ("page", "visitors", "exits", "exitrate"),
    "channels": ("channel", "visitors", "bouncerate", "visitduration"),
    "sources": ("source", "visitors", "bouncerate", "visitduration"),
    "devices": ("device", "visitors", "bouncerate", "visitduration"),
    "browsers": ("browser", "visitors", "bouncerate", "visitduration"),
    "os": ("os", "visitors", "bouncerate", "visitduration"),
    "countries": ("country", "visitors"),
    "cities": ("city", "visitors"),
    "continents": ("continent", "visitors"),
    "languages": ("language", "visitors"),
    "utm_campaign": ("utmcampaign", "visitors", "bouncerate", "visitduration"),
    "utm_content": ("utmcontent", "visitors", "bouncerate", "visitduration"),
    "utm_medium": ("utmmedium", "visitors", "bouncerate", "visitduration"),
    "utm_source": ("utmsource", "visitors", "bouncerate", "visitduration"),
    "utm_term": ("utmterm", "visitors", "bouncerate", "visitduration"),
    "events": ("event", "visitors", "count", "conversionrate"),
    "outbound_links": ("eventpropertyhref", "count", "visitors"),
}
PAGE_REPORTS = {"top_pages", "entry_pages", "exit_pages"}
# Normalised column -> (stored key, type). The first column becomes page/href/name.
COLUMNS: dict[str, tuple[str, type]] = {
    "visitors": ("visitors", int),
    "views": ("views", int),
    "entrances": ("entrances", int),
    "exits": ("exits", int),
    "count": ("count", int),
    "exitrate": ("exit_rate", float),
    "bouncerate": ("bounce_rate", float),
    "visitduration": ("visit_duration", float),
    "timeonpage": ("time_on_page", float),
    "conversionrate": ("conversion_rate", float),
}
METRICS = [key for key, _ in COLUMNS.values()]


class WebAnalyticsFile(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    content: str


def _item_key(report: str) -> str:
    if report in PAGE_REPORTS:
        return "page"
    return "href" if report == "outbound_links" else "name"


def _number(value: str, kind: type, file: str) -> int | float:
    text = value.strip().replace(",", "")
    try:
        number = float(text)  # Ahrefs writes "1." and "0." for whole rates.
    except ValueError:
        raise ValueError(f"{file}: “{value[:40]}” is not a number") from None
    if number < 0 or number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{file}: numbers must be zero or more")
    if kind is int:
        if not number.is_integer():
            raise ValueError(f"{file}: “{value[:40]}” is not a whole number")
        return int(number)
    return number


def parse_export(files: list[WebAnalyticsFile], site_domain: str) -> dict:
    """Return {"reports", "raw", "empty", "unknown"}; raise ValueError with a safe message."""
    if sum(len(file.content.encode("utf-8")) for file in files) > MAX_BYTES:
        raise ValueError("The export must be at most 2 MB in total")
    site = site_domain.removeprefix("www.")
    reports: dict[str, list[dict]] = {}
    raw: dict[str, list[dict]] = {}
    empty: list[str] = []
    unknown: list[str] = []
    for file in files:
        rows = list(csv.reader(io.StringIO(file.content.lstrip("﻿")), delimiter="\t"))
        rows = [row for row in rows if any(cell.strip() for cell in row)]
        if not rows:
            empty.append(file.name)
            continue
        header = tuple(_header(cell) for cell in rows[0])
        report = next((key for key, columns in REPORTS.items() if columns == header), None)
        if report is None:
            unknown.append(file.name)
            continue
        if report in reports:
            raise ValueError(f"{file.name}: the same report was included twice")
        body = rows[1:]
        if not body:
            empty.append(file.name)
            continue
        if len(body) > MAX_ROWS:
            raise ValueError(f"{file.name}: a report must have at most 20,000 rows")
        item_key = _item_key(report)
        parsed_rows, raw_rows = [], []
        for row in body:
            if len(row) != len(header):
                raise ValueError(f"{file.name}: every row must have {len(header)} columns")
            item = row[0].strip()
            if report in PAGE_REPORTS and domain(item) != site:
                raise ValueError(f"{file.name}: pages must belong to this website")
            parsed = {item_key: item}
            for column, value in zip(header[1:], row[1:], strict=True):
                key, kind = COLUMNS[column]
                parsed[key] = _number(value, kind, file.name)
            parsed_rows.append(parsed)
            raw_rows.append(dict(zip(rows[0], row, strict=True)))
        reports[report] = parsed_rows
        raw[report] = raw_rows
    if not reports:
        raise ValueError("No Ahrefs Web Analytics report was recognised in these files")
    return {"reports": reports, "raw": raw, "empty": empty, "unknown": unknown}


def _totals(reports: dict[str, list[dict]]) -> dict:
    return {
        "visitors": sum(row["visitors"] for row in reports.get("channels", [])),
        "phone_clicks": sum(
            row["count"]
            for row in reports.get("outbound_links", [])
            if row["href"].lower().startswith("tel:")
        ),
        "pages": len(reports.get("top_pages", [])),
    }


def import_web_analytics(
    db: Session,
    site: Site,
    period_start: date,
    period_end: date,
    files: list[WebAnalyticsFile],
) -> AxisSnapshot:
    if period_end < period_start:
        raise ValueError("The period must end on or after its start")
    parsed = parse_export(files, site.domain)
    # Persist pending site changes first: the snapshot references sites.domain.
    db.flush()
    # Same period again replaces the earlier import; raw and typed rows cascade.
    db.execute(
        delete(AxisSnapshot).where(
            AxisSnapshot.site == site.domain,
            AxisSnapshot.kind == KIND,
            AxisSnapshot.start_date == period_start,
            AxisSnapshot.end_date == period_end,
        )
    )
    snapshot = AxisSnapshot(
        site=site.domain,
        kind=KIND,
        start_date=period_start,
        end_date=period_end,
        data={
            "reports": parsed["reports"],
            "totals": _totals(parsed["reports"]),
            "files": {
                "recognised": len(parsed["reports"]),
                "empty": parsed["empty"],
                "unknown": parsed["unknown"],
            },
        },
    )
    db.add(snapshot)
    db.flush()
    raw_rows, typed_rows = [], []
    for report, rows in parsed["reports"].items():
        item_key = _item_key(report)
        for number, (row, original) in enumerate(
            zip(rows, parsed["raw"][report], strict=True), start=1
        ):
            raw_rows.append(
                {
                    "snapshot_id": snapshot.id,
                    "site": site.domain,
                    "kind": f"{KIND}:{report}",
                    "row_number": number,
                    "data": original,
                }
            )
            typed_rows.append(
                {
                    "snapshot_id": snapshot.id,
                    "site": site.domain,
                    "period_start": period_start,
                    "period_end": period_end,
                    "report": report,
                    "item": row[item_key],
                    **{metric: row.get(metric) for metric in METRICS},
                }
            )
    db.execute(insert(AhrefsCsvRow), raw_rows)
    db.execute(insert(AhrefsWebAnalytics), typed_rows)
    return snapshot


def _imports(db: Session, domain_name: str):
    return select(AxisSnapshot).where(AxisSnapshot.site == domain_name, AxisSnapshot.kind == KIND)


def latest_web_analytics(db: Session, domain_name: str) -> AxisSnapshot | None:
    return db.scalar(_imports(db, domain_name).order_by(AxisSnapshot.collected_at.desc()).limit(1))


def previous_web_analytics(
    db: Session, domain_name: str, before: AxisSnapshot
) -> AxisSnapshot | None:
    """The newest import of an earlier period than `before` (prefer non-overlapping)."""
    earlier = _imports(db, domain_name).where(AxisSnapshot.id != before.id)
    return db.scalar(
        earlier.where(AxisSnapshot.end_date < before.start_date)
        .order_by(AxisSnapshot.end_date.desc(), AxisSnapshot.collected_at.desc())
        .limit(1)
    ) or db.scalar(
        earlier.where(AxisSnapshot.end_date < before.end_date)
        .order_by(AxisSnapshot.end_date.desc(), AxisSnapshot.collected_at.desc())
        .limit(1)
    )


def history(db: Session, domain_name: str) -> list[dict]:
    snapshots = db.scalars(_imports(db, domain_name).order_by(AxisSnapshot.end_date)).all()
    return [
        {
            "period_start": snapshot.start_date,
            "period_end": snapshot.end_date,
            "visitors": snapshot.data["totals"]["visitors"],
            "phone_clicks": snapshot.data["totals"]["phone_clicks"],
        }
        for snapshot in snapshots
    ]


def _change(now: float | None, before: float | None) -> dict:
    percent = (
        round((now - before) / before * 100, 2)
        if now is not None and before not in (None, 0)
        else None
    )
    return {"now": now, "before": before, "change_percent": percent}


def _bounce(reports: dict) -> float | None:
    channels = reports.get("channels", [])
    visitors = sum(row["visitors"] for row in channels)
    if not visitors:
        return None
    return round(sum(row["visitors"] * row["bounce_rate"] for row in channels) / visitors, 4)


def compare_imports(latest: dict, previous: dict | None) -> dict:
    """Changes between two imports' data dicts; {} without a previous import."""
    if previous is None:
        return {}
    before_pages = {
        row["page"]: row["visitors"] for row in previous["reports"].get("top_pages", [])
    }
    return {
        "visitors": _change(latest["totals"]["visitors"], previous["totals"]["visitors"]),
        "phone_clicks": _change(
            latest["totals"]["phone_clicks"], previous["totals"]["phone_clicks"]
        ),
        "bounce_rate": _change(_bounce(latest["reports"]), _bounce(previous["reports"])),
        "pages": [
            {
                "page": row["page"],
                "visitors_now": row["visitors"],
                "visitors_before": before_pages.get(row["page"], 0),
            }
            for row in latest["reports"].get("top_pages", [])[:10]
        ],
    }
