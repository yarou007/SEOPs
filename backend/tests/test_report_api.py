from datetime import date

import pytest
from sqlalchemy import func, select

from app.analysis.weekly import build_report, save_report
from app.models import Site, WeeklyReport


def report(db, day: str, slug: str = "arlington", **extra) -> dict:
    site = db.scalar(select(Site).where(Site.slug == slug))
    return {**build_report(db, site, as_of=date.fromisoformat(day)), **extra}


@pytest.fixture
def store(client, db):
    def save(day: str, **extra):
        save_report(db, report(db, day, **extra))

    return save


def test_latest_report_uses_latest_stored_date(client, login_as, store):
    login_as()
    for day in ["2026-10-19", "2026-10-12"]:
        store(day)
    response = client.get("/api/sites/arlington/report/latest")
    assert response.status_code == 200
    assert response.json()["report_date"] == "2026-10-19"
    assert response.headers["cache-control"] == "no-store"


def test_saving_same_day_replaces_report_and_keeps_markdown(db, client, store):
    store("2026-10-19", flagged_pages_count=1)
    store("2026-10-19", flagged_pages_count=2)
    rows = db.scalars(select(WeeklyReport)).all()
    assert len(rows) == 1
    assert rows[0].report["flagged_pages_count"] == 2
    assert rows[0].report_date == date(2026, 10, 19)
    assert rows[0].markdown.startswith("#")


def test_report_requires_login(client):
    assert client.get("/api/sites/arlington/report/latest").status_code == 401


@pytest.mark.parametrize("slug", ["site2", "missing"])
def test_report_hides_unlinked_and_missing_sites(client, login_as, slug):
    login_as()
    response = client.get(f"/api/sites/{slug}/report/latest")
    assert response.status_code == 404
    assert response.json() == {"detail": "Site not found"}


def test_missing_report_returns_404(client, login_as):
    login_as()
    assert client.get("/api/sites/arlington/report/latest").json() == {
        "detail": "Weekly report not found"
    }


def test_report_of_another_site_is_not_returned(client, login_as, db):
    login_as()
    save_report(db, report(db, "2026-10-19", slug="site2"))
    assert client.get("/api/sites/arlington/report/latest").status_code == 404
    assert db.scalar(select(func.count()).select_from(WeeklyReport)) == 1
