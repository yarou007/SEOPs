import json

import pytest

from app.config import get_settings


@pytest.fixture
def report_dir(tmp_path, monkeypatch):
    settings = get_settings().model_copy(update={"reports_dir": tmp_path})
    monkeypatch.setattr("app.routers.analytics.get_settings", lambda: settings)
    directory = tmp_path / "arlington"
    directory.mkdir()
    return directory


def test_latest_report_uses_latest_dated_file(client, login_as, report_dir):
    login_as()
    for day in ["2026-10-19", "2026-10-12"]:
        (report_dir / f"{day}.json").write_text(
            json.dumps(
                {
                    "site": {"slug": "arlington"},
                    "report_date": day,
                    "top_pages": [],
                }
            )
        )
    (report_dir / "2026-99-99.json").write_text("{}")
    response = client.get("/api/sites/arlington/report/latest")
    assert response.status_code == 200
    assert response.json()["report_date"] == "2026-10-19"
    assert response.headers["cache-control"] == "no-store"


def test_report_requires_login(client):
    assert client.get("/api/sites/arlington/report/latest").status_code == 401


@pytest.mark.parametrize("slug", ["site2", "missing"])
def test_report_hides_unlinked_and_missing_sites(client, login_as, slug):
    login_as()
    response = client.get(f"/api/sites/{slug}/report/latest")
    assert response.status_code == 404
    assert response.json() == {"detail": "Site not found"}


def test_missing_report_returns_404(client, login_as, report_dir):
    login_as()
    assert client.get("/api/sites/arlington/report/latest").json() == {
        "detail": "Weekly report not found"
    }


@pytest.mark.parametrize("body", ["invalid JSON", '{"site":{"slug":"site2"}}'])
def test_invalid_report_returns_generic_error(client, login_as, report_dir, body):
    login_as()
    (report_dir / "2026-10-19.json").write_text(body)
    response = client.get("/api/sites/arlington/report/latest")
    assert response.status_code == 503
    assert response.json() == {"detail": "Stored weekly report is unavailable"}


def test_report_does_not_follow_symlink_outside_site_directory(client, login_as, report_dir):
    login_as()
    outside = report_dir.parent / "private.json"
    outside.write_text('{"secret":"not a report"}')
    (report_dir / "2026-10-19.json").symlink_to(outside)
    assert client.get("/api/sites/arlington/report/latest").status_code == 404
