"""Ahrefs Web Analytics "all stats" export: recognise files, parse, store, compare."""

from datetime import date

import pytest
from sqlalchemy import func, select

from app.analysis.web_analytics import (
    WebAnalyticsFile,
    compare_imports,
    import_web_analytics,
    latest_web_analytics,
    parse_export,
    previous_web_analytics,
)
from app.models import AhrefsCsvRow, AhrefsWebAnalytics, AxisSnapshot, Site

DOMAIN = "arlington247lockrepair.com"
SITE = f"https://{DOMAIN}"


def tsv(*rows: list[str]) -> str:
    return "\n".join("\t".join(f'"{cell}"' for cell in row) for row in rows) + "\n"


TOP_PAGES = tsv(
    ["Page", "Visitors", "Views", "Bounce rate", "Time on page"],
    [f"{SITE}/", "10", "16", "0.555555555556", "94"],
    [f"{SITE}/panic-bar", "5", "5", "1.", "18"],
)
EXIT_PAGES = tsv(
    ["Page", "Visitors", "Exits", "Exit rate"],
    [f"{SITE}/", "10", "9", "0.5625"],
)
CHANNELS = tsv(
    ["Channel", "Visitors", "Bounce rate", "Visit duration"],
    ["Direct", "26", "0.846153846154", "239"],
    ["Organic search", "8", "0.5", "309"],
    ["Internal", "1", "0.", "18"],
)
OUTBOUND = tsv(
    ["Event property: href", "Count", "Visitors"],
    ["tel:+17032440559", "3", "2"],
    ["https://maps.google.com/x", "4", "1"],
)


def files(**named: str) -> list[WebAnalyticsFile]:
    return [WebAnalyticsFile(name=f"{name}.csv", content=text) for name, text in named.items()]


def export(**overrides: str) -> list[WebAnalyticsFile]:
    named = {
        "TopPages": TOP_PAGES,
        "ExitPages": EXIT_PAGES,
        "Channel": CHANNELS,
        "OutboundLinkClicks": OUTBOUND,
        **overrides,
    }
    return files(**named)


def test_recognises_reports_by_header():
    parsed = parse_export(
        files(TopPages=TOP_PAGES, ExitPages=EXIT_PAGES, Whatever=CHANNELS), DOMAIN
    )
    assert set(parsed["reports"]) == {"top_pages", "exit_pages", "channels"}
    assert parsed["reports"]["channels"][0]["name"] == "Direct"
    assert parsed["reports"]["top_pages"][0]["page"] == f"{SITE}/"


def test_parses_fraction_rates_and_counts():
    parsed = parse_export(files(TopPages=TOP_PAGES, ExitPages=EXIT_PAGES, Channel=CHANNELS), DOMAIN)
    top = parsed["reports"]["top_pages"]
    assert top[0]["views"] == 16 and isinstance(top[0]["views"], int)
    assert top[1]["bounce_rate"] == 1.0
    assert parsed["reports"]["channels"][2]["bounce_rate"] == 0.0
    assert parsed["reports"]["exit_pages"][0]["exit_rate"] == 0.5625


def test_empty_and_unknown_files_are_reported():
    parsed = parse_export(
        files(TopPages=TOP_PAGES, Possible404="", Foo=tsv(["Foo", "Bar"], ["a", "b"])), DOMAIN
    )
    assert parsed["empty"] == ["Possible404.csv"]
    assert parsed["unknown"] == ["Foo.csv"]


def test_header_only_file_counts_as_empty():
    parsed = parse_export(files(TopPages=TOP_PAGES, Cities=tsv(["City", "Visitors"])), DOMAIN)
    assert parsed["empty"] == ["Cities.csv"]


def test_rejects_pages_outside_site():
    bad = tsv(
        ["Page", "Visitors", "Views", "Bounce rate", "Time on page"],
        ["https://evil.example/", "1", "1", "0.", "1"],
    )
    with pytest.raises(ValueError, match="belong to this website"):
        parse_export(files(TopPages=bad), DOMAIN)


def test_outbound_links_are_not_domain_checked():
    parsed = parse_export(files(OutboundLinkClicks=OUTBOUND), DOMAIN)
    assert parsed["reports"]["outbound_links"][0]["href"] == "tel:+17032440559"


def test_rejects_no_recognised_report():
    with pytest.raises(ValueError, match="No Ahrefs Web Analytics report"):
        parse_export(files(Foo=tsv(["Foo"], ["x"])), DOMAIN)


def test_rejects_bad_number():
    bad = tsv(
        ["Channel", "Visitors", "Bounce rate", "Visit duration"], ["Direct", "lots", "0.", "1"]
    )
    with pytest.raises(ValueError, match="number"):
        parse_export(files(Channel=bad), DOMAIN)


def test_rejects_over_2mb():
    padding = "x" * 1_100_000
    with pytest.raises(ValueError, match="2 MB"):
        parse_export(files(Channel=CHANNELS + padding, Device=CHANNELS + padding), DOMAIN)


def test_rejects_over_20000_rows():
    rows = [["Channel", "Visitors", "Bounce rate", "Visit duration"]] + [
        [f"c{i}", "1", "0.", "1"] for i in range(20_001)
    ]
    with pytest.raises(ValueError, match="20,000"):
        parse_export(files(Channel=tsv(*rows)), DOMAIN)


def site(db) -> Site:
    return db.scalar(select(Site).where(Site.domain == DOMAIN))


def do_import(db, start=date(2026, 10, 13), end=date(2026, 11, 11), **overrides):
    snapshot = import_web_analytics(db, site(db), start, end, export(**overrides))
    db.commit()
    return snapshot


def test_import_stores_snapshot_totals_and_raw_rows(db, seeded):
    snapshot = do_import(db)
    assert snapshot.kind == "web-analytics"
    assert (snapshot.start_date, snapshot.end_date) == (date(2026, 10, 13), date(2026, 11, 11))
    assert snapshot.data["totals"] == {"visitors": 35, "phone_clicks": 3, "pages": 2}
    assert snapshot.data["files"]["recognised"] == 4
    kinds = dict(
        db.execute(select(AhrefsCsvRow.kind, func.count()).group_by(AhrefsCsvRow.kind)).all()
    )
    assert kinds == {
        "web-analytics:top_pages": 2,
        "web-analytics:exit_pages": 1,
        "web-analytics:channels": 3,
        "web-analytics:outbound_links": 2,
    }


def test_typed_rows_stored(db, seeded):
    do_import(db)
    rows = db.scalars(select(AhrefsWebAnalytics).order_by(AhrefsWebAnalytics.id)).all()
    assert len(rows) == 8
    exit_row = next(row for row in rows if row.report == "exit_pages")
    assert (exit_row.item, exit_row.exits, float(exit_row.exit_rate)) == (f"{SITE}/", 9, 0.5625)
    assert {row.site for row in rows} == {DOMAIN}
    assert {(row.period_start, row.period_end) for row in rows} == {
        (date(2026, 10, 13), date(2026, 11, 11))
    }


def test_reimport_same_period_replaces(db, seeded):
    do_import(db)
    do_import(db)
    assert db.scalar(select(func.count()).select_from(AxisSnapshot)) == 1
    assert db.scalar(select(func.count()).select_from(AhrefsWebAnalytics)) == 8
    do_import(db, start=date(2026, 9, 13), end=date(2026, 10, 12))
    assert db.scalar(select(func.count()).select_from(AxisSnapshot)) == 2


def test_latest_and_previous_imports(db, seeded):
    older = do_import(db, start=date(2026, 9, 13), end=date(2026, 10, 12))
    newer = do_import(db)
    assert latest_web_analytics(db, DOMAIN).id == newer.id
    assert previous_web_analytics(db, DOMAIN, newer).id == older.id
    assert previous_web_analytics(db, DOMAIN, older) is None


def test_compare_imports():
    latest = {
        "totals": {"visitors": 35, "phone_clicks": 3},
        "reports": {
            "channels": [
                {"name": "a", "visitors": 30, "bounce_rate": 0.5},
                {"name": "b", "visitors": 5, "bounce_rate": 1.0},
            ],
            "top_pages": [{"page": "/x", "visitors": 10}, {"page": "/y", "visitors": 4}],
        },
    }
    previous = {
        "totals": {"visitors": 20, "phone_clicks": 0},
        "reports": {
            "channels": [{"name": "a", "visitors": 20, "bounce_rate": 0.25}],
            "top_pages": [{"page": "/x", "visitors": 6}],
        },
    }
    changes = compare_imports(latest, previous)
    assert changes["visitors"] == {"now": 35, "before": 20, "change_percent": 75.0}
    assert changes["phone_clicks"] == {"now": 3, "before": 0, "change_percent": None}
    assert changes["bounce_rate"]["now"] == pytest.approx(0.5714, abs=1e-4)
    assert changes["bounce_rate"]["before"] == 0.25
    assert changes["pages"] == [
        {"page": "/x", "visitors_now": 10, "visitors_before": 6},
        {"page": "/y", "visitors_now": 4, "visitors_before": 0},
    ]
    assert compare_imports(latest, None) == {}


def test_unreadable_tsv_is_a_clear_error_not_a_crash():
    broken = '"Channel"\t"Visitors"\t"Bounce rate"\t"Visit duration"\n"Direct\t' + "x" * 140_000
    with pytest.raises(ValueError, match="could not be read"):
        parse_export(files(Channel=broken), DOMAIN)


def test_nul_characters_are_rejected():
    bad = CHANNELS.replace("Direct", "Dir\x00ect")
    with pytest.raises(ValueError, match="could not be read"):
        parse_export(files(Channel=bad), DOMAIN)


def test_bom_only_body_and_dot_rates():
    parsed = parse_export(files(Possible404="﻿", Channel=CHANNELS), DOMAIN)
    assert parsed["empty"] == ["Possible404.csv"]
    assert [row["bounce_rate"] for row in parsed["reports"]["channels"]][2] == 0.0
