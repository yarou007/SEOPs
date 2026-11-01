"""Axis reads use the same site access and date validation as analytics."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.access import AccessibleSite
from app.analysis import axes
from app.analysis.csv_sources import import_csv
from app.auth import CurrentUser, check_auth_origin
from app.db import DbSession
from app.routers.analytics import DateWindow, no_store
from app.routers.sites import require_manager

router = APIRouter(
    prefix="/api/sites/{slug}/axes", tags=["analysis axes"], dependencies=[Depends(no_store)]
)


class AxisResponse(BaseModel):
    status: Literal["ready", "partial", "needs_setup"]
    reason: str | None
    data: dict


@router.get("/impressions-clicks", response_model=AxisResponse)
def impressions_clicks(site: AccessibleSite, db: DbSession, window: DateWindow):
    return axes.impressions_clicks(db, site, window)


@router.get("/funnel", response_model=AxisResponse)
def funnel(site: AccessibleSite, db: DbSession, window: DateWindow):
    return axes.funnel(db, site, window)


@router.get("/devices", response_model=AxisResponse)
def devices(site: AccessibleSite, db: DbSession, window: DateWindow):
    return axes.devices(db, site, window)


@router.get("/geography", response_model=AxisResponse)
def geography(site: AccessibleSite, db: DbSession, window: DateWindow):
    return axes.geography(db, site, window)


@router.get("/sitemaps", response_model=AxisResponse)
def sitemaps(site: AccessibleSite, db: DbSession, window: DateWindow):
    return axes.sitemaps(db, site, window)


@router.get("/internal-links", response_model=AxisResponse)
def internal_links(site: AccessibleSite, db: DbSession, window: DateWindow):
    return axes.internal_links(db, site, window)


@router.get("/site-links", response_model=AxisResponse)
def site_links(site: AccessibleSite, db: DbSession, window: DateWindow, user: CurrentUser):
    return axes.site_links(db, site, window, user)


@router.get("/search-requests", response_model=AxisResponse)
def search_requests(site: AccessibleSite, db: DbSession, window: DateWindow):
    return axes.search_requests(db, site, window)


class CsvUpload(BaseModel):
    kind: Literal["internal-links", "backlinks"]
    csv: str = Field(min_length=1, max_length=2_000_000)


@router.post("/imports", status_code=201, dependencies=[Depends(check_auth_origin)])
def upload(payload: CsvUpload, site: AccessibleSite, user: CurrentUser, db: DbSession):
    require_manager(site, user)
    try:
        evidence = import_csv(db, site, payload.kind, payload.csv)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {"id": str(evidence.id), "kind": evidence.kind}
