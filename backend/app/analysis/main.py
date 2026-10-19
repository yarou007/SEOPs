import argparse
import logging

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SEOPs local-data analysis")
    commands = parser.add_subparsers(dest="command", required=True)
    weekly = commands.add_parser("weekly", help="Write a weekly SEO report as JSON and Markdown")
    sites = weekly.add_mutually_exclusive_group(required=True)
    sites.add_argument("--site", metavar="SLUG")
    sites.add_argument("--all", action="store_true", help="Analyze all active sites")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from sqlalchemy import select

    from app.analysis.weekly import build_report, write_report
    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import Site

    settings = get_settings()
    with SessionLocal() as db:
        statement = select(Site).order_by(Site.slug)
        statement = (
            statement.where(Site.active.is_(True))
            if args.all
            else statement.where(Site.slug == args.site)
        )
        selected = list(db.scalars(statement))
    if args.site and not selected:
        logger.error("Site not found: %s", args.site)
        return 1
    failed = False
    for site in selected:
        try:
            with SessionLocal() as db:
                report = build_report(db, site, settings=settings)
            json_path, md_path = write_report(report, settings.reports_dir)
            logger.info(
                "%s: %d flagged pages; wrote %s and %s",
                site.slug,
                report["flagged_pages_count"],
                json_path,
                md_path,
            )
            for warning in report["warnings"]:
                logger.warning("%s: %s", site.slug, warning)
        except Exception as exc:
            logger.error("%s: analysis failed: %s", site.slug, str(exc)[:500])
            failed = True
    return int(failed)
