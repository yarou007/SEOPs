"""GA4 row-count pagination and mapping on the shared resumable sync runner."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Ga4Daily, Ga4SyncLog, Site
from app.sync.common import (
    round_metric,
    run_sync,
    today_in,
    upsert_batches,
    upsert_rows,
    validate_data_date,
)
from app.sync.ga4_client import PAGE_SIZE, Ga4QueryClient, Ga4Row


def _map_row(domain: str, row: Ga4Row, start_date: date, end_date: date) -> dict:
    data_date = datetime.strptime(row["date"], "%Y%m%d").date()
    validate_data_date(data_date, start_date, end_date, "GA4")
    return {
        "site": domain,
        "data_date": data_date,
        "page_path": row["pagePath"],
        "sessions": int(Decimal(row["sessions"])),
        "total_users": int(Decimal(row["totalUsers"])),
        "conversions": int(Decimal(row["conversions"])),
        "engagement_rate": round_metric(row["engagementRate"]),
        "pulled_at": func.now(),
    }


def _upsert_rows(db: Session, rows: list[dict]) -> None:
    upsert_rows(db, Ga4Daily, rows, ("sessions", "total_users", "conversions", "engagement_rate"))


def sync_site(
    site: Site,
    client: Ga4QueryClient,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    settings: Settings | None = None,
) -> int:
    def pull_chunk(db: Session, property_id: str, start: date, end: date) -> int:
        offset = 0
        expected_count = None
        while True:
            rows, row_count = client.run_report(property_id, start, end, offset, PAGE_SIZE)
            if expected_count is None:
                expected_count = row_count
            if row_count != expected_count:
                raise ValueError("GA4 row_count changed while paging")
            if row_count < 0 or offset + len(rows) > row_count or len(rows) > PAGE_SIZE:
                raise ValueError("GA4 returned an invalid row_count or page size")
            if not rows and offset < row_count:
                raise ValueError("GA4 returned an empty page before row_count was reached")
            upsert_batches(
                db, rows, lambda row: _map_row(site.domain, row, start, end), _upsert_rows
            )
            offset += len(rows)
            if offset == row_count:
                return offset

    return run_sync(
        site,
        source="GA4",
        property_name="ga4_property_id",
        log_model=Ga4SyncLog,
        pull_chunk=pull_chunk,
        from_date=from_date,
        to_date=to_date,
        settings=settings,
        today=today_in,
    )
