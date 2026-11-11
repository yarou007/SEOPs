"""Link all source data to sites, store reports and raw CSV rows, add per-site view schemas.

Every data row now references ``sites.domain`` through a real foreign key (renames
cascade, deleting a site that still has data is refused). Weekly reports and raw
Ahrefs CSV rows move into the database. Each website also gets its own schema of
read-only views so the database can be browsed and exported site by site.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

SITE_DATA_TABLES = [
    "gsc_daily",
    "gsc_sync_log",
    "ga4_daily",
    "ga4_sync_log",
    "axis_snapshots",
    "gsc_index_status",
]

# Marker stored as the schema comment, so only schemas created here are ever dropped.
MARKER = "seops site views"


def _site_views(base: str, extra_views: dict[str, str] | None = None) -> str:
    """Per-site view definitions; %1$I is the site schema, %2$L the domain literal.

    Later migrations pass ``extra_views`` (same placeholders) to add views.
    """
    b = f'"{base}"'
    views = {
        "site_info": f"SELECT * FROM {b}.sites WHERE domain = %2$L",
        "daily_totals": (
            "SELECT data_date, clicks, impressions, ctr, position, pulled_at "
            f"FROM {b}.gsc_daily WHERE site = %2$L AND page = '' AND query = '' "
            "AND device = '' AND country = 'all'"
        ),
        "devices": (
            "SELECT data_date, device, clicks, impressions, ctr, position "
            f"FROM {b}.gsc_daily WHERE site = %2$L AND page = '' AND query = '' "
            "AND device <> '' AND country = 'all'"
        ),
        "countries": (
            "SELECT data_date, country, clicks, impressions, ctr, position "
            f"FROM {b}.gsc_daily WHERE site = %2$L AND page = '' AND query = '' "
            "AND device = '' AND country <> 'all'"
        ),
        "pages": (
            "SELECT data_date, page, clicks, impressions, ctr, position "
            f"FROM {b}.gsc_daily WHERE site = %2$L AND page <> '' AND query = '' "
            "AND device = '' AND country = 'all'"
        ),
        "pages_by_device": (
            "SELECT data_date, page, device, clicks, impressions, ctr, position "
            f"FROM {b}.gsc_daily WHERE site = %2$L AND page <> '' AND query = '' "
            "AND device <> '' AND country = 'all'"
        ),
        "queries": (
            "SELECT data_date, query, page, device, clicks, impressions, ctr, position "
            f"FROM {b}.gsc_daily WHERE site = %2$L AND query <> ''"
        ),
        "ga4_pages": (
            "SELECT data_date, page_path, sessions, total_users, conversions, "
            f"engagement_rate, pulled_at FROM {b}.ga4_daily WHERE site = %2$L"
        ),
        "snapshots": (
            "SELECT id, kind, start_date, end_date, collected_at, data "
            f"FROM {b}.axis_snapshots WHERE site = %2$L"
        ),
        "index_status": (
            "SELECT url, verdict, coverage_state, indexing_state, last_crawl_time, "
            f"inspected_at FROM {b}.gsc_index_status WHERE site = %2$L"
        ),
        "weekly_reports": (
            "SELECT report_date, generated_at, markdown, report "
            f"FROM {b}.weekly_reports WHERE site = %2$L"
        ),
        "ahrefs_rows": (
            "SELECT snapshot_id, kind, row_number, data, imported_at "
            f"FROM {b}.ahrefs_csv_rows WHERE site = %2$L"
        ),
        "sync_status": (
            "SELECT 'gsc'::text AS source, last_loaded_date, last_run_at, status, "
            f"rows_loaded, error FROM {b}.gsc_sync_log WHERE site = %2$L "
            "UNION ALL SELECT 'ga4', last_loaded_date, last_run_at, status, rows_loaded, "
            f"error FROM {b}.ga4_sync_log WHERE site = %2$L"
        ),
    }
    views.update(extra_views or {})
    return "\n".join(
        f"    EXECUTE format('CREATE VIEW %1$I.{name} AS {sql.replace(chr(39), chr(39) * 2)}', "
        "target, site_row.domain);"
        for name, sql in views.items()
    )


def _refresh_function(base: str, extra_views: dict[str, str] | None = None) -> str:
    # Site schemas use the bare domain in the default "public" schema, and are
    # prefixed with the base schema anywhere else (isolated test schemas).
    prefix = "" if base == "public" else f"{base}__"
    return f"""
CREATE OR REPLACE FUNCTION "{base}".refresh_site_schemas() RETURNS void
LANGUAGE plpgsql AS $fn$
DECLARE
    site_row record;
    old_schema record;
    target text;
    existing_comment text;
BEGIN
    FOR old_schema IN
        SELECT nspname FROM pg_namespace
        WHERE obj_description(oid, 'pg_namespace') = '{MARKER} ({base})'
    LOOP
        EXECUTE format('DROP SCHEMA %I CASCADE', old_schema.nspname);
    END LOOP;

    FOR site_row IN SELECT domain FROM "{base}".sites ORDER BY domain LOOP
        target := left('{prefix}' || trim(both '_' from
            regexp_replace(lower(site_row.domain), '[^a-z0-9]+', '_', 'g')), 63);
        IF target ~ '^[0-9]' THEN
            target := left('site_' || target, 63);
        END IF;
        SELECT obj_description(oid, 'pg_namespace') INTO existing_comment
        FROM pg_namespace WHERE nspname = target;
        IF FOUND THEN
            -- Never touch a schema this function did not create.
            RAISE WARNING 'Schema % already exists; skipping site views for %',
                target, site_row.domain;
            CONTINUE;
        END IF;
        EXECUTE format('CREATE SCHEMA %I', target);
        EXECUTE format('COMMENT ON SCHEMA %I IS %L', target, '{MARKER} ({base})');
{_site_views(base, extra_views)}
    END LOOP;
END
$fn$;

CREATE OR REPLACE FUNCTION "{base}".refresh_site_schemas_trigger() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    PERFORM "{base}".refresh_site_schemas();
    RETURN NULL;
END
$fn$;
"""


def upgrade() -> None:
    connection = op.get_bind()
    base = connection.exec_driver_sql("SELECT current_schema()").scalar_one()

    orphans = connection.exec_driver_sql(
        " UNION ".join(
            f"SELECT DISTINCT site FROM {table} WHERE site NOT IN (SELECT domain FROM sites)"
            for table in SITE_DATA_TABLES
        )
    ).scalars()
    orphans = sorted(orphans)
    if orphans:
        raise RuntimeError(
            "Data exists for domains missing from sites; add or fix these sites first: "
            + ", ".join(orphans)
        )

    for table in SITE_DATA_TABLES:
        op.create_foreign_key(
            f"fk_{table}_site_sites",
            table,
            "sites",
            ["site"],
            ["domain"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        )

    op.create_table(
        "weekly_reports",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "site",
            sa.Text(),
            sa.ForeignKey("sites.domain", onupdate="CASCADE", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("report", postgresql.JSONB(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.UniqueConstraint("site", "report_date", name="uq_weekly_reports_site_report_date"),
    )
    op.create_table(
        "ahrefs_csv_rows",
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
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_ahrefs_csv_rows_site_kind", "ahrefs_csv_rows", ["site", "kind"])
    op.create_index("ix_ahrefs_csv_rows_snapshot_id", "ahrefs_csv_rows", ["snapshot_id"])

    op.execute(_refresh_function(base))
    op.execute(
        f"CREATE TRIGGER sites_refresh_site_schemas AFTER INSERT OR DELETE OR UPDATE OF domain "
        f'ON "{base}".sites FOR EACH STATEMENT '
        f'EXECUTE FUNCTION "{base}".refresh_site_schemas_trigger()'
    )
    op.execute(
        f"CREATE TRIGGER sites_refresh_site_schemas_truncate AFTER TRUNCATE "
        f'ON "{base}".sites FOR EACH STATEMENT '
        f'EXECUTE FUNCTION "{base}".refresh_site_schemas_trigger()'
    )
    op.execute(f'SELECT "{base}".refresh_site_schemas()')


def downgrade() -> None:
    connection = op.get_bind()
    base = connection.exec_driver_sql("SELECT current_schema()").scalar_one()
    op.execute(f'DROP TRIGGER IF EXISTS sites_refresh_site_schemas ON "{base}".sites')
    op.execute(f'DROP TRIGGER IF EXISTS sites_refresh_site_schemas_truncate ON "{base}".sites')
    op.execute(f"""
DO $do$
DECLARE old_schema record;
BEGIN
    FOR old_schema IN
        SELECT nspname FROM pg_namespace
        WHERE obj_description(oid, 'pg_namespace') = '{MARKER} ({base})'
    LOOP
        EXECUTE format('DROP SCHEMA %I CASCADE', old_schema.nspname);
    END LOOP;
END
$do$;
""")
    op.execute(f'DROP FUNCTION IF EXISTS "{base}".refresh_site_schemas_trigger()')
    op.execute(f'DROP FUNCTION IF EXISTS "{base}".refresh_site_schemas()')
    op.drop_table("ahrefs_csv_rows")
    op.drop_table("weekly_reports")
    for table in SITE_DATA_TABLES:
        op.drop_constraint(f"fk_{table}_site_sites", table, type_="foreignkey")
