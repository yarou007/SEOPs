"""Explicit, bounded collection commands. Never invoked by read endpoints."""

import argparse
import logging
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.analysis.csv_sources import domain, import_csv
from app.analysis.source_clients import (
    AxisGa4Client,
    Ga4AxisClient,
    GscInspectionClient,
    InspectionClient,
)
from app.config import get_settings
from app.db import SessionLocal
from app.metrics import Window, resolve_window
from app.models import AxisSnapshot, GscIndexStatus, Site


def collect_gsc(db: Session, site: Site, client: InspectionClient, urls: list[str]) -> int:
    if not site.gsc_property:
        raise ValueError("gsc_property not set")
    unique = list(dict.fromkeys(url.strip() for url in urls if url.strip()))
    if len(unique) > 200:
        raise ValueError("At most 200 inspection URLs per run")
    if any(domain(url) != site.domain.removeprefix("www.") for url in unique):
        raise ValueError("Inspection URLs must belong to the website")
    sitemaps = client.sitemaps(site.gsc_property)
    submitted_counts = [
        int(content["submitted"])
        for item in sitemaps
        if not item.get("isSitemapsIndex")
        for content in item.get("contents", [])
        if "submitted" in content
    ]
    db.add(
        AxisSnapshot(
            site=site.domain,
            kind="sitemaps",
            data={
                "sitemaps": [
                    {
                        "url": item["path"],
                        "last_submitted": item.get("lastSubmitted"),
                        "last_downloaded": item.get("lastDownloaded"),
                        "is_index": item.get("isSitemapsIndex", False),
                    }
                    for item in sitemaps
                ],
                "submitted": sum(submitted_counts) if submitted_counts else None,
                "inspected_this_run": len(unique),
                "submitted_note": (
                    "API counts may overlap between sitemap files; not unique URL inventory."
                ),
            },
        )
    )
    for url in unique:
        result = client.inspect(site.gsc_property, url)
        last_crawl = result.get("lastCrawlTime")
        values = {
            "site": site.domain,
            "url": url,
            "verdict": result.get("verdict"),
            "coverage_state": result.get("coverageState"),
            "indexing_state": result.get("indexingState"),
            "last_crawl_time": datetime.fromisoformat(last_crawl.replace("Z", "+00:00"))
            if last_crawl
            else None,
            "inspected_at": func.now(),
        }
        db.execute(
            insert(GscIndexStatus)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["site", "url"],
                set_={key: value for key, value in values.items() if key not in {"site", "url"}},
            )
        )
    return len(unique)


def collect_ga4(
    db: Session, site: Site, window: Window, client: AxisGa4Client, event: str | None = None
) -> None:
    if not site.ga4_property_id:
        raise ValueError("ga4_property_id not set")
    rows = client.report(
        site.ga4_property_id,
        window.start,
        window.end,
        ["operatingSystem"],
        ["sessions", "conversions"],
    )
    grouped = {
        name: {"os": name, "sessions": 0, "conversions": 0} for name in ["iOS", "Android", "other"]
    }
    for row in rows:
        group = row["operatingSystem"] if row["operatingSystem"] in {"iOS", "Android"} else "other"
        for key in ["sessions", "conversions"]:
            grouped[group][key] += int(float(row[key]))
    db.add(
        AxisSnapshot(
            site=site.domain,
            kind="os",
            start_date=window.start,
            end_date=window.end,
            data={"rows": list(grouped.values())},
        )
    )
    if event:
        events = client.report(
            site.ga4_property_id,
            window.start,
            window.end,
            ["eventName"],
            ["eventCount"],
            event=event,
        )
        db.add(
            AxisSnapshot(
                site=site.domain,
                kind="calls",
                start_date=window.start,
                end_date=window.end,
                data={
                    "event": event,
                    "count": sum(int(float(row["eventCount"])) for row in events)
                    if events
                    else None,
                },
            )
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect evidence for analysis axes")
    subs = parser.add_subparsers(dest="source", required=True)
    gsc = subs.add_parser("gsc", help="Sitemap metadata and up to 200 supplied URLs")
    gsc.add_argument("--urls-file", type=Path, help="One submitted page URL per line")
    ga4 = subs.add_parser("ga4", help="Site-level OS metrics and configured call event")
    ga4.add_argument("--start", type=date.fromisoformat)
    ga4.add_argument("--end", type=date.fromisoformat)
    csv_parser = subs.add_parser("csv", help="Import a local Ahrefs CSV")
    csv_parser.add_argument("--kind", choices=["internal-links", "backlinks"], required=True)
    csv_parser.add_argument("--file", type=Path, required=True)
    for command in [gsc, ga4, csv_parser]:
        command.add_argument("--site", required=True)
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        with SessionLocal.begin() as db:
            site = db.scalar(select(Site).where(Site.slug == args.site))
            if site is None:
                raise ValueError("Site not found")
            if args.source == "gsc":
                urls = args.urls_file.read_text().splitlines() if args.urls_file else []
                collect_gsc(db, site, GscInspectionClient(settings.gsc_service_account_file), urls)
            elif args.source == "ga4":
                collect_ga4(
                    db,
                    site,
                    resolve_window(args.start, args.end),
                    Ga4AxisClient(settings.ga4_service_account_file),
                    settings.ga4_call_click_events.get(site.slug),
                )
            else:
                raw = args.file.read_bytes()
                # Ahrefs commonly exports UTF-16; also accept UTF-8 BOM.
                text = raw.decode(
                    "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
                )
                import_csv(db, site, args.kind, text)
        print("Axis evidence saved")
        return 0
    except Exception as exc:
        logging.error("Axis collection failed: %s", str(exc)[:500])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
