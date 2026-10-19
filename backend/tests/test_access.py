import pytest
from sqlalchemy import delete, select

from app.models import Site, User, UserSite


def test_sites_requires_session(client):
    assert client.get("/api/sites").status_code == 401
    assert client.get("/_test/sites/arlington").status_code == 401


def test_viewer_lists_only_arlington(client, login_as):
    login_as()
    response = client.get("/api/sites")
    assert response.status_code == 200
    assert response.json() == [
        {
            "slug": "arlington",
            "domain": "arlington247lockrepair.com",
            "display_name": "Arlington",
        }
    ]


@pytest.mark.parametrize("slug", ["site2", "site3", "site4", "site5", "missing"])
def test_viewer_direct_url_returns_404(client, login_as, slug):
    login_as()
    response = client.get(f"/_test/sites/{slug}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Site not found"}


def test_viewer_can_access_linked_site(client, login_as):
    login_as()
    assert client.get("/_test/sites/arlington").json() == {"slug": "arlington"}


def test_admin_sees_all_sites_without_links(client, login_as, db):
    admin = db.scalar(select(User).where(User.role == "admin"))
    db.execute(delete(UserSite).where(UserSite.user_id == admin.id))
    db.commit()
    login_as("admin")
    response = client.get("/api/sites")
    assert response.status_code == 200
    assert [site["slug"] for site in response.json()] == [
        "arlington",
        "site2",
        "site3",
        "site4",
        "site5",
    ]
    assert client.get("/_test/sites/site2").status_code == 200
    assert client.get("/_test/sites/missing").status_code == 404


def test_access_changes_take_effect_on_existing_session(client, login_as, db):
    login_as()
    arlington = db.scalar(select(Site).where(Site.slug == "arlington"))
    viewer = db.scalar(select(User).where(User.role == "viewer"))
    db.execute(
        delete(UserSite).where(UserSite.user_id == viewer.id, UserSite.site_id == arlington.id)
    )
    db.commit()
    assert client.get("/_test/sites/arlington").status_code == 404
    assert client.get("/api/sites").json() == []
