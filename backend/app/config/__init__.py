from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    openrouter_api_key: SecretStr | None = None
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "nvidia/nemotron-3.5-super-vl:free"
    llm_fallback_models: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["google/gemma-4-31b-it:free"]
    )
    llm_max_tokens: int = Field(default=8000, gt=0)
    llm_reasoning_effort: Literal["low", "medium", "high"] | None = "low"
    llm_timeout_seconds: float = Field(default=120, gt=0)
    llm_daily_request_budget: int = Field(default=45, ge=0)

    @field_validator("openrouter_api_key", "llm_reasoning_effort", mode="before")
    @classmethod
    def blank_key_is_unset(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("llm_fallback_models", mode="before")
    @classmethod
    def comma_separated_models(cls, value):
        if isinstance(value, str):
            return [model.strip() for model in value.split(",") if model.strip()]
        return value

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
