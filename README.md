# SEOPs

Client-facing SEO analytics platform. Clients connect their analytics sources and see them together on one dashboard. Sources so far: Google Search Console, Google Analytics 4, and Ahrefs CSV exports. Each site's data goes through a weekly analysis that flags pages and opportunities.

This project does not change the websites themselves.

## What it does

- **Google Search Console sync:** daily property totals, query-free page totals, device and country totals, and query-level detail. Resumable and idempotent.
- **GA4 sync:** daily sessions, users, conversions and engagement by page path. Same resumable pattern.
- **Analysis axes:** eight protected views (see `docs/ANALYSIS_AXES.md`): impressions vs clicks, funnel, devices and OS, geography and zones, sitemaps, internal links, links between our sites, and search requests.
- **Weekly analysis:** flags pages with high impressions and low CTR, mobile/desktop gaps, queries in positions 8–20, and clicks dropping, capped at three pages per site.
- **Dashboard:** login, site list, Overview, Search, Traffic, Analysis, Ahrefs, Data status, weekly report. Light and dark mode, phone and desktop layouts.
- **Website onboarding:** any signed-in user can add a website. Its creator and admins manage Google connections and start imports. Other linked users are read-only.

## Repository layout

backend/ FastAPI, SQLAlchemy, Alembic, sync jobs, analysis, tests
frontend/ Next.js (App Router), TypeScript, Tailwind CSS
docs/ Project plan and analysis axes


Setup and commands:
- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)
- [docs/PLAN.md](docs/PLAN.md): the phased plan and its status
- [docs/ANALYSIS_AXES.md](docs/ANALYSIS_AXES.md): the eight analysis axes and their data sources

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, Alembic, PostgreSQL 16
- Frontend: Next.js, TypeScript, Tailwind CSS, recharts, Vitest, Playwright
- Google access: service accounts (Search Console API, Analytics Data API, URL Inspection API)

## Branches

| Branch | Purpose |
|---|---|
| `main` | Stable baseline (pending merge of `feat/real-data-sync`) |
| `feat/real-data-sync` | Real Google data, backfill, site onboarding, the first real site |
| `feat/analysis-axes` | Eight analysis axes, GSC totals fix, Analysis tab (PR #1 into `feat/real-data-sync`) |
| `feat/unified-database` | One database organized by website: foreign keys, per-site schemas, reports and raw Ahrefs rows stored in PostgreSQL |

Work on a feature branch and open a pull request. Don't push straight to `main`.

## Database

All data for every website lives in **one PostgreSQL 16 database** (`seops`).
Every row is linked to its website, and each website has its own folder (schema)
you can open, browse and export.

### How it is organized

```
seops
└── Schemas
    ├── public                        shared storage the app reads and writes
    │   ├── sites, users, user_sites
    │   ├── gsc_daily, gsc_sync_log   Search Console data and sync progress
    │   ├── ga4_daily, ga4_sync_log   GA4 data and sync progress
    │   ├── axis_snapshots            processed analysis evidence (OS, sitemaps, CSVs)
    │   ├── gsc_index_status          URL inspection results
    │   ├── weekly_reports            weekly analysis (JSON + readable Markdown)
    │   └── ahrefs_csv_rows           every raw row of each uploaded Ahrefs CSV
    └── <one schema per website>      e.g. dcemergencylockanddoor_com
        └── Views: site_info, daily_totals, devices, countries, pages,
                   pages_by_device, queries, ga4_pages, snapshots, index_status,
                   weekly_reports, ahrefs_rows, sync_status
```

- **Linked by website.** Each data table's `site` column is a foreign key to
  `sites.domain`. Data for an unknown website is rejected. Renaming a domain
  updates every row. A website that still has data cannot be deleted.
- **One folder per website.** The views in a website's schema show only that site's
  rows. They are views, not copies, so they always show the latest data. A trigger on
  `sites` creates, renames or removes these schemas automatically. To rebuild them by
  hand, run `SELECT refresh_site_schemas();`.
- **No double counting.** `gsc_daily` stores the same traffic at several levels (site,
  page, device, country, query). Each view picks one level, so you can sum a view
  safely. Don't sum `gsc_daily` directly.

### How data gets updated

Data changes only when a sync runs. Nothing is scheduled by default.

| Source | How to update |
|---|---|
| Search Console, GA4 | Dashboard import button, or `python -m app.sync gsc --all` and `python -m app.sync ga4 --all` |
| Weekly report | Saved after each dashboard import, or `python -m app.analysis weekly --all` |
| Ahrefs | Upload a CSV in the dashboard |

Syncs resume from the last loaded day and never create duplicates (rows are upserted).
The newest `SYNC_LAG_DAYS` days (default 3) are skipped because Google still revises
them. Report files written under `REPORTS_DIR` are an export copy; the database is the
source. To import older report files once, run `python -m scripts.import_report_files`.

### How to configure it

1. **Start PostgreSQL 16.** Choose one:
   - Docker: `cd backend && docker compose up -d --wait db` (port 5432).
   - Any existing PostgreSQL 16 server.
2. **Point the backend at it.** In `backend/.env`, set:
   ```
   DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:<port>/seops
   TEST_DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:<port>/seops_test
   ```
   The user must be allowed to create schemas, because each website gets one. Keep
   real passwords only in `.env`, which Git ignores.
3. **Create the tables, triggers and website folders:**
   ```sh
   cd backend
   alembic upgrade head
   python -m scripts.seed
   ```
4. **Run the backend** (`uvicorn app.main:app`) and add websites from the dashboard.
   Each new website gets its schema immediately.

### Browse and export

Connect any PostgreSQL client (for example DBeaver) with the values from
`DATABASE_URL`. Then open `seops → Schemas → <website> → Views`. Right-click a view and
choose **Export Data** for CSV or Excel. For a full backup, run
`pg_dump -Fc seops > seops.dump`. To restore it, run
`pg_restore -d <new database> seops.dump`.

Migration `0005` refuses to run if any data row points to a domain that is missing
from `sites`. It names the domains to fix. `alembic downgrade 0004` removes the website
schemas and the two new tables, and keeps all Google data.

## Status

- Verified with fixture data: 291 backend tests, 59 frontend unit tests, 3 browser tests.
- Real data: the test site `dcemergencylockanddoor.com` is connected. For 22 Sep–19 Oct 2026, Google shows 4 clicks and 2,519 impressions, and the dashboard matches after the totals fix.
- Not yet verified: the full 16-month backfill for that site, and the sitemap and GA4 operating-system collections.
- Arlington's seeded data is synthetic.

## Still needs setup

- Call-click event configured on each website (funnel's last step)
- Zone list for the geography axis
- Site Audit and backlink CSV exports (internal links and links between sites)
- Confirmed domains and property types for the five portfolio sites
- Keyword provider for search volume and difficulty (CEO decision)

## Known limits

- Google hides some queries, so query-level totals are partial. Page and property totals come from separate requests and are the figures to trust.
- Sorting and pagination in tables apply to the current page only. Server-side sorting is planned.
- Logout clears the browser cookie, but a copied session token stays valid until it expires. Server-side sessions are planned.
- Ahrefs data is entered by CSV upload. The free Ahrefs plan has no API for us.
- GA4 dates follow the property timezone. Our daily cutoff uses UTC, so a day's boundary can shift.

## Secrets

- Never commit `.env` files, service-account JSON keys, or API tokens.
- Keep service-account keys outside the repository, with restricted permissions (`chmod 600`).
- Configure secrets through environment variables. See `backend/.env.example`.

