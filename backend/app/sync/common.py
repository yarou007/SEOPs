"""Shared checkpoint, transaction, batching, and mapping helpers for data syncs."""

import logging
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import Ga4Daily, Ga4SyncLog, GscDaily, GscSyncLog, Site

logger = logging.getLogger(__name__)
type DailyModel = type[GscDaily] | type[Ga4Daily]
type LogModel = type[GscSyncLog] | type[Ga4SyncLog]
type PullChunk = Callable[[Session, str, date, date], int]


def today_in(timezone: str) -> date:
    return datetime.now(ZoneInfo(timezone)).date()


def date_chunks(start: date, end: date) -> Iterator[tuple[date, date]]:
    while start <= end:
        chunk_end = min(start + timedelta(days=6), end)
        yield start, chunk_end
        start = chunk_end + timedelta(days=1)


def validate_data_date(data_date: date, start: date, end: date, source: str) -> None:
    if not start <= data_date <= end:
        raise ValueError(f"{source} returned a date outside the requested chunk")


def round_metric(value: str | float | int, quantum: str = "0.0001") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(quantum), rounding=ROUND_HALF_UP)


def upsert_rows(db: Session, model: DailyModel, rows: list[dict], metrics: tuple[str, ...]) -> None:
    statement = insert(model).values(rows)
    db.execute(
        statement.on_conflict_do_update(
            index_elements=list(model.__table__.primary_key.columns),
            set_={
                **{name: getattr(statement.excluded, name) for name in metrics},
                "pulled_at": func.now(),
            },
        )
    )


def upsert_batches[Row](
    db: Session,
    rows: list[Row],
    mapper: Callable[[Row], dict],
    upsert: Callable[[Session, list[dict]], None],
) -> None:
    for offset in range(0, len(rows), 1000):
        upsert(db, [mapper(row) for row in rows[offset : offset + 1000]])


def _write_log(
    db: Session,
    model: LogModel,
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
        # Historical replays must not rewind an existing resume checkpoint.
        updates["last_loaded_date"] = func.greatest(model.last_loaded_date, last_loaded_date)
    db.execute(
        insert(model)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[model.site],
            set_=updates,
        )
    )


def run_sync(
    site: Site,
    *,
    source: str,
    property_name: str,
    log_model: LogModel,
    pull_chunk: PullChunk,
    from_date: date | None = None,
    to_date: date | None = None,
    settings: Settings | None = None,
    today: Callable[[str], date] = today_in,
) -> int:
    """Commit whole chunks with their checkpoints; independently record failed chunks."""
    settings = settings or get_settings()
    total_rows = 0
    missing_property = f"{property_name} not set"
    try:
        site_property = getattr(site, property_name)
        if not site_property:
            raise ValueError(missing_property)
        end_date = to_date or today(settings.sync_timezone) - timedelta(days=settings.sync_lag_days)
        with SessionLocal() as db:
            log = db.get(log_model, site.domain)
            checkpoint = log.last_loaded_date if log else None
        start_date = from_date or (
            checkpoint + timedelta(days=1) if checkpoint else end_date - timedelta(days=487)
        )
        if start_date > end_date:
            with SessionLocal.begin() as db:
                _write_log(db, log_model, site.domain, status="ok", rows_loaded=0)
            logger.info("%s %s: already up to date (0 rows)", source, site.slug)
            return 0

        for chunk_start, chunk_end in date_chunks(start_date, end_date):
            with SessionLocal.begin() as db:
                chunk_rows = pull_chunk(db, site_property, chunk_start, chunk_end)
                _write_log(
                    db,
                    log_model,
                    site.domain,
                    status="ok",
                    rows_loaded=total_rows + chunk_rows,
                    last_loaded_date=chunk_end,
                )
            total_rows += chunk_rows
            logger.info(
                "%s %s: %s through %s committed (%d rows; run total %d)",
                source,
                site.slug,
                chunk_start,
                chunk_end,
                chunk_rows,
                total_rows,
            )
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"[:500]
        if isinstance(exc, ValueError) and str(exc) == missing_property:
            message = missing_property
        with SessionLocal.begin() as db:
            _write_log(
                db, log_model, site.domain, status="error", rows_loaded=total_rows, error=message
            )
        logger.error("%s %s: %s", source, site.slug, message)
        raise
    return total_rows
