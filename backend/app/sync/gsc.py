"""Resumable GSC ingestion with atomic, at-most-seven-day checkpoints."""

import logging
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import GscDaily, GscSyncLog, Site
from app.sync.gsc_client import PAGE_SIZE, GscQueryClient, GscRow

logger = logging.getLogger(__name__)
DAY = timedelta(days=1)


def today_in(timezone: str) -> date:
    return datetime.now(ZoneInfo(timezone)).date()


def _write_log(
    db: Session,
    domain: str,
    *,
    status: str,
    rows_loaded: int,
    error: str | None = None,
    last_loaded_date: date | None = None,
) -> None:
    values = {
        "site": domain,
        "last_run_at": func.now(),
        "status": status,
        "rows_loaded": rows_loaded,
        "error": error,
    }
    updates = {key: value for key, value in values.items() if key != "site"}
    if last_loaded_date is not None:
        values["last_loaded_date"] = last_loaded_date
        # An explicit historical replay must not rewind the resume checkpoint.
        updates["last_loaded_date"] = func.greatest(GscSyncLog.last_loaded_date, last_loaded_date)
    db.execute(
        insert(GscSyncLog)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[GscSyncLog.site],
            set_=updates,
        )
    )


def _map_row(domain: str, row: GscRow, start_date: date, end_date: date) -> dict:
    keys = row["keys"]
    if len(keys) != 4:
        raise ValueError("Expected GSC row keys [date, page, query, device]")
    data_date = date.fromisoformat(keys[0])
    if not start_date <= data_date <= end_date:
        raise ValueError("GSC returned a date outside the requested chunk")
    return {
        "site": domain,
        "data_date": data_date,
        "page": keys[1],
        "query": keys[2],
        "device": keys[3].upper(),
        "country": "all",
        "clicks": int(row["clicks"]),
        "impressions": int(row["impressions"]),
        "ctr": Decimal(str(row["ctr"])).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "position": Decimal(str(row["position"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "pulled_at": func.now(),
    }


def _upsert_rows(db: Session, rows: list[dict]) -> None:
    statement = insert(GscDaily).values(rows)
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[
                GscDaily.site,
                GscDaily.data_date,
                GscDaily.page,
                GscDaily.query,
                GscDaily.device,
                GscDaily.country,
            ],
            set_={
                "clicks": statement.excluded.clicks,
                "impressions": statement.excluded.impressions,
                "ctr": statement.excluded.ctr,
                "position": statement.excluded.position,
                "pulled_at": func.now(),
            },
        )
    )


def sync_site(
    site: Site,
    client: GscQueryClient,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    settings: Settings | None = None,
) -> int:
    """Commit whole chunks, record failures independently, and return committed row count."""
    settings = settings or get_settings()
    total_rows = 0
    try:
        if not site.gsc_property:
            raise ValueError("gsc_property not set")
        end_date = to_date or today_in(settings.sync_timezone) - timedelta(
            days=settings.sync_lag_days
        )
        with SessionLocal() as db:
            log = db.get(GscSyncLog, site.domain)
            checkpoint = log.last_loaded_date if log else None
        start_date = from_date or (
            checkpoint + DAY if checkpoint else end_date - timedelta(days=487)
        )
        if start_date > end_date:
            with SessionLocal.begin() as db:
                _write_log(db, site.domain, status="ok", rows_loaded=0)
            logger.info("GSC %s: already up to date (0 rows)", site.slug)
            return 0

        while start_date <= end_date:
            chunk_end = min(start_date + timedelta(days=6), end_date)
            chunk_rows = 0
            with SessionLocal.begin() as db:
                start_row = 0
                while True:
                    page = client.query(
                        site.gsc_property, start_date, chunk_end, start_row, PAGE_SIZE
                    )
                    for offset in range(0, len(page), 1000):
                        batch = [
                            _map_row(site.domain, row, start_date, chunk_end)
                            for row in page[offset : offset + 1000]
                        ]
                        _upsert_rows(db, batch)
                    chunk_rows += len(page)
                    if len(page) < PAGE_SIZE:
                        break
                    start_row += PAGE_SIZE
                _write_log(
                    db,
                    site.domain,
                    status="ok",
                    rows_loaded=total_rows + chunk_rows,
                    last_loaded_date=chunk_end,
                )
            total_rows += chunk_rows
            logger.info(
                "GSC %s: %s through %s committed (%d rows; run total %d)",
                site.slug,
                start_date,
                chunk_end,
                chunk_rows,
                total_rows,
            )
            start_date = chunk_end + DAY
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"[:500]
        if isinstance(exc, ValueError) and str(exc) == "gsc_property not set":
            message = "gsc_property not set"
        with SessionLocal.begin() as db:
            _write_log(db, site.domain, status="error", rows_loaded=total_rows, error=message)
        logger.error("GSC %s: %s", site.slug, message)
        raise
    return total_rows
