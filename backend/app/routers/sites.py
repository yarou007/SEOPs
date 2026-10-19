import re
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.access import AccessibleSite
from app.auth import CurrentUser, check_auth_origin
from app.config import get_settings
from app.db import DbSession
from app.models import Ga4SyncLog, GscSyncLog, Site, User, UserSite
from app.site_management import ConnectionInput, CreateSiteInput, CredentialInfo, setup_info
from app.site_sync import SyncJob, run_site_sync

router = APIRouter(prefix="/api/sites", tags=["sites"])


class SiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    domain: str
    display_name: str


class SiteConnection(SiteResponse):
    gsc_property: str | None
    ga4_property_id: str | None
    can_manage: bool
    credentials: dict[str, CredentialInfo]
    sync: SyncJob


def require_manager(site: Site, user: User) -> None:
    if user.role != "admin" and site.created_by_user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the website's creator or an admin can manage its connections.",
        )


def connection_response(site: Site, user: User, request: Request) -> dict:
    return {
        "slug": site.slug,
        "domain": site.domain,
        "display_name": site.display_name,
        "gsc_property": site.gsc_property,
        "ga4_property_id": site.ga4_property_id,
        "can_manage": user.role == "admin" or site.created_by_user_id == user.id,
        "credentials": setup_info(get_settings()),
        "sync": request.app.state.sync_jobs.get(site.id),
    }


@router.get("", response_model=list[SiteResponse])
def list_sites(db: DbSession, user: CurrentUser, response: Response) -> list[Site]:
    statement = select(Site).order_by(Site.slug)
    if user.role != "admin":
        statement = statement.join(UserSite).where(UserSite.user_id == user.id)
    response.headers["Cache-Control"] = "no-store"
    return list(db.scalars(statement))


@router.get("/setup", response_model=dict[str, CredentialInfo])
def site_setup(user: CurrentUser, response: Response) -> dict[str, CredentialInfo]:
    response.headers["Cache-Control"] = "no-store"
    return setup_info(get_settings())


@router.post(
    "", response_model=SiteResponse, status_code=201, dependencies=[Depends(check_auth_origin)]
)
def create_site(
    payload: CreateSiteInput, db: DbSession, user: CurrentUser, response: Response
) -> Site:
    if db.scalar(select(Site.id).where(func.lower(Site.domain) == payload.domain)):
        raise HTTPException(
            status_code=409,
            detail="This website is already registered. Ask your administrator for access.",
        )
    if payload.ga4_property_id and db.scalar(
        select(Site.id).where(Site.ga4_property_id == payload.ga4_property_id)
    ):
        raise HTTPException(
            status_code=409,
            detail="This GA4 property is already connected. Contact your administrator.",
        )
    slug = re.sub(r"[^a-z0-9]+", "-", payload.domain).strip("-")[:70]
    if db.scalar(select(Site.id).where(Site.slug == slug)):
        slug = f"{slug}-{uuid4().hex[:8]}"
    site = Site(
        slug=slug,
        domain=payload.domain,
        display_name=payload.display_name,
        gsc_property=payload.gsc_property,
        ga4_property_id=payload.ga4_property_id,
        created_by_user_id=user.id,
    )
    db.add(site)
    try:
        db.flush()
        db.add(UserSite(user_id=user.id, site_id=site.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This website is already registered. Ask your administrator for access.",
        ) from None
    response.headers["Cache-Control"] = "no-store"
    return site


@router.get("/{slug}/connection", response_model=SiteConnection)
def get_connection(
    site: AccessibleSite, user: CurrentUser, request: Request, response: Response
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return connection_response(site, user, request)


@router.post(
    "/{slug}/connection", response_model=SiteConnection, dependencies=[Depends(check_auth_origin)]
)
def save_connection(
    payload: ConnectionInput,
    site: AccessibleSite,
    db: DbSession,
    user: CurrentUser,
    request: Request,
    response: Response,
) -> dict:
    require_manager(site, user)
    try:
        payload.check_domain(site.domain)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if payload.ga4_property_id and db.scalar(
        select(Site.id).where(Site.ga4_property_id == payload.ga4_property_id, Site.id != site.id)
    ):
        raise HTTPException(
            status_code=409,
            detail="This GA4 property is already connected. Contact your administrator.",
        )
    # Serialize settings changes with starts in this API process.
    jobs = request.app.state.sync_jobs
    with jobs.lock:
        if jobs.jobs.get(site.id, SyncJob()).running:
            raise HTTPException(
                status_code=409,
                detail="Wait for the current sync to finish before changing connections.",
            )
        for field, model in [("gsc_property", GscSyncLog), ("ga4_property_id", Ga4SyncLog)]:
            if getattr(site, field) != getattr(payload, field):
                log = db.get(model, site.domain)
                if log and log.last_loaded_date:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "An imported source cannot be changed here because it would mix data "
                            "from different properties. Contact your administrator."
                        ),
                    )
                if log:
                    db.delete(log)
        site.gsc_property = payload.gsc_property
        site.ga4_property_id = payload.ga4_property_id
        db.commit()
    response.headers["Cache-Control"] = "no-store"
    return connection_response(site, user, request)


@router.post(
    "/{slug}/sync",
    response_model=SyncJob,
    status_code=202,
    dependencies=[Depends(check_auth_origin)],
)
def start_sync(
    site: AccessibleSite,
    user: CurrentUser,
    request: Request,
    background: BackgroundTasks,
    response: Response,
) -> SyncJob:
    require_manager(site, user)
    if not site.active:
        raise HTTPException(
            status_code=409, detail="This website is inactive. Contact your administrator."
        )
    settings = get_settings()
    credentials = setup_info(settings)
    selected = {
        source
        for source, prop in [("gsc", site.gsc_property), ("ga4", site.ga4_property_id)]
        if prop
    }
    if not selected:
        raise HTTPException(
            status_code=422,
            detail="Save a Search Console property or GA4 property ID before syncing.",
        )
    if not any(credentials[source].configured for source in selected):
        raise HTTPException(
            status_code=503,
            detail=(
                "Google credentials are not configured on the server. "
                "Ask your administrator to complete the setup shown on this page."
            ),
        )
    jobs = request.app.state.sync_jobs
    try:
        job = jobs.start(site.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    background.add_task(run_site_sync, site.id, jobs, settings)
    response.headers["Cache-Control"] = "no-store"
    return job
