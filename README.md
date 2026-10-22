# SEOPs

SEO analytics dashboard for our local-service websites. It pulls data from Google Search Console and Google Analytics 4, stores it in PostgreSQL, and shows it per site in a web dashboard. It also produces a weekly SEO report for each site.

Ahrefs data is entered manually for now (CSV upload, planned). This project does not change the websites themselves.

## What it does

- **Google Search Console sync:** daily pages, queries, devices, clicks, impressions, CTR and position, resumable and idempotent.
- **GA4 sync:** daily sessions, users, conversions and engagement by page path, using the same resumable pattern.
- **Read API:** summaries, timeseries, page and query tables, sync status, and the latest stored report, all behind per-site access control.
- **Weekly analysis:** flags pages with high impressions and low CTR, mobile/desktop gaps, queries in positions 8–20, and clicks dropping, capped at three pages per site.
- **Dashboard:** login, site list, Overview, Search, Traffic, Ahrefs placeholder, Data status, weekly report, light and dark mode, phone and desktop layouts.

## Repository layout

backend/ FastAPI, SQLAlchemy, Alembic, sync jobs, analysis, tests
frontend/ Next.js (App Router), TypeScript, Tailwind CSS


Setup and commands live in each folder's README:
- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, Alembic, PostgreSQL 16
- Frontend: Next.js, TypeScript, Tailwind CSS, Vitest, Playwright
- Google access: service accounts (Search Console API, Analytics Data API)

## Branches

| Branch | Purpose |
|---|---|
| `main` | Stable baseline: backend, syncs, analysis API, frontend, website onboarding |
| `feat/real-data-sync` | Current work: real Google data for the first site, server-side sorting, backfill, daily automation |

Work on a feature branch and open a pull request into `main`.

## Status

- Verified with fixture data: 242 backend tests, 37 frontend unit tests, 1 browser smoke test.
- Not verified yet: real Google data. The first real site is `dcemergencylockanddoor.com`. Its Search Console access is still pending.
- Arlington's seeded data is synthetic.

## Known limits

- Sorting and pagination in the tables apply to the current page only. Server-side sorting is planned before the backfill.
- Logout clears the browser cookie, but a copied session token stays valid until it expires. Server-side sessions are planned.
- Ahrefs data is not imported automatically. The free Ahrefs plan has no API access for us.

## Secrets

- Never commit `.env` files, service-account JSON keys, or API tokens.
- Store service-account keys outside the repository, with private file permissions (`chmod 600`).
- Configure secrets through environment variables. See `backend/.env.example`.

## Roadmap

1. Real GSC and GA4 data for one site, checked against the Google UIs.
2. 16-month backfill for that site, then the other sites.
3. Server-side sorting and totals.
4. Daily automated sync (systemd timer, later n8n).
5. Ahrefs CSV upload.