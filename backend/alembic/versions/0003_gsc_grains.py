"""Allow omitted device dimensions in separate GSC aggregate grains."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_gsc_daily_device"), "gsc_daily", type_="check")
    op.create_check_constraint(
        op.f("ck_gsc_daily_device"), "gsc_daily", "device IN ('', 'MOBILE', 'DESKTOP', 'TABLET')"
    )


def downgrade() -> None:
    # Aggregate rows cannot exist under the original constraint.
    op.execute("DELETE FROM gsc_daily WHERE device = ''")
    op.drop_constraint(op.f("ck_gsc_daily_device"), "gsc_daily", type_="check")
    op.create_check_constraint(
        op.f("ck_gsc_daily_device"), "gsc_daily", "device IN ('MOBILE', 'DESKTOP', 'TABLET')"
    )
