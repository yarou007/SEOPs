# SEOPs frontend

Next.js App Router, strict TypeScript, and Tailwind CSS. No component or chart
library: the Overview chart is an accessible SVG with gaps for missing values.
All displayed data comes from the existing FastAPI contracts.

## Run locally

Use Node.js 24 LTS and the backend setup in [`backend/README.md`](../backend/README.md).
From `frontend/`:

```sh
npm ci
cp .env.example .env.local
PORT=3000 npm run dev
```

`BACKEND_URL` defaults to `http://localhost:8000`. It is a server-only variable;
do not prefix it with `NEXT_PUBLIC_`. Start FastAPI on that address. If you change
the backend address, restart development or rebuild the production app:

```sh
BACKEND_URL=http://localhost:8000 npm run build
PORT=3000 npm start
```

For a different frontend port, set `PORT` consistently rather than passing only
Next's `--port` flag. Server-rendered reads resolve the relative API path through
the local Next HTTP server on that port, forwarding the incoming cookie with
`cache: no-store`. They never derive an outbound host from a request header.

### Same-origin API and HTTPS

`next.config.ts` rewrites `/api/:path*` to `${BACKEND_URL}/api/:path*`.
The typed client in `lib/api.ts` uses only relative `/api/...` paths; browsers
never contact the backend origin directly. Next forwards requests and session
cookie headers, including login's `Set-Cookie`. Server components use the same
rewrite through a loopback URL because Node's fetch requires an absolute URL.
No session token is stored in localStorage or exposed to client JavaScript.

The backend cookie is always Secure. Use HTTPS for browser login, including local
testing. The supplied local TLS proxy keeps Next itself on HTTP so its server-side
loopback fetch remains local. In a second terminal, from `frontend/`:

```sh
mkdir -p .certs
openssl req -x509 -newkey rsa:2048 -nodes -days 7 \
  -keyout .certs/key.pem -out .certs/cert.pem \
  -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
npm run dev:https
```

Open <https://localhost:3443> and trust the local certificate in your browser.
`.certs/` is ignored. The helper supports `--key`, `--cert`, `--port`, and `--target`:
`npm run dev:https -- --port 3443 --target 3000`. It is a development/test proxy;
a production reverse proxy should terminate TLS in front of `npm start`.

Set the backend's existing `CORS_ORIGINS` to include the **public frontend origin**,
for example `https://localhost:3443,http://localhost:3000`, or your deployed HTTPS
origin. The backend checks the `Origin` on auth POSTs even when using a same-origin
rewrite. This is configuration, not a change to backend auth behavior.

## Pages and contracts

- `/login`: email/password form, generic invalid-credential message, pending/error states.
- `/`: checks `/api/auth/me` and redirects to `/sites` or `/login`.
- `/sites`: accessible sites only, with per-source status and last loaded dates.
- `/sites/[slug]`: Overview, Search, Traffic, Ahrefs, and Data status tabs.

Protected pages have a server-side session check. Every site page first calls
the protected `/status` endpoint, so a backend 404 becomes only **Site not found**.
The header logout button calls `/api/auth/logout`, then clears the displayed route
state by redirecting to `/login` and refreshing. No credentials are placed in URLs.

Tabs use `?tab=overview|search|traffic|ahrefs|status`. Dates use `?start=&end=`;
presets use the **backend's default end**, not a hardcoded client lag/timezone.
The default 28-day range is taken from `summary.current_window`. Custom dates
validate ordering and the same 16-calendar-month limit; backend 422 details are
also shown. Device and table offsets are preserved in the URL. Changing the range
or device resets the relevant pagination offsets.

The actual summary shape has `current`/`previous`, each with nullable `gsc` and
`ga4` objects, plus `current_window`/`previous_window`. Timeseries uses `data_date`,
`gsc_clicks`, `gsc_impressions`, `ga4_sessions`, and `ga4_users`. All types are in
`lib/types.ts`; the app does not assume a flat summary or fabricate missing zeros.
Missing numbers display as `—`; real zero stays 0. Change from a nonzero value is
relative; zero-to-zero is 0%, while a missing or zero prior baseline has no change
percentage. Lower average position is treated as an improvement.

The backend has no total-row count and no sort parameter. Tables request 26 rows
at each offset, display 25, and use the extra row only to enable Next. UI offsets
advance by 25. Clickable headings sort the **current page**, as labeled; they do
not claim to globally reorder backend pagination. GSC pagination is ordered by
impressions, GA4 by sessions. Null values sort last. Query notes and GA4 buckets
such as `(not set)` and `(other)` are retained. Errors can be retried by reloading;
route transitions have a loading state, and every data view has empty/error states.

Overview reads `/summary` and `/timeseries` and shows the latest stored weekly
report from `/report/latest`. Report reasons are shown verbatim from the saved
analysis, alongside device split and query candidates. Saved report windows are
explicitly shown because they do not change with the dashboard date filter.
Missing report files show an empty state. The Ahrefs tab is only the requested
placeholder; it makes no Ahrefs request and exposes no upload.

Data status reads the two nullable sync logs, uses the literal stored status,
and collapses error text by default. A last-loaded date **more than 5 days old**
gets a stale badge. Calendar-date age and displayed run times use UTC. Light/dark
colors follow `prefers-color-scheme`; tables scroll inside their own containers.

## Checks and browser fixtures

```sh
npm run build
npm run lint
npm run typecheck
npm test
npx playwright install chromium
```

The smoke test uses real FastAPI/PostgreSQL, not intercepted API responses.
Create a **disposable database whose name ends in `_smoke`**, then migrate and seed
it with the backend's Python environment. The fixture script refuses other names:

```sh
# From backend/, with PostgreSQL running; adapt connection credentials if needed.
createdb -h localhost -U seops seops_frontend_smoke
export DATABASE_URL=postgresql+psycopg://seops:seops@localhost:5432/seops_frontend_smoke
export SESSION_SECRET=local-frontend-smoke-secret-at-least-32-characters
export REPORTS_DIR=/tmp/seops-frontend-reports
alembic upgrade head
python ../frontend/e2e/seed_backend.py
CORS_ORIGINS=https://localhost:3443,http://localhost:3000 uvicorn app.main:app
```

The idempotent fixture seed creates five sites, an admin linked to all sites, and
a viewer linked only to Arlington. It inserts 56 days of synthetic GSC/GA4 metrics
and writes a weekly report. It never constructs a Google client. Test-only defaults:
`viewer@example.com` / `viewer-smoke-test-password`; admin uses the corresponding
`admin@example.com` / `admin-smoke-test-password`. These are disposable fixture
credentials. Existing seed users retain their passwords, matching backend seeding.

Keep the frontend on port 3000 and the TLS proxy on 3443, then from `frontend/`:

```sh
npm run test:e2e
```

Optional test variables: `E2E_BASE_URL` (default `https://localhost:3443`),
`E2E_VIEWER_EMAIL`, and `E2E_VIEWER_PASSWORD`. The test accepts the local self-signed
certificate, logs in on desktop and phone, verifies only Arlington is accessible,
opens Overview/Search/Traffic, checks the unlinked-site 404, and logs out. It saves
eight screenshots to `screenshots/`: login, sites, Overview, and Search at both widths.

## Backend change in this step

The only backend feature added is `GET /api/sites/{slug}/report/latest`, in a
separate commit. Existing analysis wrote files but exposed no read endpoint.
The new endpoint shares site authorization, returns the newest dated JSON file,
and does not trigger analysis or sync. No existing backend behavior was changed.
