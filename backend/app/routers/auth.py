from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select

from app.auth import (
    CurrentUser,
    check_auth_origin,
    clear_session_cookie,
    limit_login,
    password_hasher,
    set_session_cookie,
    verify_password,
)
from app.db import DbSession
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    role: str


@router.post(
    "/login",
    response_model=UserResponse,
    dependencies=[Depends(limit_login), Depends(check_auth_origin)],
)
def login(payload: LoginRequest, response: Response, db: DbSession) -> User:
    user = db.scalar(select(User).where(User.email == str(payload.email).casefold()))
    if not verify_password(payload.password, user.password_hash if user else None):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    assert user is not None
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(payload.password)
        db.commit()
    set_session_cookie(response, user)
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout", status_code=204, dependencies=[Depends(check_auth_origin)])
def logout() -> Response:
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    clear_session_cookie(response)
    return response


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser, response: Response) -> User:
    response.headers["Cache-Control"] = "no-store"
    return user
