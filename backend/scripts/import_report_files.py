"""Import weekly report files (<dir>/<slug>/<YYYY-MM-DD>.json) into the weekly_reports table.

Usage: python -m scripts.import_report_files [DIRECTORY ...]
Defaults to REPORTS_DIR. Safe to rerun: a report for the same site and day is replaced.
"""

import json
import logging
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.analysis.weekly import save_report
from app.config import get_settings
from app.db import SessionLocal
from app.models import Site

logger = logging.getLogger("import_report_files")


def import_directory(root: Path) -> tuple[int, int]:
    imported = skipped = 0
    with SessionLocal() as db:
        sites = {site.slug: site for site in db.scalars(select(Site))}
        for path in sorted(root.glob("*/????-??-??.json")):
            slug = path.parent.name
            try:
                date.fromisoformat(path.stem)
                report = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(report, dict) or report.get("site", {}).get("slug") != slug:
                    raise ValueError("report site does not match its folder")
                if report.get("report_date") != path.stem:
                    raise ValueError("report date does not match its file name")
                site = sites.get(slug)
                if site is None:
                    raise ValueError(f"no site with slug {slug!r}")
                # Reports are linked by the site's current domain.
                report["site"]["domain"] = site.domain
                save_report(db, report)
                imported += 1
                logger.info("imported %s", path)
            except (OSError, ValueError, AttributeError) as exc:
                db.rollback()
                skipped += 1
                logger.warning("skipped %s: %s", path, exc)
    return imported, skipped


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    roots = [Path(arg) for arg in argv] or [get_settings().reports_dir]
    total_imported = total_skipped = 0
    for root in roots:
        imported, skipped = import_directory(root.resolve())
        total_imported += imported
        total_skipped += skipped
    logger.info("done: %d imported, %d skipped", total_imported, total_skipped)
    return int(total_skipped > 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
