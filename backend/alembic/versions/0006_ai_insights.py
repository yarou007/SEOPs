"""Store AI conversations, insights and daily LLM usage; add AI views to site schemas."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _unified():
    path = Path(__file__).with_name("0005_unified_site_database.py")
    spec = importlib.util.spec_from_file_location("migration_0005", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ai_views(base: str) -> dict[str, str]:
    b = f'"{base}"'
    return {
        "ai_insights": (
            "SELECT id, source, report_date, priority, status, title, problem, evidence, "
            "advice, target_url, target_kpi, model, message_id, created_at, updated_at "
            f"FROM {b}.ai_insights WHERE site = %2$L"
        ),
        "ai_conversations": (
            "SELECT c.id AS conversation_id, c.title, m.created_at, m.role, m.content, "
            "m.suggested_questions, m.model "
            f"FROM {b}.ai_conversations c JOIN {b}.ai_messages m ON m.conversation_id = c.id "
            "WHERE c.site = %2$L ORDER BY c.created_at, m.created_at"
        ),
    }


def _site_column() -> sa.Column:
    return sa.Column(
        "site",
        sa.Text(),
        sa.ForeignKey("sites.domain", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )


def _created_at(name: str = "created_at") -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    )


def upgrade() -> None:
    base = op.get_bind().exec_driver_sql("SELECT current_schema()").scalar_one()
    uuid_pk = {"primary_key": True, "server_default": sa.text("gen_random_uuid()")}
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Uuid(), **uuid_pk),
        _site_column(),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("title", sa.Text(), nullable=False),
        _created_at(),
    )
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Uuid(), **uuid_pk),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "suggested_questions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "context_summary",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("model", sa.Text()),
        _created_at(),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="role"),
    )
    op.create_table(
        "ai_insights",
        sa.Column("id", sa.Uuid(), **uuid_pk),
        _site_column(),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("report_date", sa.Date()),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("ai_messages.id", ondelete="SET NULL")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("advice", sa.Text(), nullable=False),
        sa.Column("target_url", sa.Text()),
        sa.Column("target_kpi", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="new"),
        sa.Column("model", sa.Text(), nullable=False),
        _created_at(),
        _created_at("updated_at"),
        sa.CheckConstraint("source IN ('weekly', 'chat')", name="source"),
        sa.CheckConstraint("priority IN ('high', 'medium', 'low')", name="priority"),
        sa.CheckConstraint("status IN ('new', 'accepted', 'dismissed', 'done')", name="status"),
    )
    op.create_index("ix_ai_insights_site_status", "ai_insights", ["site", "status"])
    op.create_table(
        "llm_usage",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quota_exhausted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("weekly_reports", sa.Column("ai_summary", sa.Text()))
    op.execute(_unified()._refresh_function(base, _ai_views(base)))
    op.execute(f'SELECT "{base}".refresh_site_schemas()')


def downgrade() -> None:
    base = op.get_bind().exec_driver_sql("SELECT current_schema()").scalar_one()
    op.execute(_unified()._refresh_function(base))
    op.execute(f'SELECT "{base}".refresh_site_schemas()')
    op.drop_column("weekly_reports", "ai_summary")
    op.drop_table("llm_usage")
    op.drop_index("ix_ai_insights_site_status", table_name="ai_insights")
    op.drop_table("ai_insights")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
