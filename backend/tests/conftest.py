import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
env_file = dotenv_values(BACKEND / ".env")
TEST_DATABASE_URL = (
    os.getenv("TEST_DATABASE_URL")
    or env_file.get("TEST_DATABASE_URL")
    or ("postgresql+psycopg://seops:seops@localhost:5432/seops_test")
)
SCHEMA = f"test_{uuid4().hex}"
test_url = make_url(TEST_DATABASE_URL)
existing_options = test_url.query.get("options", "")
os.environ["DATABASE_URL"] = test_url.update_query_dict(
    {
        "options": f"{existing_options} -csearch_path={SCHEMA}".strip(),
    }
).render_as_string(hide_password=False)
os.environ["SESSION_SECRET"] = "test-only-session-secret-with-at-least-32-characters"
os.environ["SESSION_COOKIE_NAME"] = "seops_session"
os.environ["SESSION_MAX_AGE_SECONDS"] = "1209600"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ["SEED_ADMIN_EMAIL"] = "admin@example.com"
os.environ["SEED_ADMIN_PASSWORD"] = "admin-test-password"
os.environ["SEED_VIEWER_EMAIL"] = "viewer@example.com"
os.environ["SEED_VIEWER_PASSWORD"] = "viewer-test-password"

# Configure the isolated test schema before importing the application's engine.
from app.access import AccessibleSite  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from scripts.seed import seed  # noqa: E402


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", *args],
        cwd=BACKEND,
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture(scope="session", autouse=True)
def migrated_schema():
    """Run actual migrations in an empty private schema; never create_all()."""
    admin_engine = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{SCHEMA}"')
    try:
        run_cli("alembic", "upgrade", "head")
        yield
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{SCHEMA}" CASCADE')
        admin_engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(migrated_schema):
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "TRUNCATE user_sites, users, sites, gsc_daily, gsc_sync_log, ga4_daily, ga4_sync_log"
        )


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def seeded():
    seed()


@pytest.fixture
def client(seeded):
    app = create_app()

    # Exercise direct-URL authorization without shipping a site detail/read endpoint.
    @app.get("/_test/sites/{slug}", include_in_schema=False)
    def protected_site(site: AccessibleSite):
        return {"slug": site.slug}

    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def login_as(client):
    def login(role="viewer"):
        response = client.post(
            "/api/auth/login",
            json={
                "email": f"{role}@example.com",
                "password": f"{role}-test-password",
            },
        )
        assert response.status_code == 200
        return response

    return login
