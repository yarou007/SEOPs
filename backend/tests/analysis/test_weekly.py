import json
from datetime import date, timedelta
from decimal import Decimal

import httplib2
import pytest
import requests
from conftest import add_test_gsc_totals, run_cli

from app import metrics
from app.analysis.weekly import (
    ANALYSIS_THRESHOLDS,
    band_medians,
    build_report,
    find_page_flags,
    position_band,
    query_candidates,
    render_markdown,
    source_health,
    write_report,
)
from app.config import get_settings
from app.models import Ga4Daily, Ga4SyncLog, GscDaily, GscSyncLog, Site

TODAY = date(2026, 10, 19)
END = date(2026, 10, 16)
DOMAIN = "arlington247lockrepair.com"


@pytest.fixture(autouse=True)
def no_google_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Weekly analysis must only read local fixture data")

    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.setattr(httplib2.Http, "request", blocked)


def page(name="target", clicks=20, impressions=200, position="2"):
    return {
        "page": f"https://{DOMAIN}/{name}",
        "clicks": clicks,
        "impressions": impressions,
        "ctr": Decimal(clicks) / impressions if impressions else None,
        "avg_position": Decimal(position) if position is not None else None,
    }


def flags(current, *, previous=(), last7=(), prev7=(), mobile=(), desktop=()):
    return find_page_flags(
        list(current), list(previous), list(last7), list(prev7), list(mobile), list(desktop)
    )


def peers():
    return [page(f"peer{i}", clicks=100, impressions=1000) for i in range(3)]


@pytest.mark.parametrize(
    "clicks,impressions,expected", [(10, 300, True), (15, 300, False), (1, 199, False)]
)
def test_check1_low_ctr_threshold_and_strict_median_ratio(clicks, impressions, expected):
    result = flags([page(clicks=clicks, impressions=impressions), *peers()])
    assert bool(result) == expected
    if expected:
        assert result[0]["check"] == "low_ctr"
        assert result[0]["reason"] == "high impressions, CTR below band median"
        assert result[0]["median_ctr_for_band"] == Decimal("0.1")
        assert result[0]["impressions_lost"].quantize(Decimal("0.01")) == Decimal("20.00")


@pytest.mark.parametrize(
    "mobile_clicks,mobile_impressions,expected", [(11, 200, True), (14, 200, False), (1, 99, False)]
)
def test_check2_mobile_gap_threshold_and_strict_ratio(mobile_clicks, mobile_impressions, expected):
    mobile = page(clicks=mobile_clicks, impressions=mobile_impressions)
    desktop = page(clicks=20, impressions=200)
    current = page(clicks=mobile_clicks + 20, impressions=mobile_impressions + 200)
    result = flags([current], mobile=[mobile], desktop=[desktop])
    assert bool(result) == expected
    if expected:
        assert result[0]["check"] == "mobile_gap"
        assert result[0]["reason"] == "mobile CTR gap"
        assert result[0]["impressions_lost"] == 0


def test_mobile_gap_skips_missing_device_and_zero_desktop_ctr():
    current = page(clicks=1, impressions=200)
    assert flags([current], mobile=[current]) == []
    assert flags([current], desktop=[current]) == []
    assert flags([current], mobile=[page(clicks=0)], desktop=[page(clicks=0)]) == []


@pytest.mark.parametrize(
    "last_clicks,previous_clicks,expected", [(11, 20, True), (12, 20, False), (0, 19, False)]
)
def test_check4_weekly_click_drop_thresholds(last_clicks, previous_clicks, expected):
    result = flags(
        [page(clicks=100, impressions=1000)],
        last7=[page(clicks=last_clicks)],
        prev7=[page(clicks=previous_clicks)],
    )
    assert bool(result) == expected
    if expected:
        assert result[0]["check"] == "clicks_dropping"
        assert result[0]["reason"] == "clicks down 45% week over week"
        assert result[0]["last7_clicks"] == 11
        assert result[0]["prev7_clicks"] == 20


@pytest.mark.parametrize(
    "clicks,impressions,expected", [(0, 100, True), (0, 99, False), (1, 100, False)]
)
def test_check5_zero_click_threshold(clicks, impressions, expected):
    result = flags([page(clicks=clicks, impressions=impressions)])
    assert bool(result) == expected
    if expected:
        assert result[0]["check"] == "zero_clicks"
        assert result[0]["reason"] == "100+ impressions, no clicks"


@pytest.mark.parametrize(
    "current_clicks,previous_clicks,expected", [(13, 20, True), (14, 20, False), (0, 19, False)]
)
def test_check6_trend_drop_thresholds(current_clicks, previous_clicks, expected):
    result = flags(
        [page(clicks=current_clicks, impressions=50)], previous=[page(clicks=previous_clicks)]
    )
    assert bool(result) == expected
    if expected:
        assert result[0]["check"] == "trend"
        assert result[0]["reason"] == "clicks down 35% vs previous 28 days"
        assert result[0]["previous_clicks"] == 20


@pytest.mark.parametrize(
    "position,expected",
    [
        ("3.9", "1–3"),
        ("4.0", "4–7"),
        ("7.99", "4–7"),
        ("8", "8–10"),
        ("10.99", "8–10"),
        ("11", "11–20"),
        ("20.9", "11–20"),
        ("21", "21+"),
    ],
)
def test_position_bands_use_fractional_half_open_intervals(position, expected):
    assert position_band(Decimal(position)) == expected


def test_band_medians_do_not_mix_3_point_9_and_4_point_0_or_round_early():
    rows = [page("a", 10, 100, "3.9"), page("b", 20, 100, "3.999"), page("c", 1, 100, "4.0")]
    assert band_medians(rows) == {"1–3": Decimal("0.15"), "4–7": Decimal("0.01")}
    assert position_band(None) is None


def test_one_page_keeps_strongest_flag_and_estimated_loss():
    target = page(clicks=0, impressions=500)
    result = flags([target, *peers()], previous=[page(clicks=100)])
    assert len(result) == 1
    assert result[0]["check"] == "zero_clicks"
    assert result[0]["impressions_lost"] == Decimal(50)


def test_loss_is_floored_at_zero_even_when_trend_flags_a_high_ctr_page():
    result = flags([page(clicks=5, impressions=10), *peers()], previous=[page(clicks=100)])
    assert result[0]["check"] == "trend"
    assert result[0]["impressions_lost"] == 0


def test_completely_missing_current_source_does_not_claim_zero_traffic():
    assert flags([], previous=[page(clicks=100)]) == []


def test_disappearing_page_counts_as_zero_if_other_current_data_exists():
    result = flags([page("other")], previous=[page(clicks=100)])
    assert len(result) == 1
    assert result[0]["check"] == "trend"
    assert result[0]["clicks"] == 0
    assert result[0]["drop_percent"] == 100


def test_thresholds_are_tunable_in_one_dict(monkeypatch):
    monkeypatch.setitem(ANALYSIS_THRESHOLDS, "zero_click_min_impressions", 150)
    assert flags([page(clicks=0, impressions=100)]) == []


@pytest.fixture
def site(db):
    site = Site(slug="arlington", domain=DOMAIN, display_name="Arlington")
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def gsc_row(path, clicks, impressions, *, position="2", day=END, query="", device="MOBILE"):
    return GscDaily(
        site=DOMAIN,
        data_date=day,
        page=f"https://{DOMAIN}/{path}",
        query=query,
        device=device,
        clicks=clicks,
        impressions=impressions,
        position=Decimal(position),
    )


@pytest.fixture
def capped_data(db, site):
    db.add_all([gsc_row(f"zero{i}", 0, (i + 1) * 100) for i in range(5)])
    db.add_all([gsc_row(f"peer{i}", 100, 1000) for i in range(7)])
    db.add_all(
        [
            Ga4Daily(
                site=DOMAIN,
                data_date=END,
                page_path="/",
                sessions=5,
                total_users=3,
                conversions=1,
                engagement_rate=Decimal("0.5"),
            ),
            GscSyncLog(site=DOMAIN, last_loaded_date=END, status="ok", rows_loaded=12),
            Ga4SyncLog(site=DOMAIN, last_loaded_date=END, status="ok", rows_loaded=1),
        ]
    )
    add_test_gsc_totals(db)
    db.commit()


def test_report_caps_five_flagged_pages_at_three_without_hiding_full_count(db, site, capped_data):
    report = build_report(db, site, as_of=TODAY)
    assert report["flagged_pages_count"] == 5
    assert len(report["top_pages"]) == 3
    assert [row["page"] for row in report["top_pages"]] == [
        f"https://{DOMAIN}/zero{i}" for i in [4, 3, 2]
    ]
    assert [row["impressions_lost"] for row in report["top_pages"]] == [50.0, 40.0, 30.0]
    assert all(row["check"] == "zero_clicks" for row in report["top_pages"])
    assert report["windows"]["current"] == {"start": "2026-09-19", "end": "2026-10-16"}
    assert report["windows"]["previous"] == {"start": "2026-08-22", "end": "2026-09-18"}
    assert report["windows"]["last7"] == {"start": "2026-10-10", "end": "2026-10-16"}
    assert report["windows"]["prev7"] == {"start": "2026-10-03", "end": "2026-10-09"}
    assert report["totals"]["current"]["gsc"]["clicks"] == 700
    assert report["totals"]["current"]["ga4"] == {"sessions": 5, "total_users": 3, "conversions": 1}
    assert report["totals"]["previous"] == {"gsc": None, "ga4": None}
    assert report["device_split"]["MOBILE"]["clicks"] == 700
    assert report["device_split"]["DESKTOP"] is None
    assert report["warnings"] == []
    markdown = render_markdown(report)
    assert "Showing 3 of 5 flagged pages" in markdown
    assert "## Data notes" in markdown
    assert "GSC hides some queries" in markdown
    assert "Always use page totals as the main figure" in markdown
    for item in report["top_pages"]:
        assert item["page"] in markdown
        assert item["reason"] in markdown


@pytest.mark.parametrize(
    "position,impressions,expected",
    [
        ("8", 50, True),
        ("20", 50, True),
        ("7.99", 50, False),
        ("20.01", 50, False),
        ("10", 49, False),
    ],
)
def test_check3_query_candidates_thresholds(db, site, position, impressions, expected):
    db.add(gsc_row("candidate", 1, impressions, position=position, query="locksmith"))
    db.commit()
    result = query_candidates(db, DOMAIN, metrics.Window(END - timedelta(days=27), END))
    assert bool(result) == expected
    if expected:
        assert result[0]["reason"] == "position 8–20, close to page 1"
        assert result[0]["top_page"] == f"https://{DOMAIN}/candidate"


def test_query_candidates_top_ten_use_aggregates_and_top_page_by_impressions(db, site):
    db.add_all(
        [gsc_row(f"candidate{i}", 1, 50 + i, position="10", query=f"query{i}") for i in range(12)]
    )
    db.add(gsc_row("stronger-page", 2, 200, position="10", query="query0"))
    db.add(gsc_row("blank-query", 10, 10000, position="10"))
    db.commit()
    result = query_candidates(db, DOMAIN, metrics.Window(END, END))
    assert len(result) == 10
    assert result[0]["query"] == "query0"
    assert result[0]["impressions"] == 250
    assert result[0]["top_page"] == f"https://{DOMAIN}/stronger-page"
    assert result[1]["query"] == "query11"
    assert all(row["query"] for row in result)


@pytest.mark.parametrize("age,stale", [(5, False), (6, True)])
def test_stale_sync_warning_uses_today_and_lag_plus_two(db, site, age, stale):
    db.add_all(
        [
            GscSyncLog(site=DOMAIN, last_loaded_date=TODAY - timedelta(days=age), status="ok"),
            Ga4SyncLog(site=DOMAIN, last_loaded_date=END, status="ok"),
        ]
    )
    db.commit()
    report = build_report(db, site, as_of=TODAY)
    assert report["sync_status"]["gsc"]["stale"] is stale
    assert any("GSC: stale sync" in warning for warning in report["warnings"]) is stale
    assert ("GSC: stale sync" in render_markdown(report)) is stale


def test_missing_and_failed_sync_status_are_visible(db, site):
    db.add(GscSyncLog(site=DOMAIN, last_loaded_date=END, status="error", error="fixture error"))
    db.commit()
    status, warnings = source_health(db, DOMAIN, TODAY, get_settings())
    assert status["gsc"]["stale"] is False
    assert status["ga4"]["stale"] is True
    assert "GSC: last sync failed: fixture error" in warnings
    assert "GA4: no successful sync checkpoint" in warnings


def test_cli_writes_both_formats_with_same_data_to_temp_reports_dir(
    db, site, capped_data, tmp_path, monkeypatch
):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    result = run_cli("app.analysis", "weekly", "--site", "arlington")
    assert result.returncode == 0
    json_files = list((tmp_path / "arlington").glob("*.json"))
    assert len(json_files) == 1
    report = json.loads(json_files[0].read_text())
    md_file = json_files[0].with_suffix(".md")
    assert md_file.exists()
    assert md_file.read_text() == render_markdown(report)
    assert json_files[0].stem == report["report_date"]
    assert report["site"]["domain"] == DOMAIN
    assert report["data_notes"]


def test_cli_all_skips_inactive_and_continues_after_site_failure(db, site, tmp_path, monkeypatch):
    from app.analysis.main import main

    db.add_all(
        [
            Site(slug="site2", domain="site2.example", display_name="Site 2"),
            Site(slug="site3", domain="site3.example", display_name="Site 3", active=False),
        ]
    )
    db.commit()
    settings = get_settings().model_copy(update={"reports_dir": tmp_path})
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    from app.analysis import weekly

    original = weekly.build_report
    seen = []

    def report(db, selected, **kwargs):
        seen.append(selected.slug)
        if selected.slug == "arlington":
            raise RuntimeError("fixture error")
        return original(db, selected, **kwargs)

    monkeypatch.setattr(weekly, "build_report", report)
    assert main(["weekly", "--all"]) == 1
    assert seen == ["arlington", "site2"]
    assert len(list((tmp_path / "site2").glob("*.json"))) == 1
    assert not (tmp_path / "site3").exists()


def test_report_writer_rejects_slug_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="direct child"):
        write_report(
            {"site": {"slug": "../escape"}, "report_date": "2026-10-19"}, tmp_path / "reports"
        )
