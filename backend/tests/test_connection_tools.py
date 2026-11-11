"""Setup helpers: list the Google properties the service account sees, test saved ones."""

import pytest

from app import google_admin

OPTIONS = "/api/sites/arlington/connection/options"
TEST = "/api/sites/arlington/connection/test"


@pytest.fixture
def fake_google(monkeypatch):
    calls = {}

    def gsc(path):
        return ["https://www.example.com/", "sc-domain:arlington247lockrepair.com"]

    def ga4(path):
        return [{"id": "123", "name": "Arlington", "account": "Agency"}]

    def test_gsc(path, prop):
        calls["gsc"] = prop
        return True, "Search Console answered for sc-domain:arlington247lockrepair.com."

    def test_ga4(path, prop):
        calls["ga4"] = prop
        return False, google_admin.GA4_TEST_FAILED

    monkeypatch.setattr(google_admin, "list_gsc_properties", gsc)
    monkeypatch.setattr(google_admin, "list_ga4_properties", ga4)
    monkeypatch.setattr(google_admin, "test_gsc", test_gsc)
    monkeypatch.setattr(google_admin, "test_ga4", test_ga4)
    return calls


def test_options_lists_everything_for_a_manager(client, login_as, fake_google):
    assert client.get(OPTIONS).status_code == 401
    login_as("admin")
    assert client.get(OPTIONS).json() == {
        "gsc": {
            "properties": ["https://www.example.com/", "sc-domain:arlington247lockrepair.com"],
            "error": None,
        },
        "ga4": {
            "properties": [{"id": "123", "name": "Arlington", "account": "Agency"}],
            "error": None,
        },
    }


def test_options_and_test_are_manager_only(client, login_as, fake_google):
    login_as()  # the viewer can read arlington but did not create it
    assert client.get(OPTIONS).status_code == 403
    assert client.post(TEST).status_code == 403
    assert client.get("/api/sites/site2/connection/options").status_code == 404


def test_listing_failure_returns_safe_message(client, login_as, monkeypatch):
    def broken(path):
        raise RuntimeError("secret /path/key.json token=abc")

    monkeypatch.setattr(google_admin, "_gsc_service", broken)
    monkeypatch.setattr(google_admin, "_ga4_admin_service", broken)
    login_as("admin")
    body = client.get(OPTIONS).json()
    assert body["gsc"] == {"properties": [], "error": google_admin.GSC_LIST_FAILED}
    assert body["ga4"] == {"properties": [], "error": google_admin.GA4_LIST_FAILED}
    assert "secret" not in str(body) and "key.json" not in str(body)


def test_test_uses_saved_properties(client, login_as, fake_google, db):
    from sqlalchemy import select

    from app.models import Site

    site = db.scalar(select(Site).where(Site.slug == "arlington"))
    site.gsc_property, site.ga4_property_id = "sc-domain:arlington247lockrepair.com", None
    db.commit()
    login_as("admin")
    assert client.post(TEST, headers={"Origin": "https://evil.example"}).status_code == 400
    body = client.post(TEST).json()
    assert body["gsc"]["ok"] is True
    assert body["ga4"] == {"ok": False, "message": "Not set up"}
    assert fake_google == {"gsc": "sc-domain:arlington247lockrepair.com"}


def test_gsc_test_failure_is_safe(monkeypatch):
    class Broken:
        def __init__(self, path):
            pass

        def query(self, *args, **kwargs):
            raise RuntimeError("boom /secret")

    monkeypatch.setattr(google_admin, "GscClient", Broken)
    assert google_admin.test_gsc(None, "sc-domain:x.com") == (False, google_admin.GSC_TEST_FAILED)


def test_ga4_listing_pages_and_shapes(monkeypatch):
    pages = [
        {
            "accountSummaries": [
                {
                    "displayName": "Agency",
                    "propertySummaries": [{"property": "properties/42", "displayName": "B site"}],
                }
            ],
            "nextPageToken": "t",
        },
        {
            "accountSummaries": [
                {
                    "displayName": "Other",
                    "propertySummaries": [{"property": "properties/7", "displayName": "A site"}],
                }
            ]
        },
    ]

    class Request:
        def __init__(self, page):
            self.page = page

        def execute(self, num_retries=0):
            return self.page

    class Summaries:
        def list(self, pageSize, pageToken=None):
            return Request(pages[1] if pageToken else pages[0])

    class Service:
        def accountSummaries(self):
            return Summaries()

    monkeypatch.setattr(google_admin, "_ga4_admin_service", lambda path: Service())
    assert google_admin.list_ga4_properties(None) == [
        {"id": "7", "name": "A site", "account": "Other"},
        {"id": "42", "name": "B site", "account": "Agency"},
    ]
