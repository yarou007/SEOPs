from datetime import date
from unittest.mock import Mock

import httplib2
import pytest
import requests
from sqlalchemy import select

from app.analysis.csv_sources import import_csv
from app.analysis.sources import collect_ga4, collect_gsc
from app.config import get_settings, zones
from app.metrics import Window
from app.models import AxisSnapshot, Ga4Daily, GscDaily, GscIndexStatus, Site

DAY = date(2026, 10, 19)
WINDOW = Window(DAY, DAY)
DOMAIN = "arlington247lockrepair.com"
BASE = "/api/sites/arlington/axes"
AXES = [
    "impressions-clicks",
    "funnel",
    "devices",
    "geography",
    "sitemaps",
    "internal-links",
    "site-links",
    "search-requests",
]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Axis tests must not contact Google or websites")

    monkeypatch.setattr(httplib2.Http, "request", blocked)
    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.setattr(zones, "ZONES", [])
    monkeypatch.setattr(get_settings(), "ga4_call_click_events", {})


@pytest.fixture
def get(client, login_as):
    login_as()

    def request(axis):
        response = client.get(f"{BASE}/{axis}", params={"start": str(DAY), "end": str(DAY)})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        return response.json()

    return request


@pytest.mark.parametrize("axis", AXES)
def test_empty_axis_needs_setup(get, axis):
    result = get(axis)
    assert result["status"] == "needs_setup"
    assert result["reason"]
    assert isinstance(result["data"], dict)


@pytest.mark.parametrize("axis", AXES)
def test_auth_and_hidden_site(client, login_as, axis):
    assert client.get(f"{BASE}/{axis}").status_code == 401
    login_as()
    for slug in ["site2", "missing"]:
        assert client.get(f"/api/sites/{slug}/axes/{axis}").status_code == 404
    assert client.get(f"{BASE}/{axis}?start=2026-10-20&end=2026-10-19").status_code == 422


@pytest.fixture
def facts(db, client):
    for page, query, device, country, clicks, impressions in [
        ("", "", "", "all", 4, 150),
        (f"https://{DOMAIN}/repair", "", "", "all", 0, 150),
        ("", "", "MOBILE", "all", 4, 150),
        ("", "", "", "usa", 4, 150),
        (f"https://{DOMAIN}/repair", "emergency locksmith Georgetown", "MOBILE", "all", 0, 100),
    ]:
        db.add(
            GscDaily(
                site=DOMAIN,
                data_date=DAY,
                page=page,
                query=query,
                device=device,
                country=country,
                clicks=clicks,
                impressions=impressions,
                position=12,
            )
        )
    db.add(
        Ga4Daily(
            site=DOMAIN, data_date=DAY, page_path="/", sessions=7, total_users=7, conversions=0
        )
    )
    db.commit()


def test_impressions_and_queries_are_separate_and_labeled_partial(get, facts):
    result = get("impressions-clicks")
    assert result["status"] == "partial"
    assert result["data"]["pages"][0]["impressions"] == 150
    assert result["data"]["queries"][0]["impressions"] == 100
    assert result["data"]["pages"][0]["high_impressions_zero_clicks"] is True
    assert "hides" in result["reason"]


def test_funnel_requires_event_then_reports_rates(get, facts, db, monkeypatch):
    assert get("funnel")["data"]["steps"][3]["value"] is None
    monkeypatch.setitem(get_settings().ga4_call_click_events, "arlington", "call_click")
    assert get("funnel")["status"] == "needs_setup"
    db.add(
        AxisSnapshot(
            site=DOMAIN,
            kind="calls",
            start_date=DAY,
            end_date=DAY,
            data={"event": "call_click", "count": 2},
        )
    )
    db.commit()
    result = get("funnel")
    assert result["status"] == "ready"
    assert [step["value"] for step in result["data"]["steps"]] == [150, 4, 7, 2]
    assert result["data"]["steps"][1]["rate_from_previous"] == 0.0267
    assert result["data"]["steps"][2]["rate_from_previous"] == 1.75
    assert "Cross-source" in result["data"]["note"]


def test_devices_missing_and_full_os_remain_partial(get, facts, db):
    assert "Collect" in get("devices")["reason"]
    db.add(
        AxisSnapshot(
            site=DOMAIN,
            kind="os",
            start_date=DAY,
            end_date=DAY,
            data={"rows": [{"os": "iOS", "sessions": 3, "conversions": 0}]},
        )
    )
    db.commit()
    result = get("devices")
    assert result["status"] == "partial"
    assert result["data"]["operating_systems"][0]["sessions"] == 3
    assert "site-level only" in result["reason"]


def test_geography_matches_zones_not_substrings(get, facts, monkeypatch):
    monkeypatch.setattr(zones, "ZONES", ["Georgetown", "town"])
    result = get("geography")
    assert result["status"] == "partial"
    assert [row["zone"] for row in result["data"]["zones"]] == ["Georgetown"]
    assert result["data"]["zones"][0]["avg_position"] == 12


def test_sitemaps_collection_sample_and_unindexed_reason(get, db):
    site = db.scalar(select(Site).where(Site.domain == DOMAIN))
    site.gsc_property = f"sc-domain:{DOMAIN}"
    client = Mock()
    client.sitemaps.return_value = [
        {"path": f"https://{DOMAIN}/sitemap.xml", "contents": [{"submitted": "59"}]}
    ]
    client.inspect.side_effect = [
        {"verdict": "PASS", "coverageState": "Indexed"},
        {"verdict": "NEUTRAL", "coverageState": "Excluded by noindex"},
    ]
    collect_gsc(db, site, client, [])
    db.commit()
    assert "first URL inspection" in get("sitemaps")["reason"]
    collect_gsc(db, site, client, [f"https://{DOMAIN}/", f"https://{DOMAIN}/x"])
    db.commit()
    result = get("sitemaps")
    assert result["status"] == "partial"  # never imply complete sitemap coverage
    assert result["data"]["submitted"] == 59
    assert result["data"]["indexed"] == result["data"]["not_indexed"] == 1
    assert result["data"]["urls"][1]["reason"] == "Excluded by noindex"
    assert "bounded sample" in result["reason"]


def test_inspection_limit_validated_before_network(db):
    site = Site(domain=DOMAIN, gsc_property="test")
    client = Mock()
    with pytest.raises(ValueError, match="200"):
        collect_gsc(db, site, client, [f"https://{DOMAIN}/{i}" for i in range(201)])
    client.sitemaps.assert_not_called()
    with pytest.raises(ValueError, match="belong"):
        collect_gsc(db, site, client, ["https://external.example/"])
    client.inspect.assert_not_called()


def test_collect_ga4_groups_os_and_does_not_invent_call_counts(db, client):
    site = db.scalar(select(Site).where(Site.domain == DOMAIN))
    site.ga4_property_id = "123"
    fake = Mock()
    fake.report.side_effect = [
        [
            {"operatingSystem": "iOS", "sessions": "3", "conversions": "1"},
            {"operatingSystem": "Linux", "sessions": "2", "conversions": "0"},
        ],
        [],
    ]
    collect_ga4(db, site, WINDOW, fake, "call_click")
    db.flush()
    os = db.scalar(select(AxisSnapshot).where(AxisSnapshot.kind == "os"))
    assert os.data["rows"] == [
        {"os": "iOS", "sessions": 3, "conversions": 1},
        {"os": "Android", "sessions": 0, "conversions": 0},
        {"os": "other", "sessions": 2, "conversions": 0},
    ]
    calls = db.scalar(select(AxisSnapshot).where(AxisSnapshot.kind == "calls"))
    assert calls.data["count"] is None


AUDIT = f"URL,Inlinks,HTTP status code\nhttps://{DOMAIN}/,2,200\nhttps://{DOMAIN}/orphan,0,200\nhttps://{DOMAIN}/broken,1,404\n"


def test_internal_links_latest_upload_is_ready(get, db):
    site = db.scalar(select(Site).where(Site.domain == DOMAIN))
    import_csv(db, site, "internal-links", AUDIT)
    db.commit()
    result = get("internal-links")
    assert result["status"] == "ready"
    assert len(result["data"]["orphans"]) == len(result["data"]["broken_links"]) == 1
    assert result["data"]["inbound_distribution"][0] == {"inbound_links": 0, "pages": 1}


def test_site_links_partial_unknown_cells_and_no_site_leak(get, db, client, login_as):
    site = db.scalar(select(Site).where(Site.domain == DOMAIN))
    import_csv(
        db,
        site,
        "backlinks",
        f"Referring page URL,Target URL\nhttps://source.example/,https://{DOMAIN}/\n",
    )
    db.commit()
    result = get("site-links")
    assert result["status"] == "partial"
    assert len(result["data"]["sites"]) == 1  # viewer only sees Arlington
    assert "site2" not in str(result["data"])
    login_as("admin")
    result = get("site-links")
    assert len(result["data"]["sites"]) == 5
    assert any(cell["links"] is None for cell in result["data"]["matrix"])


def test_full_portfolio_exports_are_ready(client, login_as, db):
    login_as("admin")
    for i, site in enumerate(db.scalars(select(Site).order_by(Site.slug))):
        site.domain = f"real{i}.com"
        import_csv(
            db,
            site,
            "backlinks",
            f"Source URL,Target URL\nhttps://real0.com/a,https://{site.domain}/\n",
        )
    db.commit()
    result = client.get(f"{BASE}/site-links").json()
    assert result["status"] == "ready"
    assert len(result["data"]["matrix"]) == 25
    assert all(cell["links"] is not None for cell in result["data"]["matrix"])


def test_search_requests_keep_provider_null_and_opportunity(get, facts):
    result = get("search-requests")
    assert result["status"] == "partial"
    query = result["data"]["queries"][0]
    assert query["opportunity"] == 100
    assert query["volume"] is None and query["difficulty"] is None
    assert result["data"]["keyword_provider"]["status"] == "needs_setup"


def test_upload_auth_manager_origin_validation_and_latest(client, login_as):
    payload = {"kind": "internal-links", "csv": AUDIT}
    assert client.post(f"{BASE}/imports", json=payload).status_code == 401
    login_as()
    assert client.post(f"{BASE}/imports", json=payload).status_code == 403
    assert client.post("/api/sites/site2/axes/imports", json=payload).status_code == 404
    login_as("admin")
    assert (
        client.post(
            f"{BASE}/imports", json=payload, headers={"Origin": "https://evil.example"}
        ).status_code
        == 400
    )
    assert client.post(f"{BASE}/imports", json=payload).status_code == 201
    assert (
        client.post(f"{BASE}/imports", json={"kind": "internal-links", "csv": "bad"}).status_code
        == 422
    )


@pytest.mark.parametrize(
    "text",
    [
        "URL,Inlinks,HTTP status code\nhttps://evil.example/,0,200\n",
        f"URL,Inlinks,HTTP status code\nhttps://{DOMAIN}/,oops,200\n",
    ],
)
def test_bad_csv_is_not_stored(db, text):
    with pytest.raises(ValueError):
        import_csv(db, Site(domain=DOMAIN), "internal-links", text)
    assert list(db.scalars(select(AxisSnapshot))) == []


@pytest.mark.parametrize(
    "verdict,not_indexed,unknown",
    [
        ("FAIL", 1, 0),
        ("NEUTRAL", 1, 0),
        ("PARTIAL", 0, 1),
        ("VERDICT_UNSPECIFIED", 0, 1),
    ],
)
def test_index_verdicts_do_not_confuse_excluded_and_unknown(get, db, verdict, not_indexed, unknown):
    db.add(AxisSnapshot(site=DOMAIN, kind="sitemaps", data={"submitted": 1}))
    db.add(GscIndexStatus(site=DOMAIN, url=f"https://{DOMAIN}/x", verdict=verdict))
    db.commit()
    data = get("sitemaps")["data"]
    assert data["not_indexed"] == not_indexed
    assert data["unknown"] == unknown
