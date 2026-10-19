"""Validation and local credential readiness for website onboarding."""

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlsplit

from google.oauth2 import service_account
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import Settings


def normalize_domain(value: str) -> str:
    value = value.strip()
    try:
        parts = urlsplit(value if "://" in value else f"https://{value}")
        if (
            parts.scheme not in {"http", "https"}
            or parts.username is not None
            or parts.password is not None
            or parts.port is not None
            or parts.path not in {"", "/"}
            or parts.query
            or parts.fragment
        ):
            raise ValueError
        domain = (parts.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
        if len(domain) > 253 or "." not in domain:
            raise ValueError
        if any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in domain.split(".")
        ):
            raise ValueError
        try:
            ipaddress.ip_address(domain)
        except ValueError:
            return domain
    except (ValueError, UnicodeError):
        pass
    raise ValueError("Enter a domain or homepage URL, such as example.com or https://example.com/")


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    gsc_property: str | None = Field(default=None, max_length=2048)
    ga4_property_id: str | None = Field(default=None, max_length=30)

    @field_validator("gsc_property", "ga4_property_id", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("gsc_property")
    @classmethod
    def validate_gsc(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value.startswith("sc-domain:"):
            return f"sc-domain:{normalize_domain(value.removeprefix('sc-domain:'))}"
        try:
            parts = urlsplit(value)
            normalize_domain(f"{parts.scheme}://{parts.netloc}")
            if parts.scheme not in {"http", "https"} or parts.query or parts.fragment:
                raise ValueError
        except ValueError:
            raise ValueError(
                "Use sc-domain:example.com or the exact https://example.com/ property"
            ) from None
        return value

    @field_validator("ga4_property_id")
    @classmethod
    def validate_ga4(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[1-9][0-9]{0,29}", value):
            raise ValueError("Use the numeric GA4 property ID, not a G- measurement ID")
        return value

    def check_domain(self, domain: str) -> None:
        if not self.gsc_property:
            return
        property_domain = (
            self.gsc_property.removeprefix("sc-domain:")
            if self.gsc_property.startswith("sc-domain:")
            else normalize_domain(
                f"{urlsplit(self.gsc_property).scheme}://{urlsplit(self.gsc_property).netloc}"
            )
        )
        if domain != property_domain and not (
            self.gsc_property.startswith("sc-domain:") and domain.endswith(f".{property_domain}")
        ):
            raise ValueError("The Search Console property must belong to this website's domain")


class CreateSiteInput(ConnectionInput):
    display_name: str = Field(min_length=1, max_length=120)
    domain: str = Field(min_length=1, max_length=2048)

    @field_validator("domain")
    @classmethod
    def domain_only(cls, value: str) -> str:
        return normalize_domain(value)

    @model_validator(mode="after")
    def matching_property(self):
        self.check_domain(self.domain)
        return self


class CredentialInfo(BaseModel):
    configured: bool
    service_account_email: str | None = None
    message: str


def credential_info(path: Path | None, variable: str) -> CredentialInfo:
    if path is None:
        return CredentialInfo(
            configured=False,
            message=f"Ask your administrator to configure {variable} on the server.",
        )
    try:
        credentials = service_account.Credentials.from_service_account_file(str(path))
        email = credentials.service_account_email
        if not email:
            raise ValueError
    except Exception:
        # Do not return filenames, private keys, parser input, or credential exceptions.
        return CredentialInfo(
            configured=False,
            message=(
                f"The server's {variable} file is unavailable or invalid. "
                "Contact your administrator."
            ),
        )
    return CredentialInfo(
        configured=True,
        service_account_email=email,
        message=(
            "Server credentials are available. Grant this account access "
            "to your Google property before syncing."
        ),
    )


def setup_info(settings: Settings) -> dict[str, CredentialInfo]:
    return {
        "gsc": credential_info(settings.gsc_service_account_file, "GSC_SERVICE_ACCOUNT_FILE"),
        "ga4": credential_info(
            settings.ga4_service_account_file,
            "GA4_SERVICE_ACCOUNT_FILE (or GSC_SERVICE_ACCOUNT_FILE)",
        ),
    }
