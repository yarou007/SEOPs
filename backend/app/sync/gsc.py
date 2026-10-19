"""GSC pagination and mapping on the shared resumable sync runner."""

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import GscDaily, GscSyncLog, Site
from app.sync.common import (
    round_metric,
    run_sync,
    today_in,
    upsert_batches,
    upsert_rows,
    validate_data_date,
)
from app.sync.gsc_client import PAGE_SIZE, GscQueryClient, GscRow


def _map_row(domain: str, row: GscRow, start_date: date, end_date: date) -> dict:
    keys = row["keys"]
    if len(keys) != 4:
        raise ValueError("Expected GSC row keys [date, page, query, device]")
    data_date = date.fromisoformat(keys[0])
    validate_data_date(data_date, start_date, end_date, "GSC")
    return {
        "site": domain,
        "data_date": data_date,
        "page": keys[1],
        "query": keys[2],
        "device": keys[3].upper(),
        "country": "all",
        "clicks": int(row["clicks"]),
        "impressions": int(row["impressions"]),
        "ctr": round_metric(row["ctr"]),
        "position": round_metric(row["position"], "0.01"),
        "pulled_at": func.now(),
    }


def _upsert_rows(db: Session, rows: list[dict]) -> None:
    upsert_rows(db, GscDaily, rows, ("clicks", "impressions", "ctr", "position"))


def sync_site(
    site: Site,
    client: GscQueryClient,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    settings: Settings | None = None,
) -> int:
    def pull_chunk(db: Session, site_property: str, start: date, end: date) -> int:
        start_row = 0
        count = 0
        while True:
            page = client.query(site_property, start, end, start_row, PAGE_SIZE)
            upsert_batches(
                db, page, lambda row: _map_row(site.domain, row, start, end), _upsert_rows
            )
            count += len(page)
            if len(page) < PAGE_SIZE:
                return count
            start_row += PAGE_SIZE

    return run_sync(
        site,
        source="GSC",
        property_name="gsc_property",
        log_model=GscSyncLog,
        pull_chunk=pull_chunk,
        from_date=from_date,
        to_date=to_date,
        settings=settings,
        today=today_in,
    )
