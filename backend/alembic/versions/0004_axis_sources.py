"""Store bounded inspection results and explicitly collected axis evidence."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "axis_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("site", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_axis_snapshots_site_kind_collected_at",
        "axis_snapshots",
        ["site", "kind", "collected_at"],
    )
    op.create_table(
        "gsc_index_status",
        sa.Column("site", sa.Text(), primary_key=True),
        sa.Column("url", sa.Text(), primary_key=True),
        sa.Column("verdict", sa.Text()),
        sa.Column("coverage_state", sa.Text()),
        sa.Column("indexing_state", sa.Text()),
        sa.Column("last_crawl_time", sa.DateTime(timezone=True)),
        sa.Column(
            "inspected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("gsc_index_status")
    op.drop_index("ix_axis_snapshots_site_kind_collected_at", table_name="axis_snapshots")
    op.drop_table("axis_snapshots")
