from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import LoginRateLimiter
from app.config import get_settings
from app.routers import analytics, auth, sites
from app.site_sync import SyncJobs


def create_app() -> FastAPI:
    app = FastAPI(title="SEOPs API", version="0.1.0")
    app.state.login_limiter = LoginRateLimiter()
    app.state.sync_jobs = SyncJobs()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(auth.router)
    app.include_router(sites.router)
    app.include_router(analytics.router)
    return app


app = create_app()
