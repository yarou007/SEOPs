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

Work on a feature branch and open a pull request. Don't push straight to `main`.

## Status

- Verified with fixture data: 284 backend tests, 59 frontend unit tests, 3 browser tests.
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

