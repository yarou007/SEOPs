from uuid import uuid4

import pytest
from fastapi import HTTPException
from itsdangerous import TimestampSigner, URLSafeTimedSerializer
from sqlalchemy import select

from app.auth import LoginRateLimiter, session_serializer
from app.config import get_settings
from app.models import User


def test_login_and_me(client, login_as):
    response = login_as()
    assert set(response.json()) == {"id", "email", "role"}
    assert response.json()["email"] == "viewer@example.com"
    cookie = response.headers["set-cookie"]
    for flag in ["HttpOnly", "Secure", "SameSite=lax", "Max-Age=1209600", "Path=/"]:
        assert flag in cookie
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == response.json()
    assert me.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("email", ["viewer@example.com", "missing@example.com"])
def test_invalid_credentials_are_generic(client, email):
    response = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert "set-cookie" not in response.headers


def test_login_normalizes_email_case(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "VIEWER@example.com",
            "password": "viewer-test-password",
        },
    )
    assert response.status_code == 200


def test_me_requires_session(client):
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("token", ["garbage", "", session_serializer().dumps(str(uuid4()))])
def test_invalid_or_deleted_user_session(client, token):
    client.cookies.set("seops_session", token)
    assert client.get("/api/auth/me").status_code == 401


def test_tampered_session(client, login_as):
    login_as()
    token = client.cookies.get("seops_session")
    client.cookies.clear()
    client.cookies.set("seops_session", token + "tampered")
    assert client.get("/api/auth/me").status_code == 401


def test_expired_session(client, db):
    class OldSigner(TimestampSigner):
        def get_timestamp(self):
            return super().get_timestamp() - 1209601

    user = db.scalar(select(User).where(User.role == "viewer"))
    serializer = session_serializer()
    expired = URLSafeTimedSerializer(
        get_settings().session_secret.get_secret_value(),
        salt=serializer.salt,
        signer=OldSigner,
        signer_kwargs=serializer.signer_kwargs,
    ).dumps(str(user.id))
    client.cookies.set("seops_session", expired)
    assert client.get("/api/auth/me").status_code == 401


def test_logout_clears_cookie(client, login_as):
    login_as()
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/logout").status_code == 204


def test_login_rate_limit(client):
    for _ in range(10):
        assert (
            client.post(
                "/api/auth/login",
                json={
                    "email": "viewer@example.com",
                    "password": "wrong",
                },
            ).status_code
            == 401
        )
    response = client.post(
        "/api/auth/login",
        json={
            "email": "viewer@example.com",
            "password": "viewer-test-password",
        },
    )
    assert response.status_code == 429
    assert 0 < int(response.headers["retry-after"]) <= 900


def test_rate_limit_is_per_ip_and_expires(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.auth.monotonic", lambda: now[0])
    limiter = LoginRateLimiter()
    for _ in range(10):
        limiter.check("192.0.2.1")
    limiter.check("192.0.2.2")
    with pytest.raises(HTTPException) as error:
        limiter.check("192.0.2.1")
    assert error.value.status_code == 429
    now[0] += 900
    limiter.check("192.0.2.1")


def test_untrusted_auth_origin(client):
    response = client.post(
        "/api/auth/login",
        headers={"Origin": "https://untrusted.example"},
        json={"email": "viewer@example.com", "password": "viewer-test-password"},
    )
    assert response.status_code == 400
    assert (
        client.post(
            "/api/auth/logout",
            headers={
                "Origin": "https://untrusted.example",
            },
        ).status_code
        == 400
    )


def test_cors_allows_configured_frontend(client, login_as):
    login_as()
    response = client.get("/api/auth/me", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
