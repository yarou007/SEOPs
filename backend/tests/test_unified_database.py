"""One database: every row belongs to a site, and each site has its own schema of views."""

from datetime import date

import pytest
from conftest import SCHEMA, run_cli
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.analysis.csv_sources import import_csv
from app.models import AhrefsCsvRow, AxisSnapshot, Ga4Daily, GscDaily, Site, WeeklyReport

DOMAIN = "arlington247lockrepair.com"
# PostgreSQL names are at most 63 characters; long test prefixes get truncated.
SITE_SCHEMA = f"{SCHEMA}__arlington247lockrepair_com"[:63]


def gsc(page="", query="", device="", country="all", clicks=1, impressions=10, site=DOMAIN):
    return GscDaily(
        site=site,
        data_date=date(2026, 10, 1),
        page=page,
        query=query,
        device=device,
        country=country,
        clicks=clicks,
        impressions=impressions,
    )


def site_schemas(db) -> set[str]:
    return set(
        db.scalars(
            text("SELECT nspname FROM pg_namespace WHERE starts_with(nspname, :prefix)"),
            {"prefix": f"{SCHEMA}__"},
        )
    )


def test_data_for_unknown_site_is_rejected(db, seeded):
    db.add(gsc(site="not-a-site.example"))
    with pytest.raises(IntegrityError, match="fk_gsc_daily_site_sites"):
        db.commit()


def test_site_with_data_cannot_be_deleted(db, seeded):
    db.add(gsc())
    db.commit()
    db.delete(db.scalar(select(Site).where(Site.domain == DOMAIN)))
    with pytest.raises(IntegrityError):
        db.commit()


def test_each_site_gets_its_own_schema_of_views(db, seeded):
    assert SITE_SCHEMA in site_schemas(db)
    assert len(site_schemas(db)) == db.query(Site).count()
    views = set(
        db.scalars(
            text("SELECT table_name FROM information_schema.views WHERE table_schema = :s"),
            {"s": SITE_SCHEMA},
        )
    )
    assert {
        "site_info",
        "daily_totals",
        "pages",
        "queries",
        "devices",
        "countries",
        "ga4_pages",
        "weekly_reports",
        "ahrefs_rows",
        "snapshots",
        "sync_status",
        "ai_insights",
        "ai_conversations",
        "ahrefs_web_analytics",
    } <= views


def test_site_views_split_grains_and_hide_other_sites(db, seeded):
    db.add_all(
        [
            gsc(clicks=5, impressions=50),
            gsc(page="/a", clicks=3, impressions=30),
            gsc(device="MOBILE", clicks=2, impressions=20),
            gsc(country="usa", clicks=4, impressions=40),
            gsc(page="/a", query="locksmith", device="MOBILE", clicks=1, impressions=9),
            gsc(site="TODO-site2.example", clicks=99, impressions=999),
            Ga4Daily(site=DOMAIN, data_date=date(2026, 10, 1), page_path="/a", sessions=7),
        ]
    )
    db.commit()

    def rows(view, columns):
        return db.execute(text(f'SELECT {columns} FROM "{SITE_SCHEMA}".{view}')).all()

    assert rows("daily_totals", "clicks, impressions") == [(5, 50)]
    assert rows("pages", "page, clicks") == [("/a", 3)]
    assert rows("devices", "device, clicks") == [("MOBILE", 2)]
    assert rows("countries", "country, clicks") == [("usa", 4)]
    assert rows("queries", "query, page, device") == [("locksmith", "/a", "MOBILE")]
    assert rows("ga4_pages", "page_path, sessions") == [("/a", 7)]
    assert rows("site_info", "domain") == [(DOMAIN,)]


def test_domain_rename_moves_data_and_schema(db, seeded):
    db.add(gsc())
    db.commit()
    site = db.scalar(select(Site).where(Site.domain == DOMAIN))
    site.domain = "renamed.example"
    db.commit()
    assert db.scalar(select(GscDaily.site)) == "renamed.example"
    assert f"{SCHEMA}__renamed_example" in site_schemas(db)
    assert SITE_SCHEMA not in site_schemas(db)


def test_new_site_gets_schema_and_unrelated_schemas_are_untouched(db, seeded):
    db.execute(text(f'CREATE SCHEMA "{SCHEMA}__keep_me"'))
    db.commit()
    db.add(Site(slug="new", domain="new-site.example", display_name="New"))
    db.commit()
    assert {f"{SCHEMA}__new_site_example", f"{SCHEMA}__keep_me"} <= site_schemas(db)


def test_csv_import_keeps_every_raw_row(db, seeded):
    site = db.scalar(select(Site).where(Site.domain == DOMAIN))
    csv = (
        "URL,Inlinks,HTTP status code,Title\n"
        f"https://{DOMAIN}/,2,200,Home\n"
        f"https://{DOMAIN}/broken,1,404,Gone\n"
    )
    snapshot = import_csv(db, site, "internal-links", csv)
    db.commit()
    rows = db.scalars(select(AhrefsCsvRow).order_by(AhrefsCsvRow.row_number)).all()
    assert [row.row_number for row in rows] == [1, 2]
    assert rows[1].data == {
        "URL": f"https://{DOMAIN}/broken",
        "Inlinks": "1",
        "HTTP status code": "404",
        "Title": "Gone",
    }
    assert {row.snapshot_id for row in rows} == {snapshot.id}
    assert db.execute(text(f'SELECT count(*) FROM "{SITE_SCHEMA}".ahrefs_rows')).scalar() == 2
    db.delete(db.get(AxisSnapshot, snapshot.id))
    db.commit()
    assert db.scalars(select(AhrefsCsvRow)).all() == []


def test_weekly_cli_saves_report_in_database(db, seeded, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    run_cli("app.analysis", "weekly", "--site", "arlington")
    stored = db.scalars(select(WeeklyReport)).all()
    assert len(stored) == 1
    assert stored[0].site == DOMAIN
    assert stored[0].report["site"]["slug"] == "arlington"
    assert stored[0].markdown
    (json_file,) = (tmp_path / "arlington").glob("*.json")
    assert json_file.stem == stored[0].report_date.isoformat()


def test_report_files_import_into_database(db, seeded, tmp_path):
    import json

    from app.analysis.weekly import build_report

    site = db.scalar(select(Site).where(Site.domain == DOMAIN))
    report = build_report(db, site, as_of=date(2026, 10, 22))
    folder = tmp_path / "arlington"
    folder.mkdir()
    (folder / "2026-10-20.json").write_text(json.dumps(report))  # date mismatch
    (folder / f"{report['report_date']}.json").write_text(json.dumps(report))
    (tmp_path / "unknown-site").mkdir()
    (tmp_path / "unknown-site" / "2026-10-22.json").write_text("{}")

    with pytest.raises(Exception) as failure:
        run_cli("scripts.import_report_files", str(tmp_path))
    assert "2 skipped" in failure.value.stderr and "1 imported" in failure.value.stderr
    stored = db.scalars(select(WeeklyReport)).one()
    assert stored.site == DOMAIN
    assert stored.report_date.isoformat() == report["report_date"]


def insight(site=DOMAIN, **extra):
    from app.models import AiInsight

    return AiInsight(
        site=site,
        source="chat",
        title="Low CTR",
        problem="Page ranks but is not clicked",
        evidence=[{"metric": "ctr", "value": "0.16", "period": "28d"}],
        advice="Rewrite the title",
        target_kpi="ctr",
        priority="high",
        model="fake",
        **extra,
    )


def test_ai_insight_requires_known_site(db, seeded):
    db.add(insight(site="nope.example"))
    with pytest.raises(IntegrityError, match="fk_ai_insights_site_sites"):
        db.commit()


def test_ai_insights_view_shows_site_rows(db, seeded):
    db.add_all([insight(), insight(site="TODO-site2.example")])
    db.commit()
    rows = db.execute(text(f'SELECT title, status FROM "{SITE_SCHEMA}".ai_insights')).all()
    assert rows == [("Low CTR", "new")]


def test_ahrefs_web_analytics_view_shows_site_rows(db, seeded):
    from app.analysis.web_analytics import WebAnalyticsFile, import_web_analytics

    channels = (
        '"Channel"\t"Visitors"\t"Bounce rate"\t"Visit duration"\n"Direct"\t"26"\t"0.5"\t"239"\n'
    )
    site = db.scalar(select(Site).where(Site.domain == DOMAIN))
    import_web_analytics(
        db,
        site,
        date(2026, 10, 13),
        date(2026, 11, 11),
        [WebAnalyticsFile(name="Channel.csv", content=channels)],
    )
    db.commit()
    rows = db.execute(
        text(f'SELECT report, item, visitors FROM "{SITE_SCHEMA}".ahrefs_web_analytics')
    ).all()
    assert rows == [("channels", "Direct", 26)]
    others = db.scalars(
        text(
            "SELECT table_schema FROM information_schema.views "
            "WHERE table_name = 'ahrefs_web_analytics' AND starts_with(table_schema, :p)"
        ),
        {"p": f"{SCHEMA}__"},
    ).all()
    assert len(others) == db.query(Site).count()
    for schema in set(others) - {SITE_SCHEMA}:
        assert (
            db.execute(text(f'SELECT count(*) FROM "{schema}".ahrefs_web_analytics')).scalar() == 0
        )
