from functools import lru_cache
from pathlib import Path
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://seops:seops@localhost:5432/seops"
    session_secret: SecretStr
    session_cookie_name: str = Field(default="seops_session", min_length=1)
    session_max_age_seconds: int = Field(default=1209600, gt=0)
    cors_origins: str = "http://localhost:3000"
    gsc_service_account_file: Path | None = None
    ga4_service_account_file: Path | None = None
    sync_lag_days: int = Field(default=3, ge=0)
    sync_timezone: str = "UTC"
    ga4_call_click_events: dict[str, str] = Field(default_factory=dict)
    portfolio_site_slugs: list[str] = Field(default_factory=list)
    reports_dir: Path = Path("reports")

    @model_validator(mode="after")
    def default_ga4_credentials(self) -> Self:
        if self.ga4_service_account_file is None:
            self.ga4_service_account_file = self.gsc_service_account_file
        return self

    @field_validator("sync_timezone")
    @classmethod
    def valid_sync_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("SYNC_TIMEZONE must be a valid IANA timezone") from None
        return value

    @field_validator("session_secret")
    @classmethod
    def strong_session_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 characters")
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
