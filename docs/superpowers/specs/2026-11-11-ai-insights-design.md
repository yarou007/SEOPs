# AI insights: design

Date: 2026-11-11 · Branch: `feat/ai-insights` (based on `feat/unified-database`)

## Intent

Connect each website's stored SEO data to an LLM so the team can:

1. **Ask questions** about one website in plain English and get answers grounded in
   the real numbers.
2. **Get better questions**: every answer suggests 2–3 sharper follow-up questions the
   team should be asking.
3. **Get analysis and advice** automatically for each weekly report.

**Why now:** the data is unified in one database (`feat/unified-database`). The study
plan (`plan-etude-seo-agent.md`) describes the next system: an agent that reads advice
and opens pull requests that change the website files. This feature produces that advice
in a structured, stored form, so the agent can consume it later without rework.

**Audience for now:** the internal team (admins and site managers). Clients do not see
AI output yet. Output language: **English**.

## Goals

- A chat panel per website (new **Insights** tab in the site page). You ask a question,
  get an answer that cites figures from the data, and see suggested follow-up questions.
- AI analysis inside the weekly report: a summary plus a list of structured insights.
- Every insight is stored in the database with these fields: **problem, evidence
  (numbers), advice, target page/URL, target KPI, priority, status**. It is visible in
  each site's schema as a view `<site_schema>.ai_insights`.
- The provider and model are configuration. The default is OpenRouter with a free
  model, and switching to another OpenRouter model or another OpenAI-compatible
  provider needs no code change.

## Non-goals

- No automatic changes to website files or repositories. That is the future PR agent.
- No client-facing AI output.
- The AI does not run SQL or browse the database directly.
- No keyword-volume provider and no new data sources.

## Anti-goals (failure even if it "works")

- **Invented numbers.** Any figure in an answer or insight must come from the data
  context we sent. Advice that cites figures not in the context is a failure.
- **Silent quota burn.** The free key allows about 50 requests/day. Background jobs must
  not exhaust it unnoticed, and the UI must say clearly when the quota is used up.
- **Leaking secrets.** The API key never reaches the browser, logs, the database or git.
- **Breaking existing flows.** If the LLM is down or out of quota, sync, weekly reports
  and the dashboard keep working, and the AI parts show a clear "unavailable" state.

## Constraints

- Backend: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16. Frontend: Next.js App Router,
  TypeScript, Tailwind. Follow existing patterns: `AccessibleSite` access checks, origin
  checks on POST, `no-store` caching, migrations only through Alembic, tests against a
  real Postgres test schema.
- Provider: **OpenRouter** (`https://openrouter.ai/api/v1/chat/completions`,
  OpenAI-compatible). Key in `OPENROUTER_API_KEY` (already in `backend/.env`).
- Free tier: 50 free-model requests/day per account, 20 requests/minute. Free models
  can be reasoning models: they spend tokens before answering and may return
  `content: null` if `max_tokens` is too low (observed with 300; fine with 2000).
- The privacy trade-off is accepted by the user: summarized client SEO data is sent to
  OpenRouter free models.

## Decided by the user

- Both surfaces: chat page **and** AI analysis in the weekly report.
- English output.
- OpenRouter with the provided key, on free models.
- Insights are stored for a future system that turns them into website changes.

## Design (builder's calls are marked *(call)*)

### 1. Data context (backend, no LLM)

`app/insights/context.py` builds a compact JSON context for one site and window from
the existing functions in `app/metrics.py` and `app/analysis`:

- Site info (domain, connected sources, last sync dates, data gaps).
- Period totals for the current 28 days vs the previous 28 days: GSC clicks,
  impressions, CTR, position; GA4 sessions, users, conversions.
- Daily totals series for the window (short form).
- Top N pages and queries by impressions *(call: N = 25)*, with CTR and position.
- Device split and top countries.
- The latest weekly report's flags (`top_pages`, `query_candidates`, warnings).
- Data notes (hidden queries, lag days), so the model knows the limits.

The context gets a hard size cap *(call: ~30k characters, trimming tables first)*. Each
number carries a stable key, so answers can reference it.

### 2. LLM client

`app/insights/llm.py` makes one function call over OpenAI-compatible chat completions
using `httpx` (move `httpx` from dev to main dependencies). Settings:

| Setting | Default |
|---|---|
| `OPENROUTER_API_KEY` | required to enable AI; absent → AI shows "not configured" |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b:free` *(call; verified working 2026-11-11)* |
| `LLM_FALLBACK_MODELS` | comma list, e.g. `google/gemma-4-31b-it:free` *(call)* |
| `LLM_MAX_TOKENS` | 4000 |
| `LLM_TIMEOUT_SECONDS` | 120 |
| `LLM_DAILY_REQUEST_BUDGET` | 45 (leave headroom under 50) |

- Ask for **JSON output** (schema in the prompt plus `response_format` when supported),
  validate it with Pydantic, and retry once with the validation error if it is invalid.
- Treat `content: null`, HTTP 429 and 5xx as failures. Try the fallback models in
  order. On 429, record that the quota is exhausted until the next UTC midnight.
- Count every request (including failures) in a `llm_usage` table per UTC day. Refuse
  new requests once the budget is reached.
- Tests use a fake client. The suite never calls the network.

### 3. Storage (Alembic migration `0006`)

- `ai_conversations`: id, site (FK `sites.domain`, as in 0005), created_by (FK users),
  title, created_at.
- `ai_messages`: id, conversation_id (FK, cascade), role (`user`/`assistant`),
  content (text), suggested_questions (jsonb), context_summary (jsonb: window and
  sources used), model, created_at.
- `ai_insights`: id, site (FK), source (`weekly`/`chat`), report_date (nullable),
  message_id (nullable FK), title, problem, evidence (jsonb list of
  `{metric, value, period}`), advice, target_url (nullable), target_kpi, priority
  (`high`/`medium`/`low`), status (`new`/`accepted`/`dismissed`/`done`), model,
  created_at, updated_at.
- `llm_usage`: day (date, PK with model), requests, failures.
- Extend `refresh_site_schemas()` with the views `ai_insights` and `ai_conversations`
  (messages joined). Bump the view list in README and tests.

### 4. Prompts

`app/insights/prompts.py` has a fixed system prompt. The analyst rules:
- Use only figures from the provided context, and cite them.
- Say "the data does not show this" when the data can't answer.
- Explain likely causes as hypotheses.
- Give concrete, page-level advice.
- Always return 2–3 better follow-up questions.
- Respect the data notes.

Output schemas:
- **Chat:** `{answer_markdown, suggested_questions[2-3], insights[0-5]}`.
- **Weekly:** `{summary_markdown, insights[3-8], suggested_questions[3]}`.

### 5. API (new router `app/routers/insights.py`, under `/api/sites/{slug}/insights`)

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/status` | any linked user | configured?, model, requests left today |
| GET | `/conversations` | linked | list |
| GET | `/conversations/{id}` | linked | messages |
| POST | `/ask` | site managers/admins | `{question, conversation_id?, start?, end?}` → assistant message (synchronous; respond within the timeout) |
| GET | `/` | linked | insights list, filter by status/source |
| PATCH | `/{insight_id}` | site managers/admins | change status |
| POST | `/weekly` | site managers/admins | generate AI analysis for the latest weekly report |

The "site managers" rule is the same one used for imports: `require_manager` in
`app/routers/sites.py` (the site creator or an admin). Move it to a shared module if needed. Read-only
linked users can read but not spend quota.

### 6. Weekly integration

After `save_report` in the CLI (`app.analysis weekly`) and the dashboard import, the
weekly AI analysis does **not** run automatically by default *(call: opt-in with
`--with-ai` on the CLI and a button in the UI, to protect the daily quota)*. Its result
is stored as `ai_insights` (source `weekly`, `report_date`) plus a summary. Store the
summary in the report row: add a nullable `ai_summary` column to `weekly_reports`.

### 7. Frontend

- New site tab **Insights** with three parts:
  - **Chat:** a question box, conversation history, the answer rendered as Markdown,
    and the suggested questions as clickable chips.
  - **Insights:** a list or cards with priority, KPI, target page and evidence, plus
    status buttons (accept, dismiss, done).
  - **Quota:** "AI requests left today: N", and states for not configured and quota
    exhausted.
- In the weekly report: an "AI analysis" section with the summary and the top insights,
  plus a "Generate AI analysis" button when there is none.
- Starter question chips on an empty chat *(call)*, for example "Why did clicks change
  vs last period?", "Which pages have the best quick-win potential?", and "What should
  we fix first this week?".

### 8. Security

- The key exists only on the server. Responses and logs never include it. Error
  messages shown to users are generic.
- Strip control characters from user questions and cap their length *(call: 2,000
  characters)*. The model output is rendered as Markdown with HTML disabled.
- POST endpoints require the same origin check and session as the other mutations.

## Testing

- Unit: context building and its size cap, JSON validation and retry, fallback order,
  budget refusal, 429 handling (fake transport).
- API: access rules (viewer can read but not ask), the ask flow stores messages and
  insights, insight status changes, the not-configured and quota-exhausted states.
- Migration round trip and `alembic check`. The site-schema views include
  `ai_insights`.
- Frontend unit tests for the Insights tab states. One manual live test against
  OpenRouter, recorded in the PR.

## Builder review (self-review; settled calls)

- Concurrent asks against the same budget: increment `llm_usage` with a row lock or
  upsert before each request, so two requests can't both slip past the limit.
- The chat uses the latest stored data only. It never triggers a Google sync.
- Conversation memory: send the last 6 messages of the conversation together with a
  fresh data context *(call)*, to keep requests small.
- Free models can be removed by OpenRouter at any time. Fallback models plus a clear
  "model unavailable" error cover this, and changing `LLM_MODEL` fixes it.

## Left to the builder

The exact prompt wording, the context field names, component layout and styling within
the existing design, the pagination of insights, and the polling vs. waiting choice for
long answers (keep it synchronous unless timeouts force otherwise).
