"""Create the foundation data without replacing existing domains or credentials."""

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.auth import hash_password
from app.db import SessionLocal
from app.models import Site, User, UserSite


class SeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    seed_admin_email: EmailStr
    seed_admin_password: SecretStr = Field(min_length=1, max_length=1024)
    seed_viewer_email: EmailStr
    seed_viewer_password: SecretStr = Field(min_length=1, max_length=1024)

    @field_validator("seed_admin_email", "seed_viewer_email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return str(value).casefold()

    @model_validator(mode="after")
    def different_users(self) -> "SeedSettings":
        if self.seed_admin_email == self.seed_viewer_email:
            raise ValueError("Seed admin and viewer must use different email addresses")
        return self


SITE_SEEDS = [
    {"slug": "arlington", "domain": "arlington247lockrepair.com", "display_name": "Arlington"},
    *[
        {"slug": f"site{i}", "domain": f"TODO-site{i}.example", "display_name": f"Site {i}"}
        for i in range(2, 6)
    ],
]


def seed() -> None:
    settings = SeedSettings()
    with SessionLocal.begin() as db:
        for site in SITE_SEEDS:
            db.execute(insert(Site).values(**site).on_conflict_do_nothing(index_elements=["slug"]))
        sites = list(db.scalars(select(Site).where(Site.slug.in_([s["slug"] for s in SITE_SEEDS]))))
        for email, password, role in [
            (settings.seed_admin_email, settings.seed_admin_password, "admin"),
            (settings.seed_viewer_email, settings.seed_viewer_password, "viewer"),
        ]:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                db.execute(
                    insert(User)
                    .values(
                        email=email,
                        password_hash=hash_password(password.get_secret_value()),
                        role=role,
                    )
                    .on_conflict_do_nothing(index_elements=["email"])
                )
                user = db.scalar(select(User).where(User.email == email))
            if user is None or user.role != role:
                raise ValueError(f"Existing seed user {email} must have role {role}")
            for site in sites:
                if role == "admin" or site.slug == "arlington":
                    db.execute(
                        insert(UserSite)
                        .values(user_id=user.id, site_id=site.id)
                        .on_conflict_do_nothing()
                    )


if __name__ == "__main__":
    seed()
    print("Seed complete (existing sites and passwords preserved).")
