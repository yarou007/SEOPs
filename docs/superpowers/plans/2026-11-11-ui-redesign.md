# UI/UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SEOPs a professional, easy dashboard: app shell, self-explaining Overview, guided Setup with
property pickers and a connection test, a real Ahrefs page with a Web Analytics "all stats" import, and
cleaner AI Insights and Analysis pages.

**Architecture:** Backend adds three small additive pieces (Ahrefs Web Analytics parser + router, Google
property listing/test endpoints, an Ahrefs block in the AI context). Frontend adds `lucide-react`, a set of
UI primitives and an app shell, and pure `lib/` helpers (plain-language explanations, Ahrefs file
recognition) that pages use; pages are restyled on top of the existing data loaders.

**Tech Stack:** Next.js 16 / React 19 / Tailwind 4 / Recharts / Vitest; FastAPI / SQLAlchemy 2 / pytest /
google-api-python-client.

**Spec:** `docs/superpowers/specs/2026-11-11-ui-redesign-design.md`

## Global Constraints

- Branch `feat/ui-redesign`; base `feat/ai-insights`.
- Existing API contracts and tests stay; new endpoints only add.
- One new frontend dependency: `lucide-react` pinned to an exact version (no `^`).
- Manager-only writes use `require_manager` and `Depends(check_auth_origin)`; reads use `AccessibleSite`.
- Options endpoint returns the full, unfiltered property list to any manager (owner's decision).
- Ahrefs Web Analytics: recognise files by header row; 2 MB total decoded text; ≤ 20,000 rows per file;
  page URLs (TopPages/EntryPages/ExitPages) must belong to the site; same period re-import replaces.
- Plain-language label first, technical name second; colour never the only signal; phone width without
  horizontal page scroll.
- Never print or commit secrets; `*_ahrefs_*/` export folders stay ignored.
- Backend tests: `/home/amirben/Documents/hammi/.seops-local/pytest.sh -q`.
  Frontend: `cd frontend && npm test && npm run typecheck && npm run lint` with
  `PATH=/home/amirben/Documents/hammi/.seops-local/node-v24.22.0-linux-x64/bin:$PATH`.
- After code changes, `cd /home/amirben/Documents/hammi && graphify update .`.

## Review Focus

1. A Web Analytics file with a BOM-only body, `"1."`/`"0."` rates, or an unknown header: empty skipped,
   rates parsed, unknown reported — never a 500.
2. A viewer (non-manager) calling options/test/import endpoints gets 403; another site's slug gets 404.
3. Google APIs disabled or credentials missing: options returns empty list + safe message (no file paths,
   no exception text), UI falls back to manual entry.
4. Overview headline with no previous baseline or no GSC data says so instead of a misleading percentage.
5. Insights conversation select and suggestion chips are disabled while an answer is loading.

---

### Task 1: Ahrefs Web Analytics parser and import service

**Files:**
- Create: `backend/app/analysis/web_analytics.py`, `backend/alembic/versions/0007_ahrefs_web_analytics.py`
- Modify: `backend/app/models.py` (model `AhrefsWebAnalytics`), `backend/tests/conftest.py` (TRUNCATE list),
  `backend/tests/test_foundation.py` (table list if enumerated)
- Test: `backend/tests/analysis/test_web_analytics.py`, `backend/tests/test_unified_database.py`

**Interfaces:**
- Produces:
  - `REPORTS: dict[str, tuple[str, ...]]` — report key → normalised header signature.
    Keys: `top_pages, entry_pages, exit_pages, channels, sources, devices, browsers, os, countries,
    cities, continents, languages, utm_campaign, utm_content, utm_medium, utm_source, utm_term, events,
    outbound_links`.
  - `class WebAnalyticsFile(BaseModel): name: str (max 200); content: str`
  - `parse_export(files: list[WebAnalyticsFile], site_domain: str) -> ParsedExport` where
    `ParsedExport = {"reports": {key: list[dict]}, "raw": {key: list[dict]}, "empty": [name], "unknown":
    [name]}`. Row dicts use snake_case keys: `name|page|href`, `visitors`, `views`, `entrances`, `exits`,
    `exit_rate`, `bounce_rate`, `visit_duration`, `time_on_page`, `count`, `conversion_rate` (ints for
    counts, floats for rates/durations).
  - `import_web_analytics(db, site: Site, period_start: date, period_end: date, files) -> AxisSnapshot`
    storing `AxisSnapshot(kind="web-analytics", start_date, end_date, data={"reports":..., "totals":...,
    "files": {"recognised": n, "empty": [...], "unknown": [...]}})` and raw rows in `AhrefsCsvRow` with
    `kind="web-analytics:<key>"`; deletes an earlier `web-analytics` snapshot with the same start/end
    first (raw rows cascade).
  - `totals = {"visitors": sum(channels.visitors), "phone_clicks": sum(outbound_links.count where href
    starts with "tel:"), "pages": len(top_pages)}`.
  - Typed table `ahrefs_web_analytics` (model `AhrefsWebAnalytics`): `id` identity PK, `snapshot_id` FK
    axis_snapshots ON DELETE CASCADE, `site` `site_fk()`, `period_start`, `period_end` (date),
    `report` text, `item` text, numeric nullable columns `visitors, views, entrances, exits` (int),
    `exit_rate, bounce_rate, visit_duration, time_on_page, conversion_rate` (numeric), `count` (int),
    `imported_at` timestamptz default now(); index (site, report, period_end). One row per parsed row.
  - Migration 0007: create the table; add view `ahrefs_web_analytics` to each per-site schema by
    rebuilding `_refresh_function(base, extra_views)` with 0006's AI views plus the new one (load 0005
    and 0006 via importlib like 0006 does); downgrade restores 0006's function and drops the table.
  - `latest_web_analytics(db, domain) -> AxisSnapshot | None` (newest `collected_at`) and
    `previous_web_analytics(db, domain, before: AxisSnapshot) -> AxisSnapshot | None` (newest import whose
    `end_date` < `before.start_date`, else newest other import with an earlier `end_date`).
  - `compare_imports(latest: dict, previous: dict | None) -> dict` → `{"visitors": {"now", "before",
    "change_percent"}, "phone_clicks": {...}, "bounce_rate": {...} (visitor-weighted from channels),
    "pages": [{"page", "visitors_now", "visitors_before"}] (top 10 of latest)}`; `None` previous → `{}`.

- [ ] **Step 1: Write failing tests** using fixture text copied from the example export (tab-separated,
  quoted; built in the test, not read from the ignored folder):
  - `test_recognises_reports_by_header`: TopPages vs ExitPages (both start with "Page") map to
    `top_pages` / `exit_pages`; a file named `Whatever.csv` with Channel header maps to `channels`.
  - `test_parses_fraction_rates_and_counts`: `"1."` → 1.0, `"0."` → 0.0, `"0.5625"` → 0.5625,
    `"16"` → 16.
  - `test_empty_and_unknown_files_are_reported`: `""` content → `empty`; header `"Foo"\t"Bar"` → `unknown`.
  - `test_rejects_pages_outside_site`: TopPages row `https://evil.example/` → `ValueError`.
  - `test_rejects_no_recognised_report`, `test_rejects_over_2mb`, `test_rejects_over_20000_rows`.
  - `test_import_stores_snapshot_totals_and_raw_rows`: visitors 35 (26+8+1), phone_clicks 3, raw rows
    count equals parsed rows, kinds `web-analytics:channels` etc.
  - `test_reimport_same_period_replaces`: two imports, same dates → one snapshot; different dates → two.
  - `test_typed_rows_stored`: `ahrefs_web_analytics` rows equal parsed rows; `"0.5625"` exit_rate stored.
  - `test_compare_imports`: visitors 35 vs 20 → change 75.0; no previous → `{}`.
  - In `test_unified_database.py`: the per-site schema exposes `ahrefs_web_analytics` with only that
    site's rows; migration up/down/up keeps rows (follow the existing view tests).
- [ ] **Step 2: Run** `.seops-local/pytest.sh -q tests/analysis/test_web_analytics.py` — Expected: FAIL
  (module missing).
- [ ] **Step 3: Implement** with `csv.reader(delimiter="\t")`, header normalised with `_header` from
  `csv_sources`, `domain()` for page URL checks, `db.flush()` before inserts like `import_csv`.
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Commit** `feat(ahrefs): parse and store Ahrefs Web Analytics exports`.

### Task 2: Ahrefs router

**Files:**
- Create: `backend/app/routers/ahrefs.py`; Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_ahrefs_api.py`

**Interfaces:**
- Consumes: Task 1 `import_web_analytics`, `latest_web_analytics`, `WebAnalyticsFile`.
- Produces:
  - `POST /api/sites/{slug}/ahrefs/web-analytics` body `{period_start: date, period_end: date, files:
    [WebAnalyticsFile] (1..40)}` → 201 `WebAnalyticsResponse`; 400 on `ValueError` with its message;
    422 when `period_end < period_start`; manager-only; origin check.
  - `GET /api/sites/{slug}/ahrefs` → `{"web_analytics": WebAnalyticsResponse | null, "previous":
    {period_start, period_end, totals} | null, "changes": compare_imports(...) , "history": [{period_start,
    period_end, visitors, phone_clicks}] (all imports, oldest first), "backlinks":
    UploadInfo | null, "internal_links": UploadInfo | null}` where `WebAnalyticsResponse = {id,
    period_start, period_end, imported_at, totals, reports, files}` and `UploadInfo = {imported_at,
    rows}` (rows = count of `AhrefsCsvRow` for that snapshot).
- [ ] **Step 1: Failing tests:** `test_import_requires_manager_and_origin` (viewer on a site they did not
  create → 403; bad Origin → 400; anonymous → 401), `test_import_then_get_returns_latest`,
  `test_get_unknown_site_404`, `test_bad_file_returns_400_message`, `test_period_order_422`,
  `test_get_includes_backlinks_upload_info` (upload via existing `/axes/imports`).
- [ ] **Step 2: Run** `.seops-local/pytest.sh -q tests/test_ahrefs_api.py` — Expected: FAIL (404 routes).
- [ ] **Step 3: Implement** following `routers/insights.py` patterns (no_store, `AccessibleSite`,
  `require_manager` from `routers.sites`). Add `ahrefs` route paths to `test_foundation` route list if it
  enumerates routes.
- [ ] **Step 4: Run** full backend suite — Expected: all pass.
- [ ] **Step 5: Commit** `feat(ahrefs): Web Analytics import and summary endpoints`.

### Task 3: Google property options and connection test

**Files:**
- Create: `backend/app/google_admin.py`; Modify: `backend/app/routers/sites.py`
- Test: `backend/tests/test_connection_tools.py`

**Interfaces:**
- Produces:
  - `list_gsc_properties(path: Path | None) -> list[str]` (searchconsole v1 `sites().list()`,
    `siteEntry[].siteUrl`, sorted).
  - `list_ga4_properties(path: Path | None) -> list[dict]` (`analyticsadmin` v1beta
    `accountSummaries().list(pageSize=200)` paged; each `{"id": "<digits>", "name": displayName,
    "account": account displayName}`).
  - `test_gsc(path, property) -> (bool, str)`; `test_ga4(path, property_id) -> (bool, str)` using one
    1-row query over the last 7 days through the existing `GscClient` / `Ga4Client`.
  - Any exception → safe fixed messages, e.g. "Could not list Search Console properties. Check the
    service account and that the API is enabled." Never include exception text.
  - Routes in `sites.py`: `GET /{slug}/connection/options` →
    `{"gsc": {"properties": [...], "error": str|None}, "ga4": {"properties": [...], "error": str|None}}`
    (manager-only); `POST /{slug}/connection/test` (manager-only, origin) →
    `{"gsc": {"ok": bool, "message": str}, "ga4": {...}}`; unsaved property → `ok false, "Not set up"`.
  - Router imports the functions as module attributes (`from app import google_admin`) so tests
    monkeypatch `app.google_admin.list_gsc_properties` etc.
- [ ] **Step 1: Failing tests:** options returns faked lists for a manager; viewer of a seeded site
  (not creator) → 403; listing raising → empty list + safe message that contains no exception text;
  test endpoint ok/failed/"Not set up" cases; origin check on test.
- [ ] **Step 2: Run** `.seops-local/pytest.sh -q tests/test_connection_tools.py` — Expected: FAIL.
- [ ] **Step 3: Implement.** Scopes: GSC `webmasters.readonly`, GA4 `analytics.readonly`.
- [ ] **Step 4: Run** full backend suite — Expected: pass.
- [ ] **Step 5: Commit** `feat(setup): list Google properties and test connections`.

### Task 4: Ahrefs data in the AI context

**Files:** Modify `backend/app/insights/context.py`; Test `backend/tests/insights/test_context.py`

**Interfaces:**
- Consumes: Task 1 `latest_web_analytics`.
- Produces: `context["ahrefs_web_analytics"] = {"period": {start, end}, "totals": {...}, "top_pages":
  first 10, "channels", "sources": first 10, "devices", "events", "previous": {period, totals} | null,
  "changes": compare_imports(...), "history": [...]}` built from the `ahrefs_web_analytics` table, or
  omitted when no import.
  `render_context` trims it after `top_queries` if over the limit.
- [ ] **Step 1: Failing tests:** block present with totals after an import; absent without; with two
  imports of different periods, `previous` and `changes` hold the right numbers; its numbers appear in
  `context_numbers` (so they ground).
- [ ] **Step 2: Run** `.seops-local/pytest.sh -q tests/insights/test_context.py` — Expected: FAIL.
- [ ] **Step 3: Implement.** Add one line to SYSTEM_PROMPT data notes: Ahrefs Web Analytics is a separate
  visitor tracker; its counts differ from GA4.
- [ ] **Step 4: Run** full backend suite — Expected: pass.
- [ ] **Step 5: Commit** `feat(ai): include Ahrefs Web Analytics in the AI context`.

### Task 5: Frontend foundation — tokens, primitives, app shell

**Files:**
- Modify: `frontend/package.json` (+`lucide-react` exact), `frontend/app/globals.css`,
  `frontend/app/(dashboard)/layout.tsx`, `frontend/app/(dashboard)/sites/[slug]/page.tsx` (remove the
  in-page tab bar; sections come from the sidebar)
- Create: `frontend/components/ui/{page-header,card,stat-card,info-tip,status-pill,collapsible,steps}.tsx`,
  `frontend/components/shell/{sidebar,site-switcher}.tsx`, `frontend/lib/nav.ts`
- Test: `frontend/tests/nav.test.ts`

**Interfaces:**
- Produces:
  - `SECTIONS: {key, label, icon, href(slug)}[]` in order Overview, Search, Traffic, Analysis,
    AI Insights (`insights`), Ahrefs, Setup (`/sites/[slug]/settings`), Data status.
  - `sectionHref(slug: string, key: string, query?: URLSearchParams): string` — keeps `start`/`end`,
    drops pagination offsets (same rule as today's `link()`), Setup ignores query.
  - `activeSection(pathname: string, tab: string | null): string`.
  - `slugFromPath(pathname: string): string | null`.
  - `StatusPill` kinds: `connected | action | off | syncing | error` with icon + text.
  - `InfoTip({label, children})`: button with accessible name "What is <label>?" revealing text
    (popover via `details`/state; works with keyboard).
- [ ] **Step 1: Failing tests** for `sectionHref` (keeps dates, drops offsets, encodes slug, settings
  path), `activeSection` (settings path → setup; `?tab=insights` → insights; default overview),
  `slugFromPath`.
- [ ] **Step 2: Run** `npm test -- nav` — Expected: FAIL.
- [ ] **Step 3: Implement** `lib/nav.ts`, then load superpowers frontend-design guidance and build tokens
  (refined neutrals, one accent, dark mode via existing tokens), primitives and shell: sidebar (client
  component using `usePathname`/`useSearchParams`) with site switcher (sites list passed from layout),
  user + logout at the bottom; on < lg a top bar with a menu button opening the sidebar as a drawer.
- [ ] **Step 4: Run** `npm test && npm run typecheck && npm run lint` — Expected: pass.
- [ ] **Step 5: Commit** `feat(ui): app shell, sidebar navigation and UI primitives`.

### Task 6: Plain-language explanations and the Overview

**Files:**
- Create: `frontend/lib/explain.ts`; Test: `frontend/tests/explain.test.ts`
- Modify: `frontend/components/kpis.tsx`, `frontend/components/weekly-report.tsx`,
  `frontend/components/weekly-ai.tsx`, Overview in `sites/[slug]/page.tsx`
- Create: `frontend/components/overview/{headline,next-actions,top-insights}.tsx`

**Interfaces:**
- Produces:
  - `GLOSSARY: Record<"clicks"|"impressions"|"ctr"|"position"|"sessions"|"users"|"conversions"|
    "bounce_rate"|"entrances"|"exit_rate"|"visitors", {label: string; technical: string; help: string;
    higherIsBetter: boolean}>` (e.g. ctr → label "Click rate", technical "CTR").
  - `headline(summary: Summary, report: WeeklyReport | null): {text: string; tone: "good"|"bad"|
    "neutral"}` — e.g. "Clicks from Google fell 10.9% compared with the previous 28 days." With
    no previous clicks: "No earlier period to compare yet." With no GSC data: "No Search Console data for
    this period yet." Appends "The biggest drop is on <path>." only from a `clicks_dropping` or `trend`
    flag in `report.top_pages`, labelled "(weekly report, <report window>)".
  - `nextActions(report: WeeklyReport | null, limit = 5): {page: string; title: string; detail: string;
    check: string}[]` — templates per check: `zero_clicks` → "Rewrite the title and description of
    <path>" / "Shown N times on Google with no clicks."; `low_ctr` → "Improve the search snippet of
    <path>" / "Click rate X% vs Y% typical at this position."; `clicks_dropping`/`trend` → "Check what
    changed on <path>" / "Clicks down D% vs the previous period."; `mobile_gap` → "Fix the mobile page
    of <path>" / "Mobile click rate X% vs desktop Y%."; plus `query_candidates` → "Push <query> onto
    page 1" / "Ranks P with N impressions."; numbers formatted with existing `lib/format`.
- [ ] **Step 1: Failing tests:** each template (exact strings with real numbers), limit, headline cases
  (fell / rose / unchanged / no baseline / no GSC / with flag page), glossary has label+technical for
  every key.
- [ ] **Step 2: Run** `npm test -- explain` — Expected: FAIL.
- [ ] **Step 3: Implement** helpers, then the Overview: headline card, 4 main StatCards (clicks,
  impressions, ctr, position with InfoTip and change badge coloured by `higherIsBetter`), GA4 row,
  chart card, "What to do next" card, AI card (weekly AI summary + top 3 open insights from
  `api.insights(slug, {status: "open"})`), and the full weekly report in Collapsibles (content
  unchanged). Weekly AI button text "Uses 1–4 of today’s AI requests" (fixes deferred minor).
- [ ] **Step 4: Run** `npm test && npm run typecheck && npm run lint` — Expected: pass.
- [ ] **Step 5: Commit** `feat(ui): self-explaining Overview with next actions`.

### Task 7: Setup page

**Files:**
- Modify: `frontend/lib/api.ts`, `frontend/lib/types.ts`, `frontend/app/(dashboard)/sites/[slug]/settings/page.tsx`,
  `frontend/components/site-connection.tsx`, `frontend/components/connection-fields.tsx`,
  `frontend/components/google-setup.tsx`
- Create: `frontend/lib/setup.ts`; Test: `frontend/tests/setup.test.ts`

**Interfaces:**
- Consumes: Task 3 endpoints; Task 2 `GET /ahrefs`.
- Produces:
  - api: `connectionOptions(slug)`, `testConnection(slug)`, `ahrefs(slug)`.
  - `sourceState(connection: SiteConnection, source: "gsc"|"ga4", test?: TestResult):
    "connected"|"action"|"off"|"syncing"|"error"` and `setupProgress(states): {done: number; total: 3}`.
- [ ] **Step 1: Failing tests** for `sourceState` (no property → off; property + credentials not
  configured → action; test failed → error; running sync → syncing; property + configured → connected)
  and `setupProgress`; api path tests for the three new calls.
- [ ] **Step 2: Run** `npm test -- setup` — Expected: FAIL.
- [ ] **Step 3: Implement** the page: header "Connect your data" + progress, three step cards (GSC, GA4
  with copyable service-account email, picker `<select>` filled from options with "Enter manually"
  toggle that shows the existing input + validation, Save, Test connection with result text; Ahrefs step
  with last imports and a link to the Ahrefs page), Sync card (existing polling, per-source last loaded
  date from `api.status`). Viewers see read-only states.
- [ ] **Step 4: Run** `npm test && npm run typecheck && npm run lint` — Expected: pass.
- [ ] **Step 5: Commit** `feat(ui): guided setup with property pickers and connection test`.

### Task 8: Ahrefs page and import

**Files:**
- Create: `frontend/lib/ahrefs.ts`, `frontend/components/ahrefs/{import-card,web-analytics-view}.tsx`
- Modify: `frontend/lib/api.ts`, `frontend/lib/types.ts`, Ahrefs branch in `sites/[slug]/page.tsx`,
  `frontend/components/axis-upload.tsx` (reuse inside import card)
- Test: `frontend/tests/ahrefs.test.ts`

**Interfaces:**
- Consumes: Task 2 endpoints.
- Produces:
  - `decodeExport(bytes: Uint8Array): string` (UTF-16 LE/BE BOM, else UTF-8, fatal).
  - `recogniseReport(text: string): ReportKey | "empty" | "unknown"` — same signatures as backend
    `REPORTS`.
  - `periodFromFolder(name: string, today: Date): {start: string; end: string}` — parses
    `_YYYY-MM-DD_HH-MM-SS` → the 30 days ending on that date (Ahrefs' "Last 30 days" includes today); fallback 30 days ending today.
  - `api.importWebAnalytics(slug, {period_start, period_end, files})` (timeout 60 s).
- [ ] **Step 1: Failing tests:** decode UTF-16 LE with BOM; recognise TopPages vs ExitPages; empty BOM-only
  → empty; unknown; `periodFromFolder("dcemergencylockanddoor_all-stats_ahrefs_2026-11-11_21-23-17")` →
  `{start: "2026-10-13", end: "2026-11-11"}` (matches the Ahrefs screen "13 Oct – 11 Nov 2026"); fallback.
- [ ] **Step 2: Run** `npm test -- ahrefs` — Expected: FAIL.
- [ ] **Step 3: Implement** the page: header, Import card with three tabs (Web Analytics: file input with
  `multiple` and a "Choose folder" input with `webkitdirectory`, preview list "N reports recognised, E
  empty, U unknown", period inputs, Import button; Backlinks and Site Audit: existing `AxisUpload` with
  "How to export" steps), then the imported-data view (StatCards visitors, phone clicks, pages; tables
  for top pages, entry/exit pages, channels, sources, devices, countries, events with GLOSSARY labels).
  A "Change since the previous import" strip (visitors, phone clicks, bounce rate with arrows and the two
  periods named) and a small history chart of visitors per import when there are 2+ imports.
  Viewers see data, not the import controls.
- [ ] **Step 4: Run** `npm test && npm run typecheck && npm run lint` — Expected: pass.
- [ ] **Step 5: Commit** `feat(ui): Ahrefs page with Web Analytics import`.

### Task 9: AI Insights polish

**Files:** Modify `frontend/components/insights-panel.tsx`, `frontend/components/insight-card.tsx`,
`frontend/lib/insights.ts`; Test `frontend/tests/insights.test.ts`

**Interfaces:**
- Produces: `filterInsights(items: AiInsight[], status: InsightStatus | "all", priority: "all"|"high"|
  "medium"|"low"): AiInsight[]` (then `sortInsights`), `quotaPercent(usage: UsageInfo): number`.
- [ ] **Step 1: Failing tests** for `filterInsights` and `quotaPercent` (0 budget → 0; exhausted → 100).
- [ ] **Step 2: Run** `npm test -- insights` — Expected: FAIL.
- [ ] **Step 3: Implement** bubbles, chips, quota bar, filters, priority stripe, evidence chips; disable
  the conversation select while busy; show "AI status could not be loaded" when `initialUsage` is null
  (fixes deferred minors).
- [ ] **Step 4: Run** `npm test && npm run typecheck && npm run lint` — Expected: pass.
- [ ] **Step 5: Commit** `feat(ui): clearer AI Insights chat and insight filters`.

### Task 10: Analysis, Search, Traffic, Data status, Sites list, Login restyle

**Files:** Modify `frontend/components/{analysis,data-table,status-table,date-control,login-form}.tsx`,
`frontend/app/(dashboard)/sites/page.tsx`, `frontend/app/login/page.tsx`, Search/Traffic in
`sites/[slug]/page.tsx`

- [ ] **Step 1:** Analysis: sticky contents, takeaway line per section, Collapsible bodies (first open),
  replace `AxisUpload` with a link "Upload Ahrefs exports on the Ahrefs page". Existing
  `tests/analysis.test.ts` must stay green.
- [ ] **Step 2:** Tables: GLOSSARY labels with technical names in column headers' title text; Search/
  Traffic/Data status in Cards with PageHeaders; Sites list cards with StatusPills; Login centred card.
- [ ] **Step 3: Run** `npm test && npm run typecheck && npm run lint && npm run build` — Expected: pass.
- [ ] **Step 4: Commit** `feat(ui): restyle analysis, tables, sites list and login`.

### Task 11: Docs and real-browser check

- [ ] **Step 1:** README: update the frontend section (navigation, Setup, Ahrefs import steps with the
  Web Analytics export, screenshots list); backend README: new endpoints.
- [ ] **Step 2:** Restart backend and frontend; with a dashboard login, check every section on
  dcemergencylockanddoor.com at desktop and phone width, import the example export, test the property
  picker and connection test; save screenshots to `frontend/screenshots/redesign/`.
- [ ] **Step 3:** Full suites: backend `.seops-local/pytest.sh -q`, frontend `npm test && npm run
  typecheck && npm run lint && npm run build`.
- [ ] **Step 4: Commit** `docs: redesign screenshots and README updates`; `graphify update .`.
