from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import Ga4Daily, Ga4SyncLog, GscDaily, GscSyncLog, Site, User, UserSite
from app.site_management import CredentialInfo, credential_info
from app.site_sync import SyncJobs
from app.sync.common import today_in
from app.sync.ga4_client import FakeGa4Client
from app.sync.gsc_client import FakeGscClient

NEW_SITE = {
    "display_name": "My Website",
    "domain": "https://EXAMPLE.com/",
    "gsc_property": "sc-domain:example.com",
    "ga4_property_id": "987654321",
}


@pytest.fixture
def owned(client, login_as):
    login_as()
    response = client.post("/api/sites", json=NEW_SITE)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def ready(monkeypatch, tmp_path):
    info = {
        source: CredentialInfo(
            configured=True,
            service_account_email=f"{source}@test.iam.gserviceaccount.com",
            message="Ready",
        )
        for source in ["gsc", "ga4"]
    }
    monkeypatch.setattr("app.routers.sites.setup_info", lambda settings: info)
    settings = get_settings().model_copy(update={"reports_dir": tmp_path})
    monkeypatch.setattr("app.routers.sites.get_settings", lambda: settings)
    monkeypatch.setattr("app.site_sync.GscClient", lambda path: FakeGscClient())
    monkeypatch.setattr("app.site_sync.Ga4Client", lambda path: FakeGa4Client())
    return tmp_path


def test_add_requires_session_and_checks_origin(client, login_as):
    assert client.post("/api/sites", json=NEW_SITE).status_code == 401
    login_as()
    assert (
        client.post(
            "/api/sites", json=NEW_SITE, headers={"Origin": "https://evil.example"}
        ).status_code
        == 400
    )
    assert client.get("/api/sites").json()[0]["slug"] == "arlington"


def test_viewer_adds_own_site_without_expanding_other_access(client, owned, db):
    assert owned == {"slug": "example-com", "domain": "example.com", "display_name": "My Website"}
    viewer = db.scalar(select(User).where(User.role == "viewer"))
    site = db.scalar(select(Site).where(Site.slug == owned["slug"]))
    assert site.created_by_user_id == viewer.id
    assert db.get(UserSite, (viewer.id, site.id)) is not None
    assert [site["slug"] for site in client.get("/api/sites").json()] == [
        "arlington",
        "example-com",
    ]
    assert client.get("/api/sites/site2/connection").status_code == 404
    assert client.get("/api/sites/example-com/summary").json()["current"] == {
        "gsc": None,
        "ga4": None,
    }
    assert client.get("/api/sites/example-com/connection").json()["can_manage"] is True


@pytest.mark.parametrize("domain", ["example.com", "https://example.com/", "EXAMPLE.COM."])
def test_duplicate_domains_do_not_duplicate_or_grant_links(client, owned, db, domain):
    payload = {**NEW_SITE, "domain": domain}
    assert client.post("/api/sites", json=payload).status_code == 409
    assert db.scalar(select(func.count()).select_from(Site)) == 6


def test_existing_site_cannot_be_claimed_by_domain_or_ga4_id(client, login_as, db):
    login_as()
    response = client.post(
        "/api/sites", json={"display_name": "Claim", "domain": "TODO-site2.example"}
    )
    assert response.status_code == 409
    assert client.get("/api/sites/site2/connection").status_code == 404
    site = db.scalar(select(Site).where(Site.slug == "site2"))
    site.ga4_property_id = "987654321"
    db.commit()
    assert client.post("/api/sites", json=NEW_SITE).status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"domain": "http://user:pass@example.com"},
        {"domain": "https://example.com/some-page"},
        {"domain": "localhost"},
        {"domain": "127.0.0.1"},
        {"domain": "example.com:1234"},
        {"domain": "ftp://example.com"},
        {"domain": "bad domain.com"},
        {"domain": "example..com"},
        {"gsc_property": "sc-domain:someone-else.com"},
        {"gsc_property": "https://someone-else.com/"},
        {"gsc_property": "ftp://example.com/"},
        {"ga4_property_id": "G-ABC123"},
        {"ga4_property_id": "properties/123"},
        {"display_name": " "},
        {"active": True},
        {"created_by_user_id": "anything"},
    ],
)
def test_reject_invalid_site_input(client, login_as, changes):
    login_as()
    assert client.post("/api/sites", json={**NEW_SITE, **changes}).status_code == 422


def test_idna_domain_and_parent_gsc_property(client, login_as):
    login_as()
    response = client.post(
        "/api/sites",
        json={
            "display_name": "International",
            "domain": "https://bücher.example/",
            "gsc_property": "sc-domain:bücher.example",
        },
    )
    assert response.status_code == 201
    assert response.json()["domain"] == "xn--bcher-kva.example"
    response = client.post(
        "/api/sites",
        json={
            "display_name": "WWW",
            "domain": "www.example.com",
            "gsc_property": "sc-domain:example.com",
        },
    )
    assert response.status_code == 201


def test_slug_collision_keeps_distinct_websites(client, owned):
    response = client.post(
        "/api/sites", json={"display_name": "Different", "domain": "example-com.net"}
    )
    assert response.status_code == 201
    # Two domains can have the same punctuation-stripped slug.
    first = client.post(
        "/api/sites", json={"display_name": "First", "domain": "foo-bar.example"}
    ).json()
    second = client.post(
        "/api/sites", json={"display_name": "Second", "domain": "foo.bar.example"}
    ).json()
    assert first["slug"] != second["slug"]


def test_viewing_shared_site_does_not_grant_management(client, login_as):
    login_as()
    assert client.get("/api/sites/arlington/connection").json()["can_manage"] is False
    assert (
        client.post(
            "/api/sites/arlington/connection",
            json={"gsc_property": "sc-domain:arlington247lockrepair.com"},
        ).status_code
        == 403
    )
    assert client.post("/api/sites/arlington/sync").status_code == 403
    assert client.post("/api/sites/site2/sync").status_code == 404
    assert client.post("/api/sites/missing/connection", json={}).status_code == 404


def test_owner_can_save_connections_but_not_domain(client, owned):
    response = client.post(
        "/api/sites/example-com/connection",
        json={"gsc_property": "https://example.com/", "ga4_property_id": ""},
    )
    assert response.status_code == 200
    assert response.json()["gsc_property"] == "https://example.com/"
    assert response.json()["ga4_property_id"] is None
    assert (
        client.post("/api/sites/example-com/connection", json={"domain": "other.com"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/sites/example-com/connection", json={"gsc_property": "sc-domain:other.com"}
        ).status_code
        == 422
    )


def test_admin_can_manage_without_site_links(client, login_as):
    login_as("admin")
    assert client.get("/api/sites/site2/connection").json()["can_manage"] is True
    assert (
        client.post("/api/sites/site2/connection", json={"ga4_property_id": "123456"}).status_code
        == 200
    )


def test_cannot_replace_imported_property_or_modify_running_site(client, owned, db):
    site = db.scalar(select(Site).where(Site.slug == "example-com"))
    db.add(GscSyncLog(site=site.domain, last_loaded_date=today_in("UTC"), status="ok"))
    db.commit()
    assert (
        client.post(
            "/api/sites/example-com/connection", json={"gsc_property": "https://example.com/"}
        ).status_code
        == 409
    )
    client.app.state.sync_jobs.start(site.id)
    assert (
        client.post(
            "/api/sites/example-com/connection",
            json={"gsc_property": "sc-domain:example.com", "ga4_property_id": "987654321"},
        ).status_code
        == 409
    )


def test_sync_requires_properties_and_real_credentials(client, owned, monkeypatch):
    monkeypatch.setattr(
        "app.routers.sites.setup_info",
        lambda settings: {
            source: CredentialInfo(configured=False, message="Missing") for source in ["gsc", "ga4"]
        },
    )
    assert client.post("/api/sites/example-com/sync").status_code == 503
    assert client.get("/api/sites/example-com/connection").json()["sync"]["running"] is False
    assert client.post("/api/sites/example-com/connection", json={}).status_code == 200
    assert client.post("/api/sites/example-com/sync").status_code == 422


def test_sync_uses_existing_pipelines_and_updates_report(client, owned, ready, db, monkeypatch):
    monkeypatch.setenv("SYNC_FAKE_CLIENT", "1")
    # Only this test's injected clients can generate rows; the endpoint ignores the CLI flag.
    end = today_in("UTC") - timedelta(days=get_settings().sync_lag_days)
    for model in [GscSyncLog, Ga4SyncLog]:
        db.add(model(site="example.com", last_loaded_date=end - timedelta(days=2), status="ok"))
    db.commit()
    response = client.post("/api/sites/example-com/sync")
    assert response.status_code == 202
    assert response.json()["running"] is True
    result = client.get("/api/sites/example-com/connection").json()["sync"]
    assert result["running"] is False
    assert result["results"]["gsc"]["rows_loaded"] == 12
    assert result["results"]["ga4"]["rows_loaded"] == 2
    assert result["results"]["report"]["status"] == "ok"
    assert db.scalar(select(func.count()).select_from(GscDaily)) == 12
    assert db.scalar(select(func.count()).select_from(Ga4Daily)) == 2
    assert db.get(GscSyncLog, "example.com").last_loaded_date == end
    assert (ready / "example-com").is_dir()
    assert client.post("/api/sites/example-com/sync").status_code == 202
    assert db.scalar(select(func.count()).select_from(GscDaily)) == 12


def test_sync_continues_when_one_source_fails(client, owned, ready, monkeypatch):
    class BrokenGsc:
        def query(self, *args, **kwargs):
            raise RuntimeError("Google permission denied")

    monkeypatch.setattr("app.site_sync.GscClient", lambda path: BrokenGsc())
    assert client.post("/api/sites/example-com/sync").status_code == 202
    result = client.get("/api/sites/example-com/connection").json()["sync"]["results"]
    assert result["gsc"]["status"] == "error"
    assert result["ga4"]["status"] == "ok"
    status = client.get("/api/sites/example-com/status").json()
    assert status["gsc"]["status"] == "error"
    assert status["gsc"]["last_loaded_date"] is None
    assert status["ga4"]["last_loaded_date"] is not None


def test_no_fake_fallback_when_real_client_fails(client, owned, ready, monkeypatch):
    monkeypatch.setenv("SYNC_FAKE_CLIENT", "1")

    def fail(*args, **kwargs):
        raise RuntimeError("Credentials unavailable")

    monkeypatch.setattr("app.site_sync.gsc.sync_site", fail)
    monkeypatch.setattr("app.site_sync.ga4.sync_site", fail)
    assert client.post("/api/sites/example-com/sync").status_code == 202
    results = client.get("/api/sites/example-com/connection").json()["sync"]["results"]
    assert results["gsc"]["status"] == results["ga4"]["status"] == "error"


def test_duplicate_sync_and_capacity_rejected(client, owned, ready, db):
    site = db.scalar(select(Site).where(Site.slug == "example-com"))
    jobs = client.app.state.sync_jobs
    jobs.start(site.id)
    assert client.post("/api/sites/example-com/sync").status_code == 409
    site2 = db.scalar(select(Site).where(Site.slug == "site2"))
    site3 = db.scalar(select(Site).where(Site.slug == "site3"))
    jobs.start(site2.id)
    with pytest.raises(ValueError, match="Two website syncs"):
        jobs.start(site3.id)


def test_setup_requires_session_and_never_exposes_credential_contents(
    client, login_as, tmp_path, monkeypatch
):
    assert client.get("/api/sites/setup").status_code == 401
    login_as()
    path = tmp_path / "secret.json"
    path.write_text('{"private_key":"never-return-this-value"}')
    settings = get_settings().model_copy(
        update={"gsc_service_account_file": path, "ga4_service_account_file": path}
    )
    monkeypatch.setattr("app.routers.sites.get_settings", lambda: settings)
    response = client.get("/api/sites/setup")
    assert response.json()["gsc"]["configured"] is False
    assert "never-return-this-value" not in response.text
    assert str(path) not in response.text
    assert response.headers["cache-control"] == "no-store"
    monkeypatch.setattr(
        "app.site_management.service_account.Credentials.from_service_account_file",
        lambda path: SimpleNamespace(service_account_email="public@test.iam.gserviceaccount.com"),
    )
    assert (
        client.get("/api/sites/setup").json()["gsc"]["service_account_email"]
        == "public@test.iam.gserviceaccount.com"
    )


def test_unavailable_credential_file_has_safe_message():
    info = credential_info(Path("/not/a/real/private-credentials.json"), "GSC_SERVICE_ACCOUNT_FILE")
    assert info.configured is False
    assert "private-credentials" not in info.message
    assert credential_info(None, "GSC_SERVICE_ACCOUNT_FILE").configured is False


def test_sync_registry_can_resume_after_job_finishes():
    from uuid import uuid4

    jobs = SyncJobs()
    site_id = uuid4()
    jobs.start(site_id)
    jobs.finish(site_id, {})
    assert jobs.start(site_id).running is True
