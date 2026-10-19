"""Track who may manage a website without expanding viewer permissions."""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_sites_created_by_user_id_users",
        "sites",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_sites_created_by_user_id_users", "sites", type_="foreignkey")
    op.drop_column("sites", "created_by_user_id")
