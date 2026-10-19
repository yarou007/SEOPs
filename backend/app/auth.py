import hashlib
import math
from collections import deque
from threading import Lock
from time import monotonic
from typing import Annotated
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import APIKeyCookie
from itsdangerous import BadData, URLSafeTimedSerializer

from app.config import get_settings
from app.db import DbSession
from app.models import User

password_hasher = PasswordHasher()
_dummy_hash = password_hasher.hash("dummy-password-for-unknown-users")
session_cookie = APIKeyCookie(name=get_settings().session_cookie_name, auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        valid = password_hasher.verify(password_hash or _dummy_hash, password)
        return valid and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def session_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        get_settings().session_secret.get_secret_value(),
        salt="seops.session.v1",
        signer_kwargs={"digest_method": hashlib.sha256},
    )


def set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        session_serializer().dumps(str(user.id)),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        get_settings().session_cookie_name,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(session_cookie)],
) -> User:
    unauthorized = HTTPException(status_code=401, detail="Not authenticated")
    if not token:
        raise unauthorized
    try:
        user_id = UUID(
            session_serializer().loads(
                token,
                max_age=get_settings().session_max_age_seconds,
            )
        )
    except (BadData, ValueError, TypeError, AttributeError):
        raise unauthorized from None
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class LoginRateLimiter:
    """Thread-safe sliding window, local to this application process."""

    def __init__(self, limit: int = 10, window_seconds: int = 900):
        self.limit = limit
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = {}
        self._lock = Lock()
        self._last_cleanup = 0.0

    def check(self, ip: str) -> None:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            if now - self._last_cleanup >= 60:
                self._attempts = {
                    key: attempts
                    for key, attempts in self._attempts.items()
                    if attempts and attempts[-1] > cutoff
                }
                self._last_cleanup = now
            attempts = self._attempts.setdefault(ip, deque())
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= self.limit:
                retry_after = max(1, math.ceil(attempts[0] + self.window_seconds - now))
                raise HTTPException(
                    status_code=429,
                    detail="Too many login attempts",
                    headers={"Retry-After": str(retry_after)},
                )
            attempts.append(now)


def limit_login(request: Request) -> None:
    # Forwarded headers must only be resolved by Uvicorn for explicitly trusted proxies.
    ip = request.client.host if request.client else "unknown"
    request.app.state.login_limiter.check(ip)


def check_auth_origin(request: Request) -> None:
    """Reject browser auth POSTs from untrusted origins; allow non-browser clients."""
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().allowed_origins + [
        str(request.base_url).rstrip("/")
    ]:
        raise HTTPException(status_code=400, detail="Untrusted request origin")
