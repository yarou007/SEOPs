from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import select

from app.auth import CurrentUser
from app.db import DbSession
from app.models import Site, UserSite


def get_site_for_user(slug: str, db: DbSession, user: CurrentUser) -> Site:
    statement = select(Site).where(Site.slug == slug)
    if user.role != "admin":
        statement = statement.join(UserSite).where(UserSite.user_id == user.id)
    site = db.scalar(statement)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


AccessibleSite = Annotated[Site, Depends(get_site_for_user)]
