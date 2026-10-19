from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.auth import CurrentUser
from app.db import DbSession
from app.models import Site, UserSite

router = APIRouter(prefix="/api/sites", tags=["sites"])


class SiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    domain: str
    display_name: str


@router.get("", response_model=list[SiteResponse])
def list_sites(db: DbSession, user: CurrentUser, response: Response) -> list[Site]:
    statement = select(Site).order_by(Site.slug)
    if user.role != "admin":
        statement = statement.join(UserSite).where(UserSite.user_id == user.id)
    response.headers["Cache-Control"] = "no-store"
    return list(db.scalars(statement))
