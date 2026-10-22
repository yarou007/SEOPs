from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'viewer')", name="role"),)

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, default="viewer", server_default="viewer")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(Text, unique=True)
    domain: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    gsc_property: Mapped[str | None] = mapped_column(Text)
    ga4_property_id: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class UserSite(Base):
    __tablename__ = "user_sites"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    site_id: Mapped[UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
    )


class GscDaily(Base):
    __tablename__ = "gsc_daily"
    __table_args__ = (
        CheckConstraint("device IN ('', 'MOBILE', 'DESKTOP', 'TABLET')", name="device"),
    )

    # Sync data is keyed by sites.domain, never the slug.
    site: Mapped[str] = mapped_column(Text, primary_key=True)
    data_date: Mapped[date] = mapped_column(Date, primary_key=True)
    page: Mapped[str] = mapped_column(Text, primary_key=True)
    query: Mapped[str] = mapped_column(Text, primary_key=True, server_default="", default="")
    device: Mapped[str] = mapped_column(Text, primary_key=True)
    country: Mapped[str] = mapped_column(
        Text, primary_key=True, server_default="all", default="all"
    )
    clicks: Mapped[int] = mapped_column(Integer)
    impressions: Mapped[int] = mapped_column(Integer)
    ctr: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    position: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    pulled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class GscSyncLog(Base):
    __tablename__ = "gsc_sync_log"
    __table_args__ = (CheckConstraint("status IN ('ok', 'error')", name="status"),)

    site: Mapped[str] = mapped_column(Text, primary_key=True)
    last_loaded_date: Mapped[date | None] = mapped_column(Date)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str | None] = mapped_column(Text)
    rows_loaded: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)


class Ga4Daily(Base):
    __tablename__ = "ga4_daily"
    __table_args__ = (Index("ix_ga4_daily_site_page_path", "site", "page_path"),)

    site: Mapped[str] = mapped_column(Text, primary_key=True)
    data_date: Mapped[date] = mapped_column(Date, primary_key=True)
    page_path: Mapped[str] = mapped_column(Text, primary_key=True)
    sessions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_users: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    conversions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    engagement_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    pulled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Ga4SyncLog(Base):
    __tablename__ = "ga4_sync_log"

    site: Mapped[str] = mapped_column(Text, primary_key=True)
    last_loaded_date: Mapped[date | None] = mapped_column(Date)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str | None] = mapped_column(Text)
    rows_loaded: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)


class AxisSnapshot(Base):
    """Source evidence collected explicitly; read endpoints never contact Google."""

    __tablename__ = "axis_snapshots"
    __table_args__ = (
        Index("ix_axis_snapshots_site_kind_collected_at", "site", "kind", "collected_at"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    site: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    data: Mapped[dict] = mapped_column(JSONB)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class GscIndexStatus(Base):
    __tablename__ = "gsc_index_status"

    site: Mapped[str] = mapped_column(Text, primary_key=True)
    url: Mapped[str] = mapped_column(Text, primary_key=True)
    verdict: Mapped[str | None] = mapped_column(Text)
    coverage_state: Mapped[str | None] = mapped_column(Text)
    indexing_state: Mapped[str | None] = mapped_column(Text)
    last_crawl_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inspected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
