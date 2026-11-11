# SEOPs UI/UX redesign — design

Date: 2026-11-11 · Branch: `feat/ui-redesign` (built on `feat/ai-insights`) · Status: approved in chat

## Why

The owner's words: the dashboard is "just not that good", connecting GA4, GSC and Ahrefs is "a little bit
complicated", and the results are "a little bit hard to understand and analyse". Asked to "just make it a
professional website with good UI/UX", including the LLM (AI insights) pages, the website configuration
page and importing Ahrefs data.

The dashboard serves **both** the internal team (knows SEO) and clients (may not know what CTR or position
means). Every screen must read in plain language first and keep the technical detail one step away.

## Goals

1. A professional, consistent look: app shell with a left sidebar, site switcher, consistent cards,
   spacing, typography and icons, good empty/loading/error states, works at phone width (no horizontal
   page scroll, 16px gutter).
2. An Overview that explains itself: plain-language headline, four main numbers with plain names,
   explanations and good/bad colouring, a "What to do next" list, the top AI insights.
3. A guided setup page for connecting Search Console, GA4 and Ahrefs, with property pickers, a test button
   and clear sync progress.
4. A real Ahrefs page with an import that accepts the Ahrefs **Web Analytics "all stats" export** (the
   example folder `dcemergencylockanddoor_all-stats_ahrefs_2026-11-11_21-23-17/`) plus the existing
   Backlinks and Site Audit (internal links) CSV uploads, and a view of the imported data.
5. A cleaner AI Insights page (chat bubbles, suggestion chips, quota bar, insight filters).
6. An Analysis page that is easier to scan (sticky contents, one-line takeaway per section).

## Non-goals

- No change to how data is synced from Google, to the AI pipeline, or to the database design beyond what
  the Ahrefs Web Analytics import needs.
- No Ahrefs API integration (the account's key returns 401: the plan has no API access).
- No new auth, user management, theming system or i18n. English only.
- No zip upload (the user unzips; the page accepts several files or a whole folder).

## Anti-goals (a failure even if it works)

- Hiding numbers clients or the team rely on. Everything visible today stays reachable.
- Jargon-first screens: a client must be able to read the Overview without knowing "CTR".
- Breaking the existing tests' guarantees (access control, manager-only actions, 2 MB CSV cap, grounding
  labels on AI figures).
- Inventing numbers: headlines and "what to do next" items are computed only from stored data.

## Current state (from recon)

- Top bar only ("SEOPs", user, Log out); site page tabs: Overview, Search, Traffic, Analysis, Insights,
  Ahrefs (placeholder text), Data status. "Data connections" is a button to `/sites/[slug]/settings`.
- Settings page: three separate panels (type GSC property string, type GA4 numeric ID; "Give SEOPs access"
  instructions with the service-account email; "Import real data" with Sync). No test, no pickers, no
  Ahrefs.
- Ahrefs CSV upload exists only inside Analysis (internal-links, backlinks) via `POST
  /api/sites/{slug}/axes/upload` → `import_csv` → `AxisSnapshot` + raw `AhrefsCsvRow` rows.
- Overview: 7 KPI boxes with technical names, chart, a long weekly report (flagged pages, device split,
  query candidates), AI summary block.

## The Ahrefs Web Analytics export (input format)

A folder of up to 21 files, each **UTF-16 LE with BOM, tab-separated, every cell quoted**, header row
first. Empty reports are a 2-byte file (BOM only). Numbers are strings; rates are fractions ("0.5625",
"1.", "0."); durations are seconds. The files carry **no dates**; the folder name carries the export
timestamp. Files and their header (first column identifies the report):

| File | Columns |
|---|---|
| TopPages | Page, Visitors, Views, Bounce rate, Time on page |
| EntryPages | Entry page, Visitors, Entrances, Visit duration |
| ExitPages | Page, Visitors, Exits, Exit rate |
| Channel | Channel, Visitors, Bounce rate, Visit duration |
| Source | Source, Visitors, Bounce rate, Visit duration |
| Device / Browser / OS | Device·Browser·OS, Visitors, Bounce rate, Visit duration |
| Countries / Cities / Continents / Languages | name, Visitors |
| UtmCampaign/Content/Medium/Source/Term | UTM x, Visitors, Bounce rate, Visit duration |
| TrackedEvents | Event, Visitors, Count, Conversion Rate |
| OutboundLinkClicks | Event property: href, Count, Visitors (e.g. `tel:+1703…` = phone clicks) |
| ClonedPages, Possible404 | (empty in the example) |

## Design

### 1. App shell and visual language
- Left sidebar (collapsible to a top menu on phones): SEOPs mark, **site switcher** (dropdown of
  accessible sites), sections **Overview, Search, Traffic, Analysis, AI Insights, Ahrefs, Setup**, plus
  "Data status" as a small link; user email/role and Log out at the bottom. All sites list stays at
  `/sites`.
- Section navigation keeps the existing URL scheme (`/sites/[slug]?tab=...`, settings at
  `/sites/[slug]/settings`) so links and tests keep working; the date control stays on data tabs only.
- Visual language: refined neutral palette with one accent, light and dark via existing CSS tokens,
  Inter-style system font, 8px spacing scale, cards with subtle borders, icon per section
  (`lucide-react`). Page headers: title, one-line plain description, primary action on the right.
- Shared components: `PageHeader`, `Card`, `StatCard`, `InfoTip` (ⓘ with plain explanation),
  `StatusPill` (Connected / Needs action / Not set up / Syncing / Error), `EmptyState` with a next action,
  `Steps` (numbered setup steps), `Collapsible`.

### 2. Overview
- **Headline card** (plain language, computed client-side from the summary and stored weekly report):
  e.g. "Clicks from Google fell 11% compared with the previous 28 days." plus, when the weekly report
  flags pages, "The biggest drop is on /lock-repair/." With no prior baseline it says so. Never invents
  a cause.
- **Four main numbers** with plain labels and the technical name underneath:
  Clicks from Google (GSC clicks), Times shown on Google (impressions), Click rate (CTR), Average Google
  position (lower is better). Each has an InfoTip and a green/red change badge with "vs previous N days".
  The three GA4 numbers (Visits, Visitors, Conversions) sit in a secondary row with the same treatment.
- Chart as today, in a card.
- **What to do next**: up to 5 action items derived from the weekly report flags with a fixed
  plain-language template per flag reason (e.g. "Shown 21,160 times but no clicks → rewrite the title and
  description of /contact/"; "Ranks 8–20, close to page 1 → strengthen /rekeying/ content and internal
  links"). Each links to the page row / Search tab.
- **AI**: the stored weekly AI summary (or the Generate button for managers) and the top 3 open insights
  by priority, linking to AI Insights.
- The full weekly report (flagged pages, device split, query candidates, data notes) moves into
  Collapsible sections below, unchanged in content.

### 3. Setup (was "Data connections")
- Page header "Connect your data" with an overall progress line ("2 of 3 sources connected").
- Three step cards: **① Google Search Console ② Google Analytics 4 ③ Ahrefs**, each with a StatusPill,
  a short plain explanation of what it brings, and its controls:
  - GSC/GA4: "Give SEOPs access" instructions with the service-account email and a copy button;
    **property picker** — a dropdown filled from a new endpoint listing properties the service account
    can see, with "Enter manually" fallback (existing validation kept); **Test connection** button; save.
  - Ahrefs: links to the Ahrefs import (section 4) and shows the last import date per kind.
- **Sync** card: one primary "Sync now" button, progress per source (existing polling), last sync time
  per source, clear errors.
- Viewers (non-managers) see read-only status with the existing explanation.

New backend endpoints (manager-only, same access rules as the connection endpoints):
- `GET /api/sites/{slug}/connection/options` → `{gsc: {properties: [string], error: string|null},
  ga4: {properties: [{id, name, account}], error: string|null}}`. GSC from the Search Console
  `sites.list` API; GA4 from the Analytics Admin API `accountSummaries.list` (via
  google-api-python-client discovery). If an API is disabled or credentials are missing, that source
  returns an empty list and a safe error message and the UI falls back to manual entry.
- `POST /api/sites/{slug}/connection/test` → `{gsc: {ok, message}, ga4: {ok, message}}` using the saved
  properties: one tiny query each (GSC: 1 row over the last few days; GA4: 1-row report). Sources without
  a saved property return `ok: false, message: "Not set up"`.
- **Owner's decision:** the options endpoint returns the **full, unfiltered** list of properties the
  service account can see, to every manager of the site (admin or site creator). SEOPs is used only by
  the owner's team for now. Revisit if outside clients get accounts that can create websites.

### 4. Ahrefs page and import
- Ahrefs section (replacing the placeholder) with two parts:
  - **Import** card with tabs per export type: **Web Analytics (all stats)**, **Backlinks**, **Site Audit
    — internal links**. Each tab says exactly where to click in Ahrefs to export it. Web Analytics accepts
    several files or a whole folder (`multiple` + folder picker), shows the recognised reports before
    upload (e.g. "18 reports recognised, 3 empty, 0 unknown"), and asks for the **period** the export covers
    (default: the 30 days ending on the date in the folder name if present, else today). Backlinks and
    Site Audit reuse the existing upload endpoint (moved here; Analysis links to this page instead).
  - **Imported data** view of the latest Web Analytics import: period and import date; cards for
    Visitors (sum of channel visitors), phone clicks (outbound `tel:` link clicks), top channels,
    top sources, top pages (visitors, views, bounce rate, time on page), entry and exit pages, devices,
    countries, tracked events. Plain labels and InfoTips (bounce rate, entrances, exit rate).
  - Shows last import date and row counts for Backlinks and Site Audit with a link to their Analysis
    sections.
- Backend: `POST /api/sites/{slug}/ahrefs/web-analytics` (manager-only, origin check like other writes)
  with `{period_start, period_end, files: [{name, content}]}`; the browser decodes UTF-16 to text. The
  server recognises each file by its header row (not by file name), parses numbers strictly (fractions,
  "1." and "0." accepted), skips empty files, reports unknown files, and rejects: no recognised report,
  a page URL outside the site's domain, more than 20,000 rows in a file, or more than 2 MB in total. It
  stores one `AxisSnapshot(kind="web-analytics", data={period, reports:{...}})` and every raw row in
  `ahrefs_csv_rows` with `kind="web-analytics:<report>"` (no migration needed: `kind` is free text).
  `GET /api/sites/{slug}/ahrefs` returns the latest web-analytics snapshot plus the latest backlinks and
  internal-links snapshot metadata (collected_at, row counts).
- The AI context (`build_context`) gains an `ahrefs_web_analytics` block (period, totals, top 10 pages,
  channels, phone clicks) when an import exists, so AI answers can use it and its figures count as
  grounded.

### 5. AI Insights
- Two columns on desktop (chat left, insights right), stacked on phones.
- Chat: message bubbles (user right, AI left with Markdown), the existing "unverified" marking, suggested
  questions as chips, conversation list as a dropdown with "New conversation", disabled while an answer
  is loading, a quota bar ("12 of 45 AI requests left today").
- Insights: filter by status (Open / Done / Dismissed) and priority; cards with a coloured priority
  stripe, problem, evidence chips, advice, target page and KPI, status buttons for managers.
- Clear errors and empty states ("No insights yet — ask a question or generate the weekly analysis").

### 6. Analysis
- Sticky contents list (desktop) of the 8 sections; each section opens with its question and a one-line
  takeaway (existing `axisFinding`), the charts and tables inside a Collapsible that is open by default
  for the first section only. Ahrefs uploads replaced by a link to the Ahrefs page.

### 7. Search, Traffic, Data status, Sites list, Login
- Same data, restyled with the new components; plain column labels with InfoTips (CTR → "Click rate").
- Sites list: cards with a status pill per source and the clicks trend; "Add website" primary.
- Login: centred card with the product name.

## Constraints

- Stack stays: Next.js 16 App Router, React 19, Tailwind 4, Recharts, Vitest, FastAPI, SQLAlchemy.
  One new frontend dependency allowed: `lucide-react` (pinned exact version).
- Existing API contracts stay; new endpoints only add. Existing backend and frontend tests stay green.
- Accessibility: labelled controls, keyboard reachable, visible focus, colour never the only signal.
- Secrets never reach the browser (service-account file paths stay server-side; the email is already
  shown today).

## Calls made by the designer (not asked of the owner)

- Sidebar navigation with the existing URL scheme kept.
- Four main GSC numbers plus a secondary GA4 row (instead of seven equal boxes).
- "What to do next" is rule-based templates on the weekly flags, not AI, so it is always available and
  never invents numbers.
- The Web Analytics period is entered by the user (the export has no dates), defaulted from the folder
  name.
- GA4 property listing uses the Analytics Admin API, which may need enabling in Google Cloud; manual
  entry remains.
- Re-importing Web Analytics for the same period (same start and end) replaces the earlier snapshot and
  its raw rows; a different period is kept alongside. "Latest" means the most recently imported.
- Recognition is by header row; the domain check applies to page URLs only (TopPages, EntryPages,
  ExitPages), not outbound `tel:`/external links. The 2 MB cap counts the decoded UTF-8 text.
  The period is stored in `AxisSnapshot.start_date`/`end_date`.
- The Overview headline uses the selected date range; weekly-report facts are labelled with the
  report's own dates so the two periods are never mixed.
- The example export folder is ignored by git (`*_ahrefs_*/` in `.gitignore`) so real visitor data is
  never committed.

## Left to the builder

Exact colours, icon choices, spacing values, component file layout, chart styling details, and the exact
wording of help texts (plain English, short).
