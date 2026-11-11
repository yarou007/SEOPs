import argparse
import logging

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SEOPs local-data analysis")
    commands = parser.add_subparsers(dest="command", required=True)
    weekly = commands.add_parser(
        "weekly", help="Save a weekly SEO report to the database (plus JSON and Markdown copies)"
    )
    sites = weekly.add_mutually_exclusive_group(required=True)
    sites.add_argument("--site", metavar="SLUG")
    sites.add_argument("--all", action="store_true", help="Analyze all active sites")
    weekly.add_argument(
        "--with-ai",
        action="store_true",
        help="Also generate the AI analysis (uses the daily AI request budget)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from sqlalchemy import select

    from app.analysis.weekly import build_report, save_report, write_report
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
                save_report(db, report)
            json_path, md_path = write_report(report, settings.reports_dir)
            logger.info(
                "%s: %d flagged pages; saved to the database and wrote %s and %s",
                site.slug,
                report["flagged_pages_count"],
                json_path,
                md_path,
            )
            for warning in report["warnings"]:
                logger.warning("%s: %s", site.slug, warning)
            if args.with_ai:
                from app.insights.llm import LlmError, OpenRouterClient
                from app.insights.service import generate_weekly

                try:
                    with SessionLocal() as db:
                        stored = generate_weekly(db, site, OpenRouterClient(settings), settings)
                    logger.info("%s: AI analysis saved for %s", site.slug, stored.report_date)
                except LlmError as error:
                    logger.error("%s: AI analysis skipped: %s", site.slug, error.message)
                    failed = True
        except Exception as exc:
            logger.error("%s: analysis failed: %s", site.slug, str(exc)[:500])
            failed = True
    return int(failed)
