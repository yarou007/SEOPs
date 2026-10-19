"""Small, single-process background runner for user-triggered real-data imports."""

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID

from pydantic import BaseModel, Field

from app.analysis.weekly import build_report, write_report
from app.config import Settings
from app.db import SessionLocal
from app.models import Site
from app.sync import ga4, gsc
from app.sync.ga4_client import Ga4Client
from app.sync.gsc_client import GscClient


class SyncResult(BaseModel):
    status: str
    rows_loaded: int | None = None
    message: str


class SyncJob(BaseModel):
    running: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None
    results: dict[str, SyncResult] = Field(default_factory=dict)


class SyncJobs:
    """Bound concurrency and prevent duplicate starts within this API process."""

    def __init__(self):
        self.lock = Lock()
        self.jobs: dict[UUID, SyncJob] = {}

    def get(self, site_id: UUID) -> SyncJob:
        with self.lock:
            return deepcopy(self.jobs.get(site_id, SyncJob()))

    def start(self, site_id: UUID) -> SyncJob:
        with self.lock:
            if self.jobs.get(site_id, SyncJob()).running:
                raise ValueError("A sync is already running for this website.")
            if sum(job.running for job in self.jobs.values()) >= 2:
                raise ValueError("Two website syncs are already running. Try again shortly.")
            job = SyncJob(running=True, started_at=datetime.now(UTC))
            self.jobs[site_id] = job
            return deepcopy(job)

    def finish(self, site_id: UUID, results: dict[str, SyncResult]) -> None:
        with self.lock:
            job = self.jobs[site_id]
            job.running = False
            job.finished_at = datetime.now(UTC)
            job.results = results


def run_site_sync(site_id: UUID, jobs: SyncJobs, settings: Settings) -> None:
    results: dict[str, SyncResult] = {}
    try:
        with SessionLocal() as db:
            site = db.get(Site, site_id)
            if site is None:
                raise ValueError("Site no longer exists")
            db.expunge(site)
        # Deliberately instantiate real clients. SYNC_FAKE_CLIENT never affects this route.
        for source, property_name, sync, client in [
            ("gsc", "gsc_property", gsc.sync_site, GscClient(settings.gsc_service_account_file)),
            ("ga4", "ga4_property_id", ga4.sync_site, Ga4Client(settings.ga4_service_account_file)),
        ]:
            if not getattr(site, property_name):
                continue
            try:
                count = sync(site, client, settings=settings)
                results[source] = SyncResult(
                    status="ok", rows_loaded=count, message=f"Imported {count:,} rows from Google."
                )
            except Exception:
                # Existing sync logs retain the bounded diagnostic; keep job responses generic.
                results[source] = SyncResult(
                    status="error",
                    message=(
                        "Import failed. Check Data status and your Google property access, "
                        "then retry."
                    ),
                )
        if any(result.status == "ok" for result in results.values()):
            try:
                with SessionLocal() as db:
                    write_report(build_report(db, site), settings.reports_dir)
                results["report"] = SyncResult(
                    status="ok", message="Weekly report updated from stored data."
                )
            except Exception:
                results["report"] = SyncResult(
                    status="error",
                    message=(
                        "Data was imported, but the weekly report could not be saved. "
                        "Contact your administrator."
                    ),
                )
    except Exception:
        results["sync"] = SyncResult(
            status="error", message="Sync could not complete. Retry or contact your administrator."
        )
    finally:
        jobs.finish(site_id, results)
