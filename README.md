# SEOPs

Client-facing SEO analytics platform. Clients connect their analytics sources and see them together on one dashboard. Sources so far: Google Search Console, Google Analytics 4, and Ahrefs exports (Web Analytics, Backlinks, Site Audit). Each site's data goes through a weekly analysis that flags pages and opportunities.

This project does not change the websites themselves.

## What it does

- **Google Search Console sync:** daily property totals, query-free page totals, device and country totals, and query-level detail. Resumable and idempotent.
- **GA4 sync:** daily sessions, users, conversions and engagement by page path. Same resumable pattern.
- **Analysis axes:** eight protected views (see `docs/ANALYSIS_AXES.md`): impressions vs clicks, funnel, devices and OS, geography and zones, sitemaps, internal links, links between our sites, and search requests.
- **Weekly analysis:** flags pages with high impressions and low CTR, mobile/desktop gaps, queries in positions 8–20, and clicks dropping, capped at three pages per site.
- **AI insights:** ask questions about a website's data in plain English, get answers that cite the stored figures plus better follow-up questions, and generate an AI analysis for the weekly report. Every piece of advice is stored as a structured insight (see [AI insights](#ai-insights)).
- **Dashboard:** a sidebar with a website switcher and the sections Overview, Search, Traffic, Analysis, AI Insights, Ahrefs, Setup and Data status. Light and dark mode, phone (menu drawer) and desktop layouts. See [Using the dashboard](#using-the-dashboard).
- **Ahrefs import:** upload the Ahrefs Web Analytics "all stats" export (a folder of files), Backlinks or Site Audit CSVs from the Ahrefs page. Every import is stored in the database and compared with the previous one.
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
| `feat/ai-insights` | AI chat, weekly AI analysis and stored insights over each site's data (built on `feat/unified-database`) |
| `feat/ui-redesign` | New dashboard design, guided Setup, Ahrefs Web Analytics import and history (built on `feat/ai-insights`) |

Work on a feature branch and open a pull request. Don't push straight to `main`.

## Using the dashboard

Sign in, then pick a website in the sidebar (or on **Your websites**).

| Section | What it shows |
|---|---|
| **Overview** | One plain sentence on how clicks from Google changed, the four main numbers (clicks, times shown, click rate, average position) with an ⓘ explanation each, visits from GA4, a day-by-day chart, **What to do next** (actions built from the weekly report's flags), AI advice, and the full weekly report folded below. |
| **Search** | Pages and searches from Search Console, sortable. |
| **Traffic** | Visits per page from GA4. |
| **Analysis** | Eight questions, each with a one-line answer; open the details for charts and tables. |
| **AI Insights** | Ask questions in plain English; advice cards with filters (open, done, dismissed, priority). |
| **Ahrefs** | Import Ahrefs exports and see visitors, phone clicks, pages, channels and devices, with the change since the previous import. |
| **Setup** | Three steps: Search Console, GA4, Ahrefs. Each shows Connected, Needs action, Not set up or Not working. Pick the property from a list, **Test connection**, then **Sync now**. |
| **Data status** | When each source was last copied into SEOPs. |

Labels use plain words first and the technical name second (for example "Click rate", then CTR).

### Connect a website (Setup)

1. Copy the service-account email shown in step 1 and add it in Search Console
   (Settings, Users and permissions). Do the same in GA4 (Admin, Property access
   management, Viewer role).
2. Choose the property from the list. SEOPs lists the properties the service account can
   already read. The GA4 list needs the **Google Analytics Admin API** enabled in the
   Google Cloud project; without it, type the numeric property ID by hand.
3. Click **Save Google settings**, then **Test connection**, then **Sync now**.

### Import Ahrefs data

1. In Ahrefs, open **Web Analytics** for the website, choose the period (for example Last
   30 days) and click **Export all data**. Unzip the download.
2. In SEOPs, open **Ahrefs**, click **Choose folder** and pick the unzipped folder. The page
   lists the recognised reports (top pages, entry and exit pages, channels, sources,
   devices, countries, cities, events, outbound clicks and more) and fills in the period
   from the folder name. Check the period, then **Import**.
3. The data is saved in `ahrefs_web_analytics` (one row per item, with the period) and in
   the website's `ahrefs_web_analytics` view. Import a new period every month to follow
   the trend; importing the same period again replaces it. The AI uses the latest
   import, the previous one and the changes between them.

Backlinks and Site Audit CSVs are uploaded from the same page (tabs **Backlinks** and
**Site Audit**). Ahrefs API access needs a paid Ahrefs plan, so SEOPs uses exports.

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
    │   ├── weekly_reports            weekly analysis (JSON + Markdown + AI summary)
    │   ├── ahrefs_csv_rows           every raw row of each uploaded Ahrefs CSV
    │   ├── ahrefs_web_analytics      Ahrefs Web Analytics rows, typed, one per item and import period
    │   ├── ai_conversations, ai_messages   AI chat history
    │   ├── ai_insights               structured AI advice (problem, evidence, advice, KPI)
    │   └── llm_usage                 AI requests used per UTC day
    └── <one schema per website>      e.g. dcemergencylockanddoor_com
        └── Views: site_info, daily_totals, devices, countries, pages,
                   pages_by_device, queries, ga4_pages, snapshots, index_status,
                   weekly_reports, ahrefs_rows, sync_status,
                   ai_insights, ai_conversations, ahrefs_web_analytics
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

## AI insights

An LLM reads a compact summary of one website's stored data and answers in English. It
never queries the database or Google directly. The backend sends it: 28-day totals
against the previous 28 days, daily totals, the top 25 pages and queries, devices,
countries, the weekly report's flags, sync status and the data notes. It is told to use
only these figures.

- **Insights tab** (on each website): ask a question, read the answer, and click one of
  the 2–3 suggested follow-up questions. Insights from answers appear on the right, with
  priority, target page, KPI and evidence. Managers can accept, dismiss or close them.
- **Weekly report:** an **AI analysis** section with a short summary and up to 5
  insights. Generate it with the button, or with
  `python -m app.analysis weekly --all --with-ai`. It never runs on its own, to save the
  daily quota.
- **Stored for later use:** every insight is a row in `ai_insights`, also shown as the
  view `<site_schema>.ai_insights`. Each row has `problem`, `evidence` (metric, value,
  period, `grounded`), `advice`, `target_url`, `target_kpi`, `priority` and `status`
  (`new`, `accepted`, `dismissed`, `done`). A future agent can turn accepted insights
  into website changes.
- **Checked figures:** each evidence value is compared with the data that was sent to the
  AI. A value that doesn't match is stored with `grounded: false` and shown as
  **unverified**.
- **Who can do what:** the website's creator and admins can ask questions and generate
  analyses. Other linked users can read everything.

### Configuration (`backend/.env`)

| Variable | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | empty | OpenRouter key. Empty disables AI; the UI shows "AI not configured". |
| `LLM_MODEL` | `nvidia/nemotron-3.5-super-vl:free` | Main model (any OpenRouter model ID) |
| `LLM_FALLBACK_MODELS` | `google/gemma-4-31b-it:free` | Comma-separated; the first one is tried if the main model fails |
| `LLM_REASONING_EFFORT` | `low` | `low`/`medium`/`high`, or empty to omit (reasoning models) |
| `LLM_MAX_TOKENS` | `8000` | Max reply tokens, including reasoning |
| `LLM_TIMEOUT_SECONDS` | `120` | Per request |
| `LLM_DAILY_REQUEST_BUDGET` | `45` | Requests per UTC day, counted before each call (retries and fallbacks count) |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible API |

Free OpenRouter keys allow 50 free-model requests per day; $10 of credit raises that to
1,000. Free models are often busy (HTTP 429 or 503). The app then tries the fallback
model and shows "The AI could not answer right now", so you can retry a minute later.
Only OpenRouter's per-day limit marks the day as used up. Answers take 1–2 minutes on
free models, and the Next.js proxy allows 180 seconds. On free tiers, prompts may be used
by the model provider. The data sent is aggregated SEO metrics, not credentials.

## Status

- Verified with fixture data: 371 backend tests, 98 frontend unit tests, 3 browser tests.
- Redesign checked on 2026-11-11 in a browser (desktop and phone) on a copy of the real database: every section, the Setup property list and **Test connection** (Search Console and GA4 both answered for `dcemergencylockanddoor.com`), and an Ahrefs Web Analytics import of a real export (19 reports, 35 visitors, 3 phone clicks). Screenshots of the synthetic site are in `frontend/screenshots/redesign/`.
- AI insights verified live on 2026-11-11 for `dcemergencylockanddoor.com`: one weekly analysis (5 insights) and one chat answer (5 insights), with every evidence value grounded.
- Real data: the test site `dcemergencylockanddoor.com` is connected. For 22 Sep–19 Oct 2026, Google shows 4 clicks and 2,519 impressions, and the dashboard matches after the totals fix.
- Not yet verified: the full 16-month backfill for that site, and the sitemap and GA4 operating-system collections.
- Arlington's seeded data is synthetic.

## Still needs setup

- Call-click event configured on each website (funnel's last step)
- Zone list for the geography axis
- Site Audit and backlink CSV exports (internal links and links between sites), now uploaded from the Ahrefs page
- Google Analytics Admin API enabled in the Google Cloud project, so Setup can list GA4 properties
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

