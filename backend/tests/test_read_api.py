from datetime import UTC, date, datetime
from decimal import Decimal

import httplib2
import pytest
import requests

from app import metrics
from app.models import Ga4Daily, Ga4SyncLog, GscDaily, GscSyncLog

DOMAIN = "arlington247lockrepair.com"
BASE = "/api/sites/arlington"
START, END = "2026-10-15", "2026-10-16"
PATHS = ["summary", "timeseries", "gsc/pages", "gsc/queries", "ga4/pages", "status"]


@pytest.fixture(autouse=True)
def no_google_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Read API tests must not make Google HTTP requests")

    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.setattr(httplib2.Http, "request", blocked)


@pytest.fixture
def data(db, client):
    def gsc(day, page, query, device, clicks, impressions, position, domain=DOMAIN):
        return GscDaily(
            site=domain,
            data_date=date.fromisoformat(day),
            page=f"https://{domain}/{page}",
            query=query,
            device=device,
            clicks=clicks,
            impressions=impressions,
            ctr=Decimal("0.9999"),
            position=Decimal(str(position)),
        )

    def ga4(day, path, sessions, users, conversions, rate):
        return Ga4Daily(
            site=DOMAIN,
            data_date=date.fromisoformat(day),
            page_path=path,
            sessions=sessions,
            total_users=users,
            conversions=conversions,
            engagement_rate=Decimal(str(rate)),
        )

    db.add_all(
        [
            gsc(START, "a", "alpha", "MOBILE", 10, 100, 2),
            gsc(START, "a", "beta", "DESKTOP", 1, 300, 10),
            gsc(START, "b", "alpha", "MOBILE", 3, 100, 6),
            gsc(START, "c", "", "TABLET", 0, 0, 5),
            gsc(END, "a", "alpha", "MOBILE", 2, 100, 4),
            gsc(END, "b", "alpha", "DESKTOP", 4, 200, 12),
            gsc("2026-10-13", "a", "alpha", "MOBILE", 8, 40, 5),
            gsc("2026-10-14", "a", "alpha", "MOBILE", 2, 60, 9),
            gsc("2026-10-10", "a", "alpha", "MOBILE", 1000, 10000, 1),
            gsc(END, "a", "alpha", "MOBILE", 999, 9999, 1, "TODO-site2.example"),
            ga4(START, "/a", 10, 8, 1, 0.2),
            ga4(END, "/a", 30, 20, 3, 0.8),
            ga4(END, "/b", 5, 4, 0, 0.4),
            ga4(START, "(not set)", 0, 0, 0, 0.8),
            ga4("2026-10-14", "/a", 20, 10, 2, 0.5),
            GscSyncLog(
                site=DOMAIN,
                last_loaded_date=date(2026, 10, 16),
                last_run_at=datetime(2026, 10, 19, tzinfo=UTC),
                status="ok",
                rows_loaded=200,
            ),
            Ga4SyncLog(
                site=DOMAIN,
                last_loaded_date=date(2026, 10, 15),
                status="error",
                rows_loaded=4,
                error="fixture failure",
            ),
        ]
    )
    db.commit()


@pytest.fixture
def get(client, login_as, data):
    login_as()

    def request(path, **params):
        return client.get(f"{BASE}/{path}", params={"start": START, "end": END, **params})

    return request


def test_summary_current_previous_weighted_position_and_computed_ctr(get):
    response = get("summary")
    assert response.status_code == 200
    result = response.json()
    assert result["current_window"] == {"start": START, "end": END}
    assert result["previous_window"] == {"start": "2026-10-13", "end": "2026-10-14"}
    assert result["current"] == {
        "gsc": {"clicks": 20, "impressions": 800, "ctr": 0.025, "avg_position": 8.25},
        "ga4": {"sessions": 45, "total_users": 32, "conversions": 4},
    }
    assert result["previous"] == {
        "gsc": {"clicks": 10, "impressions": 100, "ctr": 0.1, "avg_position": 7.4},
        "ga4": {"sessions": 20, "total_users": 10, "conversions": 2},
    }
    assert response.headers["cache-control"] == "no-store"


def test_timeseries_every_day_and_unknown_missing_days(get):
    assert get("timeseries", end="2026-10-17").json() == [
        {
            "data_date": START,
            "gsc_clicks": 14,
            "gsc_impressions": 500,
            "ga4_sessions": 10,
            "ga4_users": 8,
        },
        {
            "data_date": END,
            "gsc_clicks": 6,
            "gsc_impressions": 300,
            "ga4_sessions": 35,
            "ga4_users": 24,
        },
        {
            "data_date": "2026-10-17",
            "gsc_clicks": None,
            "gsc_impressions": None,
            "ga4_sessions": None,
            "ga4_users": None,
        },
    ]


def test_gsc_pages_weighted_aggregation_and_null_zero_impressions(get):
    assert get("gsc/pages").json() == [
        {
            "page": f"https://{DOMAIN}/a",
            "clicks": 13,
            "impressions": 500,
            "ctr": 0.026,
            "avg_position": 7.2,
        },
        {
            "page": f"https://{DOMAIN}/b",
            "clicks": 7,
            "impressions": 300,
            "ctr": 0.0233,
            "avg_position": 10.0,
        },
        {
            "page": f"https://{DOMAIN}/c",
            "clicks": 0,
            "impressions": 0,
            "ctr": None,
            "avg_position": None,
        },
    ]


def test_gsc_queries_group_by_query_and_pick_top_page_by_impressions(get):
    assert get("gsc/queries").json() == [
        {
            "query": "alpha",
            "clicks": 19,
            "impressions": 500,
            "ctr": 0.038,
            "avg_position": 7.2,
            "top_page": f"https://{DOMAIN}/b",
        },
        {
            "query": "beta",
            "clicks": 1,
            "impressions": 300,
            "ctr": 0.0033,
            "avg_position": 10.0,
            "top_page": f"https://{DOMAIN}/a",
        },
    ]


def test_ga4_pages_use_session_weighted_engagement_and_keep_buckets(get):
    assert get("ga4/pages").json() == [
        {
            "page_path": "/a",
            "sessions": 40,
            "total_users": 28,
            "conversions": 4,
            "engagement_rate": 0.65,
        },
        {
            "page_path": "/b",
            "sessions": 5,
            "total_users": 4,
            "conversions": 0,
            "engagement_rate": 0.4,
        },
        {
            "page_path": "(not set)",
            "sessions": 0,
            "total_users": 0,
            "conversions": 0,
            "engagement_rate": None,
        },
    ]


def test_status_returns_each_sources_log(get):
    response = get("status")
    assert response.status_code == 200
    result = response.json()
    assert result["gsc"]["site"] == DOMAIN
    assert result["gsc"]["last_loaded_date"] == END
    assert result["gsc"]["rows_loaded"] == 200
    assert result["gsc"]["status"] == "ok"
    assert result["gsc"]["error"] is None
    assert result["ga4"]["status"] == "error"
    assert result["ga4"]["rows_loaded"] == 4
    assert result["ga4"]["error"] == "fixture failure"


@pytest.mark.parametrize("path", PATHS)
def test_all_endpoints_require_login(client, path):
    assert client.get(f"{BASE}/{path}").status_code == 401


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("slug", ["site2", "missing"])
def test_all_endpoints_hide_unlinked_and_missing_sites(client, login_as, path, slug):
    login_as()
    response = client.get(f"/api/sites/{slug}/{path}", params={"start": START, "end": END})
    assert response.status_code == 404
    assert response.json() == {"detail": "Site not found"}


def test_admin_access_and_missing_source_nulls(client, login_as, data):
    login_as("admin")
    result = client.get("/api/sites/site2/summary", params={"start": START, "end": END}).json()
    assert result["current"]["gsc"]["clicks"] == 999
    assert result["current"]["ga4"] is None
    assert result["previous"] == {"gsc": None, "ga4": None}
    assert client.get("/api/sites/site2/status").json() == {"gsc": None, "ga4": None}


@pytest.mark.parametrize("path", PATHS[:-1])
@pytest.mark.parametrize(
    "params",
    [
        {"start": "2026-10-17", "end": END},
        {"start": "2025-06-15", "end": END},
    ],
)
def test_invalid_or_over_16_month_ranges_return_422(client, login_as, path, params):
    login_as()
    assert client.get(f"{BASE}/{path}", params=params).status_code == 422


def test_defaults_use_timezone_lag_and_28_day_window(client, login_as, monkeypatch):
    monkeypatch.setattr("app.metrics.today_in", lambda timezone: date(2026, 10, 19))
    login_as()
    result = client.get(f"{BASE}/summary").json()
    assert result["current_window"] == {"start": "2026-09-19", "end": END}
    assert result["previous_window"] == {"start": "2026-08-22", "end": "2026-09-18"}


def test_calendar_month_boundary_is_accepted(get):
    assert get("summary", start="2025-06-16").status_code == 200
    assert metrics.resolve_window(date(2025, 2, 28), date(2026, 6, 30)).start == date(2025, 2, 28)


@pytest.mark.parametrize(
    "path,key,expected",
    [
        ("gsc/pages", "page", f"https://{DOMAIN}/b"),
        ("gsc/queries", "query", "beta"),
        ("ga4/pages", "page_path", "/b"),
    ],
)
def test_pagination_and_descending_order(get, path, key, expected):
    rows = get(path, limit=1, offset=1).json()
    assert len(rows) == 1
    assert rows[0][key] == expected
    assert get(path, limit=1, offset=50).json() == []


@pytest.mark.parametrize("path", ["gsc/pages", "gsc/queries", "ga4/pages"])
@pytest.mark.parametrize("params", [{"limit": 1001}, {"limit": 0}, {"offset": -1}])
def test_pagination_bounds(get, path, params):
    assert get(path, **params).status_code == 422


@pytest.mark.parametrize("device", ["MOBILE", "DESKTOP", "TABLET"])
def test_gsc_device_filter(get, device):
    pages = get("gsc/pages", device=device).json()
    queries = get("gsc/queries", device=device).json()
    assert (
        sum(row["impressions"] for row in pages)
        == {"MOBILE": 300, "DESKTOP": 500, "TABLET": 0}[device]
    )
    if device == "MOBILE":
        assert queries[0]["query"] == "alpha"
        assert queries[0]["clicks"] == 15
        assert queries[0]["avg_position"] == 4.0
    if device == "TABLET":
        assert queries == []


def test_invalid_device_or_date_returns_422(get):
    assert get("gsc/pages", device="mobile").status_code == 422
    assert get("gsc/queries", device="PHONE").status_code == 422
    assert get("summary", start="not-a-date").status_code == 422
    assert get("summary", start=None, end="0001-01-01").status_code == 422


def test_query_with_zero_impressions_has_null_ctr_and_position(get, db):
    db.add(
        GscDaily(
            site=DOMAIN,
            data_date=date.fromisoformat(END),
            page=f"https://{DOMAIN}/zero",
            query="zero-impression query",
            device="TABLET",
            clicks=0,
            impressions=0,
            position=Decimal("1"),
        )
    )
    db.commit()
    result = get("gsc/queries").json()[-1]
    assert result["query"] == "zero-impression query"
    assert result["ctr"] is None
    assert result["avg_position"] is None


def test_present_zero_rows_are_not_reported_as_missing_sources(get, db):
    day = date(2026, 1, 1)
    db.add_all(
        [
            GscDaily(
                site=DOMAIN,
                data_date=day,
                page=f"https://{DOMAIN}/zero",
                query="",
                device="MOBILE",
                clicks=0,
                impressions=0,
                position=None,
            ),
            Ga4Daily(
                site=DOMAIN,
                data_date=day,
                page_path="/zero",
                sessions=0,
                total_users=0,
                conversions=0,
                engagement_rate=None,
            ),
        ]
    )
    db.commit()
    assert get("summary", start=day.isoformat(), end=day.isoformat()).json()["current"] == {
        "gsc": {"clicks": 0, "impressions": 0, "ctr": None, "avg_position": None},
        "ga4": {"sessions": 0, "total_users": 0, "conversions": 0},
    }


def test_empty_ranges_return_null_sources_and_empty_tables(get):
    assert get("summary", start="2024-01-01", end="2024-01-02").json()["current"] == {
        "gsc": None,
        "ga4": None,
    }
    for path in ["gsc/pages", "gsc/queries", "ga4/pages"]:
        assert get(path, start="2024-01-01", end="2024-01-02").json() == []
