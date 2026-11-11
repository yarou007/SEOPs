"""Store Ahrefs Web Analytics rows in a typed table; add its view to every site schema."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _load(name: str, filename: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _views(base: str) -> dict[str, str]:
    views = _load("migration_0006", "0006_ai_insights.py")._ai_views(base)
    views["ahrefs_web_analytics"] = (
        "SELECT period_start, period_end, report, item, visitors, views, entrances, exits, "
        "count, exit_rate, bounce_rate, visit_duration, time_on_page, conversion_rate, "
        f'snapshot_id, imported_at FROM "{base}".ahrefs_web_analytics WHERE site = %2$L '
        "ORDER BY period_end, report, visitors DESC NULLS LAST"
    )
    return views


def upgrade() -> None:
    base = op.get_bind().exec_driver_sql("SELECT current_schema()").scalar_one()
    op.create_table(
        "ahrefs_web_analytics",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("axis_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "site",
            sa.Text(),
            sa.ForeignKey("sites.domain", onupdate="CASCADE", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("report", sa.Text(), nullable=False),
        sa.Column("item", sa.Text(), nullable=False),
        *(
            sa.Column(name, sa.Integer())
            for name in ["visitors", "views", "entrances", "exits", "count"]
        ),
        *(
            sa.Column(name, sa.Numeric())
            for name in [
                "exit_rate",
                "bounce_rate",
                "visit_duration",
                "time_on_page",
                "conversion_rate",
            ]
        ),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_ahrefs_web_analytics_snapshot_id", "ahrefs_web_analytics", ["snapshot_id"])
    op.create_index(
        "ix_ahrefs_web_analytics_site_report_end",
        "ahrefs_web_analytics",
        ["site", "report", "period_end"],
    )
    unified = _load("migration_0005", "0005_unified_site_database.py")
    op.execute(unified._refresh_function(base, _views(base)))
    op.execute(f'SELECT "{base}".refresh_site_schemas()')


def downgrade() -> None:
    base = op.get_bind().exec_driver_sql("SELECT current_schema()").scalar_one()
    unified = _load("migration_0005", "0005_unified_site_database.py")
    ai_views = _load("migration_0006", "0006_ai_insights.py")._ai_views(base)
    op.execute(unified._refresh_function(base, ai_views))
    op.execute(f'SELECT "{base}".refresh_site_schemas()')
    op.drop_table("ahrefs_web_analytics")
