# SEOPs backend foundation

Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, PostgreSQL 16, and Alembic.
This step provides database tables, authentication, and site authorization.
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

Emails are normalized to lowercase by seeding and login. Passwords use Argon2id
through `argon2-cffi`; unknown emails still perform password verification against
a dummy hash. Auth POSTs reject an untrusted browser `Origin`; non-browser clients
without an `Origin` header are supported.

`get_site_for_user(slug)` / `AccessibleSite` in `app/access.py` checks the current
user's membership or admin role and returns the same 404 for missing and unlinked
sites. Future site-specific handlers must use this dependency. No site detail
handler is shipped in this step; tests mount a private route to verify direct-URL
authorization. Admins can access all sites even without `user_sites` links. Access
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

## Deferred work

- Replace the four `TODO-site*.example` domains and set real display names,
  GSC properties, and GA4 property IDs.
- Sync jobs, GSC/GA4 read endpoints, Ahrefs tables/integration, and the frontend.
- Distributed rate limiting and individual session revocation when needed.
