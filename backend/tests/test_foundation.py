import pytest
from conftest import run_cli
from pydantic import ValidationError
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db import engine
from app.models import Site, User, UserSite


def test_migration_round_trip_on_empty_schema():
    expected = {
        "users",
        "sites",
        "user_sites",
        "gsc_daily",
        "gsc_sync_log",
        "ga4_daily",
        "ga4_sync_log",
        "alembic_version",
    }
    assert set(inspect(engine).get_table_names()) == expected
    run_cli("alembic", "downgrade", "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    run_cli("alembic", "upgrade", "head")
    assert set(inspect(engine).get_table_names()) == expected
    run_cli("alembic", "check")


def test_seed_cli_runs_twice_and_preserves_existing_data(db, monkeypatch):
    run_cli("scripts.seed")
    viewer = db.scalar(select(User).where(User.role == "viewer"))
    original_hash = viewer.password_hash
    site2 = db.scalar(select(Site).where(Site.slug == "site2"))
    site2.domain = "updated.example"
    db.commit()
    monkeypatch.setenv("SEED_VIEWER_PASSWORD", "a-new-value-should-not-reset-the-password")
    run_cli("scripts.seed")
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(User)) == 2
    assert db.scalar(select(func.count()).select_from(Site)) == 5
    assert db.scalar(select(func.count()).select_from(UserSite)) == 6
    assert viewer.password_hash == original_hash
    assert site2.domain == "updated.example"
    viewer_sites = db.scalars(select(Site.slug).join(UserSite).where(UserSite.user_id == viewer.id))
    assert list(viewer_sites) == ["arlington"]


def test_role_constraint_and_cascade_delete(db, seeded):
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE users SET role = 'owner'"))
        db.commit()
    db.rollback()
    viewer = db.scalar(select(User).where(User.role == "viewer"))
    db.delete(viewer)
    db.commit()
    assert db.scalar(select(func.count()).select_from(UserSite)) == 5
    site = db.scalar(select(Site).where(Site.slug == "arlington"))
    db.delete(site)
    db.commit()
    assert db.scalar(select(func.count()).select_from(UserSite)) == 4


def test_docs_list_only_foundation_routes(client):
    assert client.get("/docs").status_code == 200
    assert set(client.get("/openapi.json").json()["paths"]) == {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
        "/api/sites",
    }


def test_placeholder_session_secret_is_rejected():
    with pytest.raises(ValidationError):
        Settings(session_secret="change-me", _env_file=None)
