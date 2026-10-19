# SEOPs backend foundation

Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, PostgreSQL 16, and Alembic.
This backend provides authentication, site-scoped read APIs, GSC/GA4 sync, and weekly analysis.
All backend commands below run from `backend/`.

## Local setup

Prerequisites: Python 3.12 and Docker Compose (or an existing PostgreSQL 16 server).

```sh
cd backend
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Alternatively, use `uv sync --locked --extra dev` and activate `.venv`. The committed
`uv.lock` records the dependency versions used for validation.

Edit `.env`: set both seed passwords and replace `SESSION_SECRET` with the output of:

```sh
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

The app rejects secrets shorter than 32 characters, including `change-me`.
`.env` is ignored by Git. Seed email addresses must be distinct; passwords must be nonempty.
Settings load from environment variables, falling back to `backend/.env` when run here.
`CORS_ORIGINS` accepts a comma-separated list of exact origins, without Markdown or JSON.

```sh
docker compose up -d --wait db
alembic upgrade head
python -m scripts.seed
python -m scripts.seed
uvicorn app.main:app --reload
```

Open <http://localhost:8000/docs>. Startup does not create or migrate tables:
Alembic is the only schema management path. For an existing PostgreSQL instance,
set `DATABASE_URL` accordingly and omit the Compose command.

### HTTPS for local cookie authentication

Session cookies always have `HttpOnly`, `Secure`, `SameSite=Lax`, and `Path=/`.
Use HTTPS for reliable browser and command-line cookie authentication; the HTTP
server above is sufficient for viewing the API docs. For local HTTPS:

```sh
mkdir -p .local-certs
openssl req -x509 -newkey rsa:2048 -nodes -days 7 \
  -keyout .local-certs/key.pem -out .local-certs/cert.pem \
  -subj '/CN=localhost' -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1'
uvicorn app.main:app --reload --ssl-keyfile .local-certs/key.pem \
  --ssl-certfile .local-certs/cert.pem
```

Trust the local certificate in your browser, then open <https://localhost:8000/docs>.
In deployment, terminate TLS at a trusted proxy. When a frontend is added, serve it
on the same site and scheme, configure its exact origin in `CORS_ORIGINS`, and send
requests with `credentials: "include"`. CORS does not override SameSite cookie rules.

## API and access

| Method | Path | Behavior |
| --- | --- | --- |
| POST | `/api/auth/login` | JSON `{email, password}`; returns `{id, email, role}` and sets cookie. Invalid credentials return generic 401. |
| POST | `/api/auth/logout` | Clears cookie; returns 204, including when already logged out. |
| GET | `/api/auth/me` | Returns `{id, email, role}`, or 401 for missing/invalid/expired sessions. |
| GET | `/api/sites` | Returns accessible sites as `[{slug, domain, display_name}]`; requires a session. |
| POST | `/api/sites` | Creates a website and links its creator. All signed-in users may create. |
| GET | `/api/sites/setup` | Credential readiness and service account email; never credential files. |
| GET | `/api/sites/{slug}/connection` | Saved Google properties, management permission, and background sync state. |
| POST | `/api/sites/{slug}/connection` | Creator/admin updates Google property settings. |
| POST | `/api/sites/{slug}/sync` | Creator/admin starts a real Google import; returns 202 immediately. |

Emails are normalized to lowercase by seeding and login. Passwords use Argon2id
through `argon2-cffi`; unknown emails still perform password verification against
a dummy hash. Auth POSTs reject an untrusted browser `Origin`; non-browser clients
without an `Origin` header are supported.

### Add websites and connect real Google data

Run `alembic upgrade head` when updating an existing installation. Migration 0002
adds nullable `sites.created_by_user_id`; existing sites remain admin-managed.
The frontend **Sites → Add website** form is available to every signed-in user.
It accepts a name, domain or homepage URL, optional GSC property, and optional
numeric GA4 property ID. Domains are normalized to lowercase ASCII/IDNA, and
slugs are generated automatically. The creator receives a `user_sites` link and
management rights; existing viewers retain read-only access to shared sites.
Admins can manage all sites. Duplicate domains are rejected without granting access.
Unknown and unlinked site URLs still return 404.

The **Data connections** page explains Google access and offers **Sync real data**.
For the administrator, configure the existing server settings (files stay on disk):

```dotenv
GSC_SERVICE_ACCOUNT_FILE=/absolute/path/to/service-account.json
# Optional: defaults to the GSC file when omitted.
GA4_SERVICE_ACCOUNT_FILE=/absolute/path/to/another-service-account.json
```

Enable the Search Console API and Google Analytics Data API in the service
account's Google Cloud project. Restart FastAPI after changing configuration.
For each website, add the service account email shown in the UI to the matching
[Search Console property](https://support.google.com/webmasters/answer/7687615)
and/or give it Viewer access to the
[GA4 property](https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart).
Domain properties use `sc-domain:example.com`; URL-prefix properties must match
the exact Google property, such as `https://www.example.com/`. GA4 uses a numeric
property ID, never a `G-` measurement ID. No Google user password, private key,
credential path, or credential parser exception is exposed through the browser.
Credential readiness only checks the local file; the import verifies Google access.

New websites start empty, without fixture data. The HTTP import always constructs
the real Google clients and **ignores `SYNC_FAKE_CLIENT`**. It uses the existing
lag, timezone, 487-day initial window, seven-day commits, retries, upserts, and
checkpoint resume logic. Sources fail independently, with diagnostics in their
existing sync logs. After a successful source import, it also saves the weekly
report. Missing credentials return 503; no configured property returns 422.
The UI polls connection state while a job runs and reports completion/errors.

Domain changes are deliberately unsupported because metrics are keyed by domain.
Properties cannot be changed after a source has a checkpoint: an administrator
must explicitly archive/reset the source's old metrics and log before reconnecting,
to prevent mixing properties or skipping history. Changes are blocked during sync.
Auth-origin checks also protect all new write routes.

This uses the existing manually provisioned, trusted user accounts and shared
server service accounts; it is not per-user Google OAuth or Google ownership
verification. Only provision users trusted to use those service accounts.
For a public signup product, add per-user OAuth/property authorization first.

For this local deployment, run **one FastAPI worker**. At most two website imports
run concurrently, with one job per site, using FastAPI background tasks. The job
registry is in memory; data/checkpoints persist in Postgres. On restart, unfinished
chunks roll back and another click resumes from committed checkpoints. Do not run
CLI imports concurrently with UI imports for the same site. Multiple API workers
or durable queued jobs require a shared job queue/lock before deployment.

`get_site_for_user(slug)` / `AccessibleSite` in `app/access.py` checks the current
user's membership or admin role and returns the same 404 for missing and unlinked
sites. All site-specific read handlers use this dependency. Tests also mount a
private route to verify the dependency independently. Admins can access all sites
even without `user_sites` links. Access
does not currently filter on `active`; it follows membership and role.

### Session storage decision

Sessions use [ItsDangerous timestamped signatures](https://itsdangerous.palletsprojects.com/en/stable/timed/)
with SHA-256, stored in the cookie. The signed payload contains only the user's UUID;
it is signed, not encrypted. No server-side session table is needed. Expiry is checked
on every request using `SESSION_MAX_AGE_SECONDS` (default 1,209,600 seconds / 14 days)
and is also sent as the cookie's `Max-Age`. The expiration is fixed from login;
requests do not renew it. User existence, role, and memberships are read from the
database, so deleting a user or changing access takes effect on existing sessions.

Logout removes the browser cookie. A copied token remains valid until expiry;
individual session revocation and password-change revocation are deferred. Rotating
`SESSION_SECRET` invalidates all existing sessions. Keep the secret stable and shared
across application instances.

Login is limited to 10 attempts per client IP in a rolling 15-minute window;
successful and failed attempts both count. Excess attempts return 429 with
`Retry-After`. The in-memory limiter is thread-safe but resets on restart and is
separate per worker. Run one worker for the current limit, or replace it with a
shared store before scaling. Uvicorn resolves client IPs: trust forwarded headers
only from known proxy addresses, never arbitrary internet clients.

## Schema and seed data

One reversible migration, `0001`, creates `users`, `sites`, `user_sites`,
`gsc_daily`, `gsc_sync_log`, `ga4_daily`, and `ga4_sync_log`, including composite
primary keys, cascading membership foreign keys, role/device/status checks, and
the GA4 `(site, page_path)` index. User/site UUIDs are generated with uuid4 in
Python or `gen_random_uuid()` for direct SQL inserts.

Daily metric and sync-log `site` columns hold **`sites.domain`, never the slug**.
These remain text keys without foreign keys, as specified. Dates, numeric precision,
nullability, and server defaults follow the requested schema. Models do not create tables.

`python -m scripts.seed` runs in one transaction and safely inserts missing records:

- `arlington` → `arlington247lockrepair.com`.
- `site2` through `site5` → `TODO-site2.example` through `TODO-site5.example`.
- Admin and viewer from `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` and
  `SEED_VIEWER_EMAIL` / `SEED_VIEWER_PASSWORD`.
- Admin memberships for all five seeded sites; viewer membership for Arlington.

Rerunning preserves existing domains, passwords, property IDs, and memberships,
and restores missing seed memberships. It does not reset passwords or remove
additional memberships. An existing seed user with a different role causes an error
and transaction rollback rather than silently changing privileges.

## Tests and checks

Create a separate test database once; the test user needs permission to create schemas:

```sh
docker compose exec db createdb -U seops seops_test
pytest
ruff check .
ruff format --check .
alembic check
```

`TEST_DATABASE_URL` defaults to
`postgresql+psycopg://seops:seops@localhost:5432/seops_test` and can be set in `.env`
or the environment. Tests create a unique private schema, run real Alembic migrations,
and drop that schema afterward. They never call `create_all()` and do not truncate
tables in the default schema. Tests require a running PostgreSQL server; database
failures fail the suite rather than silently skipping integration checks.

Coverage includes valid/invalid logins, generic failures, secure cookie flags,
session expiry/tampering/logout, login limits and window reset, viewer/admin access,
membership changes, docs paths, cascade deletion, role checks, migration
upgrade/downgrade and model parity, and two seed CLI runs preserving existing data.

## GSC sync

The standalone Python CLI pulls finalized Search Console performance data into
`gsc_daily`, using `sites.domain` as the data key and `sites.gsc_property` as the
Google API property. It does not depend on n8n or the FastAPI server.

Install the updated dependencies with `uv sync --locked --extra dev` or
`python -m pip install -e '.[dev]'`. Configure these settings in `.env` or the environment:

```dotenv
GSC_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
SYNC_LAG_DAYS=3
SYNC_TIMEZONE=UTC
```

Enable the Search Console API for the service account's Google Cloud project and
grant that service account access to each Search Console property. Store the JSON
credentials file outside the repository. Credentials are read only from that file,
with the `webmasters.readonly` scope; file contents are never logged. Set the real
`sites.gsc_property` values, for example `sc-domain:arlington247lockrepair.com`.
A missing property is skipped with status `error` and the message `gsc_property not set`.

```sh
python -m app.sync gsc --help
python -m app.sync gsc --site arlington
python -m app.sync gsc --all
python -m app.sync gsc --site arlington --from 2026-10-01 --to 2026-10-07
```

`--all` processes active sites in slug order; each site has its own error handling.
It continues after failures and exits 1 if any site failed, otherwise 0. `--site`
explicitly selects one site, including an inactive site. Unknown slugs exit 1.
`--from` and `--to` individually override the normal start/end dates, and dates are
inclusive. If both are supplied, an inverted range is rejected.

The normal end date is today's date in `SYNC_TIMEZONE` minus `SYNC_LAG_DAYS`.
The normal start is the checkpoint's `last_loaded_date + 1 day`, or `end_date - 487 days`
if there is no successful checkpoint (488 days inclusive). Timezones must be valid
IANA names and lag must be nonnegative. The scheduling timezone chooses the end date;
the date values returned by Google are stored as returned.

The sync queries oldest-first chunks of at most seven days with dimensions
`date, page, query, device` and `dataState=final`. Each chunk pages at offsets
0, 25000, 50000, etc., stopping on a page shorter than 25000 rows. Rows are upserted
in batches of at most 1000 against the complete composite primary key. Devices
are uppercased, country is `all`, counts are integers, and decimal values are rounded
to the database precision. Replays update metrics and `pulled_at` without duplicates.
See the [Google query reference](https://developers.google.com/webmaster-tools/v1/searchanalytics/query).

All pages of a chunk and its checkpoint commit together. Failure rolls back the
current chunk, preserves previous committed chunks, and records a short error
(at most 500 characters). A normal rerun resumes after the last completed chunk,
including after an outage. Empty successful chunks still advance the checkpoint.
`rows_loaded` counts rows committed during this run, not the lifetime table size;
on a no-op run it is 0. Errors do not move the checkpoint, and success clears old errors.
Historical replays do not move an existing checkpoint backward. An explicit forward
`--from` overrides the resume point, so omit it for ordinary outage recovery.

HTTP 429 and 5xx responses are retried up to five total attempts, sleeping 1, 2, 4,
then 8 seconds. Other HTTP failures are raised immediately. Retry exhaustion is
recorded as a site failure. There is no scheduler in this module: invoke the CLI
manually or from your scheduler.

### Test-only offline mode

`SYNC_FAKE_CLIENT=1` must be explicitly set in the process environment. It does not
activate from `.env`, and no other value enables it. Missing credentials never
implicitly enable fake mode. This mode writes **synthetic data to the selected
database**, so use a disposable local database. It skips all Google calls and all
credential-file reads, but still requires the site's `gsc_property` to be set.
For a seeded disposable database, set that field using SQL, for example:

```sql
UPDATE sites SET gsc_property = 'sc-domain:arlington247lockrepair.com'
WHERE slug = 'arlington';
```

```sh
SYNC_FAKE_CLIENT=1 python -m app.sync gsc --site arlington
```

The fake produces one row per requested day: page `https://<domain>/sync-fake`,
query `TEST-ONLY synthetic query`, device `MOBILE`, country `all`, clicks 3,
impressions 20, CTR 0.1500, and position 2.25. With the default first-run window it
writes 488 rows; rerunning resumes with zero rows. Logs clearly identify fake mode.

`tests/sync/test_gsc.py` uses canned clients or a mocked Google transport, blocks
Google HTTP transports, and patches retry sleep. It verifies paging, upserts,
mapping, checkpoints, chunk rollback/recovery, missing properties, retries,
per-site CLI failures, explicit fake activation, and real CLI/database writes.
The existing auth and foundation tests run alongside these tests with `pytest`.

## GA4 sync

The GA4 CLI uses `google-analytics-data` (`BetaAnalyticsDataClient`) to load daily
page metrics into `ga4_daily`. Set `sites.ga4_property_id` to the property's numeric
ID (for example `123456789`, without a `properties/` prefix).

Install the updated dependencies with `uv sync --locked --extra dev` or
`python -m pip install -e '.[dev]'`. Configuration in `.env` or the environment:

```dotenv
GA4_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
SYNC_LAG_DAYS=3
SYNC_TIMEZONE=UTC
```

If `GA4_SERVICE_ACCOUNT_FILE` is unset, it defaults to `GSC_SERVICE_ACCOUNT_FILE`.
The shared service account must have access to both services if the same file is
used. Enable the Google Analytics Data API for its Google Cloud project and grant
the service account read access to the GA4 property. Credentials are loaded only
from disk, with scope `https://www.googleapis.com/auth/analytics.readonly`. File
contents and credential parsing details are never logged. Missing credentials
produce an error; they never implicitly activate fake mode.

```sh
python -m app.sync --help
python -m app.sync ga4 --help
python -m app.sync ga4 --site arlington
python -m app.sync ga4 --all
python -m app.sync ga4 --site arlington --from 2026-10-01 --to 2026-10-07
```

`--all`, active-site filtering, per-site error isolation, exit codes, and date
overrides work the same as GSC. A missing property ID is skipped with status
`error` and exactly `ga4_property_id not set` in `ga4_sync_log.error`.

Both sources use `app/sync/common.py` for date windows, seven-day chunks, batches
of 1000, PostgreSQL upserts, checkpoint updates, and per-chunk transactions. GA4
resumes from its own `ga4_sync_log.last_loaded_date + 1 day`, independently of GSC.
The initial window starts 487 days before the end date (488 days inclusive).
The end date is today in `SYNC_TIMEZONE` minus `SYNC_LAG_DAYS`.
Successful empty chunks advance the checkpoint; failed chunks roll back all their
pages while preserving earlier commits. Errors are truncated to 500 characters,
success clears old errors, and historical overrides cannot move checkpoints backward.
As with GSC, omit `--from` for normal outage recovery because it explicitly overrides
the resume point. `rows_loaded` counts committed rows for the current run, including
updated rows, and is 0 when already up to date.

Reports request dimensions `date` and `pagePath`, and metrics `sessions`,
`totalUsers`, `conversions`, and `engagementRate`. Requests use
`properties/<ga4_property_id>` with ISO date ranges, ordered by date and page path
for stable pagination. Paging starts at offset 0
with a limit of 100000, increases the offset by the actual number of rows returned,
and stops at the report's `row_count`. An unexpectedly empty page or a changing
row count fails the chunk so an incomplete report cannot advance the checkpoint.
The wrapper uses REST transport and disables SDK retries; HTTP 429 and 5xx errors
get up to five total attempts, with sleeps of 1, 2, 4, and 8 seconds. Other errors
fail immediately. See the [Google runReport reference](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport).

Rows use `sites.domain` as `site`, parse the date dimension from `YYYYMMDD`, and
store `pagePath` verbatim as `page_path`. Paths such as `/`, `/services/`,
`(not set)`, and `(other)` are retained without adding a domain. Counts map to
integers and engagement rate is rounded to four decimal places. Upserts on
`(site, data_date, page_path)` replace all metrics and refresh `pulled_at` without
duplicating rows. No schema migration is needed for this feature.

### Test-only GA4 offline mode

The same explicitly exported `SYNC_FAKE_CLIENT=1` flag enables synthetic GA4 data.
It writes to the selected database and bypasses credentials and all Google calls.
It does not activate from `.env`; use it only against a disposable local database.
Set a placeholder property ID on the seeded Arlington site first:

```sql
UPDATE sites SET ga4_property_id = '123456789' WHERE slug = 'arlington';
```

```sh
SYNC_FAKE_CLIENT=1 python -m app.sync ga4 --site arlington
```

The fake produces one row per requested day with path `/sync-fake/`, sessions 20,
total users 15, conversions 2, and engagement rate 0.7500. A default first run
writes 488 rows. The flag and synthetic writes are clearly identified in logs.

`tests/sync/test_ga4.py` uses fake clients or mocked SDK responses, blocks HTTP
transports, and patches retry sleep. It covers 150000-row paging, date/path mapping,
upsert updates, independent resume checkpoints, chunk and page rollback/recovery,
incomplete reports, missing properties, retries, credential fallback, CLI isolation,
and fake-mode activation. Run `pytest` to include all GA4, GSC, and auth tests.

## Read API

All read endpoints require the existing session cookie and use
`get_site_for_user`: unauthenticated requests return 401; an unlinked or missing
site returns the same 404. Responses have `Cache-Control: no-store`.
The prefix is `/api/sites/{slug}`:

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/summary?start&end` | `current_window`, `previous_window`, and `current`/`previous` source totals. |
| GET | `/timeseries?start&end` | One row per day with `data_date`, `gsc_clicks`, `gsc_impressions`, `ga4_sessions`, `ga4_users`. |
| GET | `/gsc/pages?start&end&device` | `page`, clicks, impressions, CTR, and weighted average position. |
| GET | `/gsc/queries?start&end&device` | `query`, clicks, impressions, CTR, weighted average position, `top_page`. |
| GET | `/ga4/pages?start&end` | `page_path`, sessions, total users, conversions, weighted engagement rate. |
| GET | `/status` | `gsc` and `ga4` sync-log records, or `null` for a missing log. |
| GET | `/report/latest` | Latest dated stored report JSON for this site. Returns 404 if no report exists. |

`start` and `end` are inclusive ISO dates. The default end is today in
`SYNC_TIMEZONE` minus `SYNC_LAG_DAYS`; the default start is end minus 27 days.
This is a 28-day window. Summary compares it to the immediately preceding window
of equal inclusive length. For example:

```text
GET /api/sites/arlington/summary?start=2026-10-01&end=2026-10-07
GET /api/sites/arlington/gsc/pages?start=2026-10-01&end=2026-10-07&device=MOBILE&limit=25&offset=0
```

Ranges over 16 **calendar** months, inverted ranges, and invalid dates return 422.
The oldest allowed start is end minus 16 months, clamped to the last day of a shorter
month. Device accepts exactly `MOBILE`, `DESKTOP`, or `TABLET`; omit it for all devices.
The three table endpoints support `limit` (1–1000, default 100) and nonnegative `offset`.
GSC tables sort by impressions descending, breaking ties by page/query alphabetically.
GA4 has no impression metric, so its pages sort by sessions descending, then path.
A query's top page is the page with most impressions for that query in the same
window and device filter; ties use clicks descending, then page alphabetically.
Blank query strings are omitted from query tables.

`summary.current` and `.previous` each contain `gsc` and `ga4`:

```json
{
  "gsc": {"clicks": 20, "impressions": 800, "ctr": 0.025, "avg_position": 8.25},
  "ga4": {"sessions": 45, "total_users": 32, "conversions": 4}
}
```

A source is `null` if no rows exist for it in that window. Existing rows with zero
traffic remain zero. Timeseries also preserves this distinction: missing source/day
values are `null`, while present zero rows return 0. Empty table results are `[]`.
CTR is `SUM(clicks) / SUM(impressions)`, never an average of stored CTRs. Position
is `SUM(position * impressions) / SUM(impressions)`. Both are `null` when total
impressions are zero. GA4 engagement rate is session-weighted and is `null` when
total sessions are zero. Counts are integers; ratios are rounded to four decimal
places and positions to two, only when presenting results. Analysis uses unrounded
Decimal values for comparisons. SQL aggregation is shared in `app/metrics.py`.

The source tables impose two limits on interpretation: stored GSC rows contain
query dimensions, so page aggregates cannot reconstruct hidden-query traffic;
GA4 total users are summed daily/page counts, not unique people deduplicated across
the whole window. The weekly report includes both limitations in its data notes.

## Weekly analysis

The CLI reads only local PostgreSQL tables. It makes no Google calls and does not
run a sync. It writes the same report data as JSON and short Markdown, without charts:

```sh
python -m app.analysis weekly --site arlington
python -m app.analysis weekly --all
```

Set `REPORTS_DIR` in `.env` or the environment (default `reports/`, relative to the
working directory). Files are written to
`<REPORTS_DIR>/<slug>/<report-date>.json` and `.md`. The filename uses the **run date
in `SYNC_TIMEZONE`**, while the data window ends at run date minus `SYNC_LAG_DAYS`.
Rerunning on the same date replaces that date's files. Default generated reports
are ignored by Git. `--all` includes active sites and continues after site failures;
it exits 1 if any site failed, otherwise 0. Explicit `--site` can select an inactive site.

The frontend reads the saved JSON through `GET /api/sites/{slug}/report/latest`.
It uses the same site-access dependency, selects the newest valid date filename,
and never runs analysis or sync as part of a request. Missing reports return 404;
unreadable, invalid, or mismatched stored JSON returns a generic 503. Symlinks
outside the site's report directory are ignored. Existing read/sync behavior is unchanged.

The report includes the site and all four inclusive windows:

- `current`: 28 days ending at the configured lagged end date.
- `previous`: the 28 days immediately before `current`.
- `last7`: the last seven days of `current`.
- `prev7`: the seven days immediately before `last7`.

All tunable cutoffs, limits, position bands, and tie priorities live in
`ANALYSIS_THRESHOLDS` in `app/analysis/weekly.py`:

| Check | Threshold | Reason |
| --- | --- | --- |
| Low CTR | Current page impressions ≥ 200 and CTR < 50% of its band's median page CTR | high impressions, CTR below band median |
| Mobile gap | Each device has ≥ 100 impressions; mobile CTR < 70% of desktop CTR | mobile CTR gap |
| Query opportunity | Current query impressions ≥ 50 and weighted position 8–20 inclusive | position 8–20, close to page 1 |
| Weekly clicks | Previous seven days clicks ≥ 20 and last seven days clicks < 60% of them | clicks down X% week over week |
| Zero clicks | Current impressions ≥ 100 and clicks = 0 | 100+ impressions, no clicks |
| 28-day trend | Previous 28 days clicks ≥ 20 and current clicks down **more than** 30% | clicks down X% vs previous 28 days |

Position bands use fractional, half-open intervals `[1,4)`, `[4,8)`, `[8,11)`,
`[11,21)`, and `[21,∞)`, labeled 1–3, 4–7, 8–10, 11–20, 21+. Thus 3.9 is in 1–3
and 4.0 is in 4–7. Median CTR includes all current pages with positive impressions
and a known position in that band, including the page being assessed. Unknown
positions are excluded from the band comparison. A page without both eligible
mobile and desktop data is skipped for the mobile-gap check; zero desktop CTR
cannot produce a gap flag.

Each flagged page is kept once. For low CTR, zero clicks, and the 28-day trend,
`impressions_lost = max(0, impressions × (band_median_ctr − page_ctr))`; a missing
benchmark yields 0. This is the requested field name for an estimated click
opportunity, not a literal count of missing impressions. Other checks use 0 for
this ranking value. The strongest flag is the one with the highest estimate; ties
prefer zero clicks, 28-day trend, weekly clicks, low CTR, then mobile gap. Unique
pages rank by estimate descending, then impressions descending, then URL. The
report shows at most **3** pages and always shows the full unique flagged-page count.
Query candidates are separate from that page count, with at most **10**, ordered
by impressions and carrying their top page.

If the current GSC source is entirely missing, no click-drop claims are made.
Within an available current source, a page absent from a comparison window counts
as zero clicks, so a disappearing page can still be flagged. Missing positions
can still yield zero-click or trend flags, with an opportunity estimate of 0.

Reports include current/previous source totals, MOBILE/DESKTOP clicks, impressions,
CTR and position, sync-log status, query candidates, and data notes. Sync is stale
when `(today − last_loaded_date).days > SYNC_LAG_DAYS + 2`; equality is not stale.
Missing checkpoints and failed syncs also produce visible warnings. The data notes
explain hidden GSC queries, page totals as the main figures, missing data, and GA4
user-count limitations. JSON preserves the data and Markdown presents the same
windows, warnings, totals, selected flags, and query candidates.

To review the existing synthetic sync data in a disposable local database, run the
analysis command normally. `SYNC_FAKE_CLIENT` is unnecessary because analysis does
not construct any Google client. The tests use fixture data and temp report folders:

```sh
pytest tests/test_read_api.py tests/analysis
pytest
```

## Deferred work

- Replace the four `TODO-site*.example` domains and set real display names,
  GSC properties, and GA4 property IDs.
- Ahrefs tables/integration and the frontend.
- Distributed rate limiting and individual session revocation when needed.
