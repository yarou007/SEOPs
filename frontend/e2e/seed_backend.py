"""Idempotent synthetic browser fixtures. Only databases ending in _smoke are accepted."""

import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ.setdefault("SEED_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "admin-smoke-test-password")
os.environ.setdefault("SEED_VIEWER_EMAIL", "viewer@example.com")
os.environ.setdefault("SEED_VIEWER_PASSWORD", "viewer-smoke-test-password")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.analysis.weekly import build_report, write_report  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.metrics import default_end  # noqa: E402
from app.models import Ga4Daily, Ga4SyncLog, GscDaily, GscSyncLog, Site  # noqa: E402
from app.sync.common import upsert_rows  # noqa: E402
from scripts.seed import seed  # noqa: E402


def main():
    settings = get_settings()
    if not (make_url(settings.database_url).database or "").endswith("_smoke"):
        raise ValueError(
            "Browser fixtures require a disposable database with a name ending in _smoke"
        )
    seed()
    end = default_end(settings)
    paths = ["", "emergency-locksmith/", "lock-repair/", "car-lockout/", "rekeying/", "contact/"]
    paths += [f"services/service-{i}/" for i in range(1, 30)]
    gsc, ga4 = [], []
    domain = "arlington247lockrepair.com"
    for day_index in range(56):
        day = end - timedelta(days=55 - day_index)
        current = day_index >= 28
        for index, path in enumerate(paths):
            impressions = max(25, 520 - index * 11 + (day_index % 7) * 13)
            for device in ["MOBILE", "DESKTOP"]:
                count = impressions if device == "MOBILE" else impressions // 2
                clicks = max(1, count // 18 + (day_index % 5) - 2)
                if index == 2 and current:
                    clicks = 0 if device == "MOBILE" else 1
                if index == 4 and current:
                    clicks = 1
                if index == 5 and current:
                    clicks = 0
                position = Decimal("3.2") if index == 0 else Decimal(str(4 + index % 16))
                gsc.append(
                    {
                        "site": domain,
                        "data_date": day,
                        "page": f"https://{domain}/{path}",
                        "query": "arlington locksmith"
                        if index == 0
                        else path.replace("/", " ").strip(),
                        "device": device,
                        "country": "all",
                        "clicks": clicks,
                        "impressions": count,
                        "ctr": Decimal(clicks) / count,
                        "position": position,
                    }
                )
            sessions = max(3, 90 - index * 2 + day_index % 9 * 3)
            ga4.append(
                {
                    "site": domain,
                    "data_date": day,
                    "page_path": f"/{path}",
                    "sessions": sessions,
                    "total_users": sessions * 3 // 4,
                    "conversions": sessions // 20,
                    "engagement_rate": Decimal("0.55") + Decimal(index % 4) / 10,
                }
            )
        for bucket in ["(not set)", "(other)"]:
            ga4.append(
                {
                    "site": domain,
                    "data_date": day,
                    "page_path": bucket,
                    "sessions": 2,
                    "total_users": 1,
                    "conversions": 0,
                    "engagement_rate": Decimal("0.5"),
                }
            )
    with SessionLocal.begin() as db:
        site = db.scalar(select(Site).where(Site.slug == "arlington"))
        site.gsc_property = f"sc-domain:{domain}"
        site.ga4_property_id = "123456789"
        for rows, model, metric_fields in [
            (gsc, GscDaily, ("clicks", "impressions", "ctr", "position")),
            (ga4, Ga4Daily, ("sessions", "total_users", "conversions", "engagement_rate")),
        ]:
            for offset in range(0, len(rows), 1000):
                upsert_rows(db, model, rows[offset : offset + 1000], metric_fields)
        for model, count in [(GscSyncLog, len(gsc)), (Ga4SyncLog, len(ga4))]:
            values = {
                "site": domain,
                "last_loaded_date": end,
                "last_run_at": datetime.now(UTC),
                "status": "ok",
                "rows_loaded": count,
                "error": None,
            }
            db.execute(
                insert(model)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[model.site],
                    set_={key: value for key, value in values.items() if key != "site"},
                )
            )
    with SessionLocal() as db:
        site = db.scalar(select(Site).where(Site.slug == "arlington"))
        write_report(build_report(db, site), settings.reports_dir)
    print(
        f"Browser fixture ready: {len(gsc)} GSC rows, {len(ga4)} GA4 rows; viewer linked to Arlington only."
    )


if __name__ == "__main__":
    main()
