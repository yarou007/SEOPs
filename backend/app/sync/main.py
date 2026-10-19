import argparse
import logging
import os
from datetime import date

logger = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SEOPs data synchronization")
    commands = parser.add_subparsers(dest="command", required=True)
    for command, description in [
        ("gsc", "Sync finalized Google Search Console performance data"),
        ("ga4", "Sync Google Analytics 4 performance data"),
    ]:
        sync = commands.add_parser(command, help=description)
        sites = sync.add_mutually_exclusive_group(required=True)
        sites.add_argument("--site", metavar="SLUG", help="Sync one site by slug")
        sites.add_argument("--all", action="store_true", help="Sync every active site")
        sync.add_argument("--from", dest="from_date", type=date.fromisoformat, metavar="YYYY-MM-DD")
        sync.add_argument("--to", dest="to_date", type=date.fromisoformat, metavar="YYYY-MM-DD")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.from_date and args.to_date and args.from_date > args.to_date:
        parser.error("--from must be on or before --to")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Keep imports lazy so --help needs neither app settings nor a database.
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import Site

    settings = get_settings()
    fake_mode = os.environ.get("SYNC_FAKE_CLIENT") == "1"
    if fake_mode:
        logger.warning("SYNC_FAKE_CLIENT=1: test-only synthetic data will be written to Postgres")
    if args.command == "gsc":
        from app.sync.gsc import sync_site
        from app.sync.gsc_client import FakeGscClient, GscClient

        client = FakeGscClient() if fake_mode else GscClient(settings.gsc_service_account_file)
    else:
        from app.sync.ga4 import sync_site
        from app.sync.ga4_client import FakeGa4Client, Ga4Client

        client = FakeGa4Client() if fake_mode else Ga4Client(settings.ga4_service_account_file)
    with SessionLocal() as db:
        statement = select(Site).order_by(Site.slug)
        if args.all:
            statement = statement.where(Site.active.is_(True))
        else:
            statement = statement.where(Site.slug == args.site)
        sites = list(db.scalars(statement))
    if args.site and not sites:
        logger.error("Site not found: %s", args.site)
        return 1
    failed = False
    for site in sites:
        try:
            sync_site(
                site, client, from_date=args.from_date, to_date=args.to_date, settings=settings
            )
        except Exception:
            # sync_site records the short error; do not dump credentials or response bodies here.
            logger.error(
                "%s sync failed for %s; continuing with remaining sites",
                args.command.upper(),
                site.slug,
            )
            failed = True
    return int(failed)
