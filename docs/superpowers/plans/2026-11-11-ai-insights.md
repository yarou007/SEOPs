# AI Insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the team chat with an LLM about each website's stored SEO data, get AI
analysis in the weekly report, and store every piece of advice as a structured insight.

**Architecture:** The backend builds a compact JSON data context from existing metrics
and sends it, with a fixed analyst prompt, to OpenRouter (an OpenAI-compatible API) over
`httpx`. It validates the JSON reply with Pydantic, then stores conversations, messages
and insights in PostgreSQL. A per-day request budget protects the free quota. The
frontend adds an **Insights** tab (chat plus insight list) and an AI section in the
weekly report.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, httpx, Pydantic 2;
Next.js App Router, TypeScript, Tailwind, Vitest, react-markdown.

**Spec:** `docs/superpowers/specs/2026-11-11-ai-insights-design.md`

## Global Constraints

- Output language: English. The audience is the internal team; clients get no AI output.
- Provider: OpenRouter, `LLM_BASE_URL=https://openrouter.ai/api/v1`, key in
  `OPENROUTER_API_KEY`. Default `LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free`,
  `LLM_FALLBACK_MODELS=google/gemma-4-31b-it:free`, `LLM_MAX_TOKENS=4000`,
  `LLM_TIMEOUT_SECONDS=120`, `LLM_DAILY_REQUEST_BUDGET=45`.
- The key never appears in responses, logs, the database or git. Users see only generic
  error text.
- The test suite never calls the network. Use a fake `ChatClient`.
- Every new `site` column is a foreign key to `sites.domain`
  (`onupdate=CASCADE, ondelete=RESTRICT`), using `site_fk()` from `app/models.py`.
- Users who can ask or generate: `require_manager` (site creator or admin). Every linked
  user can read.
- POST and PATCH routes use `Depends(check_auth_origin)`. All routes set
  `Cache-Control: no-store`, as in `app/routers/analytics.py`.
- Limits: question ≤ 2,000 characters, context ≤ 30,000 characters, last 6 messages sent
  as memory, chat output has 2–3 suggested questions and 0–5 insights, weekly output has
  1–8 insights and 3 suggested questions.
- Markdown from the model renders with HTML disabled.
- Run backend tests with
  `TEST_DATABASE_URL=$(grep ^DATABASE_URL .env | cut -d= -f2- | sed 's#/seops$#/seops_test#') .venv/bin/python -m pytest -q`
  from `backend/`.
- After code changes, run `graphify update .` from `/home/amirben/Documents/hammi`.

## Review Focus

1. **Numbers the model invented**: evidence values that don't appear in the context.
   Expect them stored with `grounded: false` and shown as "unverified" (Task 4 test
   `test_ungrounded_evidence_is_flagged`).
2. **Reasoning model returns `content: null` or truncated JSON**: expect a retry, then the
   fallback model, then a clean `unavailable` error, with no partial rows saved (Task 2
   `test_null_content_falls_back`, Task 4 `test_failed_ask_stores_nothing`).
3. **Two asks at once at 44/45 used**: only one may run. The budget is reserved atomically
   before the HTTP call (Task 2 `test_budget_reserved_atomically`).
4. **Site with no data yet** (new site, no sync): the context says so and the model is
   still called, or the API returns a clear 409 "No data stored for this website yet"
   without spending quota (Task 3 `test_context_empty_site`, Task 5
   `test_ask_without_data_returns_409`).
5. **Long answers past proxy timeouts**: Next.js rewrites time out after 30 s by default.
   Expect `experimental.proxyTimeout = 180_000` and a client timeout of 180 s for ask and
   weekly (Task 7).

---

### Task 1: Storage: migration 0006, models, site views

**Files:**
- Modify: `backend/alembic/versions/0005_unified_site_database.py` (add an optional
  `extra_views` parameter; default output must stay byte-identical)
- Create: `backend/alembic/versions/0006_ai_insights.py`
- Modify: `backend/app/models.py`, `backend/tests/conftest.py` (TRUNCATE list),
  `backend/tests/test_foundation.py` (expected tables), `backend/tests/test_unified_database.py`
  (expected views)

**Interfaces:**
- Produces these models in `app/models.py`:
  - `AiConversation(id: UUID, site: str, created_by_user_id: UUID | None, title: str, created_at)`
  - `AiMessage(id: UUID, conversation_id: UUID, role: str, content: str, suggested_questions: list, context_summary: dict, model: str | None, created_at)`
  - `AiInsight(id: UUID, site: str, source: str, report_date: date | None, message_id: UUID | None, title: str, problem: str, evidence: list, advice: str, target_url: str | None, target_kpi: str, priority: str, status: str, model: str, created_at, updated_at)`
  - `LlmUsage(day: date PK, requests: int, failures: int, quota_exhausted: bool)`. The
    budget is per account, so the key is the day only. This deliberately departs from
    the spec's "(day, model)".
  - `WeeklyReport.ai_summary: str | None`
- Checks: `role IN ('user','assistant')`, `source IN ('weekly','chat')`,
  `priority IN ('high','medium','low')`, `status IN ('new','accepted','dismissed','done')`
  (default `'new'`).
- FKs: `ai_messages.conversation_id → ai_conversations.id ON DELETE CASCADE`;
  `ai_insights.message_id → ai_messages.id ON DELETE SET NULL`;
  `ai_conversations.created_by_user_id → users.id ON DELETE SET NULL`.
- Index `ix_ai_insights_site_status` on `(site, status)`.
- Site views added: `ai_insights` (all columns except `site`) and `ai_conversations`
  (conversation title, message role, content, suggested_questions, model, created_at,
  joined and ordered by conversation and time).

- [ ] **Step 1: Write failing tests.** In `test_unified_database.py`, extend the expected
  view set with `"ai_insights", "ai_conversations"`. Add
  `test_ai_insight_requires_known_site` (an insert with `site="nope.example"` raises
  `IntegrityError` matching `fk_ai_insights_site_sites`). Add
  `test_ai_insights_view_shows_site_rows` (insert one insight per site for two sites;
  the arlington view returns exactly 1 row). In `test_foundation.py`, add
  `ai_conversations, ai_messages, ai_insights, llm_usage` to `expected`.
- [ ] **Step 2: Run them.** Expect failures because the tables and views are missing.
- [ ] **Step 3: Implement.** In 0005, give `_site_views(base, extra_views=None)` and
  `_refresh_function(base, extra_views=None)` an optional `dict[str, str]` of extra
  view SQL (same `%2$L` domain placeholder). 0006 loads 0005 with
  `importlib.util.spec_from_file_location` (same directory), creates the tables and the
  `weekly_reports.ai_summary` column, then runs `_refresh_function(base, AI_VIEWS)` and
  `SELECT refresh_site_schemas()`. The downgrade restores `_refresh_function(base)`,
  refreshes, then drops the column and tables.
- [ ] **Step 4: Run the full suite.** Expect everything to pass, including
  `test_migration_round_trip_on_empty_schema` (which runs `alembic check`).
- [ ] **Step 5: Commit** with `feat(db): store AI conversations, insights and LLM usage`.

### Task 2: LLM client, settings and daily budget

**Files:**
- Modify: `backend/app/config/__init__.py`, `backend/pyproject.toml` (move
  `httpx>=0.28,<1` into main dependencies, then `uv lock`), `backend/.env.example`
- Create: `backend/app/insights/__init__.py`, `backend/app/insights/llm.py`
- Test: `backend/tests/insights/test_llm.py` (plus `tests/insights/__init__.py` if the
  existing test packages use one)

**Interfaces:**
- Settings: `openrouter_api_key: SecretStr | None = None`,
  `llm_base_url: str = "https://openrouter.ai/api/v1"`, `llm_model: str`,
  `llm_fallback_models: list[str]` (comma-separated in env, like
  `portfolio_site_slugs`), `llm_max_tokens: int = 4000`,
  `llm_timeout_seconds: float = 120`, `llm_daily_request_budget: int = 45`.
- `class LlmError(Exception)` with `code: Literal["not_configured", "quota_exhausted", "unavailable", "invalid_output"]`
  and a generic, user-safe `message`.
- `class TransportError(Exception)` with `status: int | None`.
- `class ChatClient(Protocol): def complete(self, model: str, messages: list[dict], max_tokens: int) -> str | None`.
  It returns `choices[0].message.content` and raises `TransportError` on HTTP errors or
  timeouts.
- `class OpenRouterClient(ChatClient)`: `__init__(self, settings: Settings)`, using
  `httpx.Client(base_url, timeout)` and the headers `Authorization: Bearer <key>`,
  `X-Title: SEOPs`. It sends `response_format={"type": "json_object"}`.
- `def usage_today(db: Session, settings: Settings) -> UsageInfo` (Pydantic:
  `configured: bool, model: str, used: int, budget: int, remaining: int, exhausted: bool`).
  Days are UTC.
- `def generate_json[T: BaseModel](db: Session, client: ChatClient, settings: Settings, messages: list[dict], schema: type[T]) -> tuple[T, str]`.
  It returns the parsed object and the model that answered.

Algorithm for `generate_json`. The budget and transport rules need it, and they can't
be read from a signature alone:

```
if no api key: raise LlmError("not_configured")
for model in [llm_model, *llm_fallback_models][:2]:
    reserve(): in its own committed transaction, upsert llm_usage(day) with
        requests = requests + 1 RETURNING requests, quota_exhausted;
        if quota_exhausted or requests > budget: roll back the increment, raise quota_exhausted
    try content = client.complete(model, msgs, max_tokens)
    except TransportError(429): mark quota_exhausted=true, failures+1; raise quota_exhausted
    except TransportError: failures+1; continue
    for attempt in (1, 2):   # the second attempt counts against the budget too
        parse JSON (strip ``` fences) and schema.model_validate
        ok → return (obj, model)
        invalid and attempt 1 → reserve(); append the assistant text plus a user message
            "Your reply was not valid JSON for the schema: <error, 500 chars>. Reply with JSON only.";
            content = client.complete(...)
    failures+1   # null content counts as invalid
raise LlmError("unavailable" if the last failure was transport, else "invalid_output")
```

- [ ] **Step 1: Write failing tests** using a `FakeChatClient(replies: list[str | None | TransportError])`
  that records the `(model, messages)` calls:
  - `test_not_configured_raises_without_key`: no request is recorded.
  - `test_valid_json_returns_model_and_counts_one_request`: `usage_today(...).used == 1`.
  - `test_invalid_json_retries_once_with_error_message`: the second call's last user
    message contains `"not valid JSON"`.
  - `test_null_content_falls_back`: replies `[None, None, valid]` → the result model is
    the fallback model.
  - `test_429_marks_quota_exhausted`: after it, `usage_today(...).exhausted is True` and
    the next call raises `quota_exhausted` without calling the client.
  - `test_budget_reserved_atomically`: with the budget at 1, two threads that each have
    their own `SessionLocal()` → exactly one succeeds and one raises `quota_exhausted`.
  - `test_openrouter_client_sends_key_and_reads_content`: uses `httpx.MockTransport`.
    Assert the bearer header and `response_format`, and that a 500 raises
    `TransportError(status=500)`.
- [ ] **Step 2: Run them.** Expect `ModuleNotFoundError: app.insights`.
- [ ] **Step 3: Implement** `llm.py` and the settings. Add the commented LLM variables to
  `.env.example`, with no real key.
- [ ] **Step 4: Run** `tests/insights/test_llm.py`, then the full suite. Expect all to pass.
- [ ] **Step 5: Commit** with `feat(insights): OpenRouter client with fallback and daily budget`.

### Task 3: Data context builder

**Files:**
- Create: `backend/app/insights/context.py`
- Test: `backend/tests/insights/test_context.py`

**Interfaces:**
- Consumes these functions from `app.metrics`: `period_totals`, `timeseries`, `gsc_pages`,
  `gsc_queries`, `gsc_totals(device=...)`, `sync_status`, `Window`, `resolve_window`, and
  `public`. Also the latest `WeeklyReport.report` for the site.
- Produces:
  - `def build_context(db: Session, site: Site, window: metrics.Window) -> dict`, with
    these keys: `site`, `window`, `previous_window`, `totals` (`current`/`previous`),
    `daily`, `top_pages`, `top_queries`, `devices`, `countries`, `weekly_flags`,
    `sync_status`, `data_notes`, `has_data: bool`.
  - `def render_context(context: dict, limit: int = 30_000) -> str`: compact JSON. When
    it's over the limit, drop rows from the end of `top_queries`, then `top_pages`, then
    `daily`, until it fits.
  - `def context_numbers(context: dict) -> set[str]`: every numeric value, normalized to
    strings with up to 4 decimals and no trailing zeros. Used for grounding (Task 4).
- Top lists: 25 rows ordered by impressions. Countries: top 10 rows of
  `page='' AND query='' AND device='' AND country<>'all'` summed over the window. Add a
  `gsc_countries` helper in `context.py` if `metrics` has none.

- [ ] **Step 1: Write failing tests.**
  - `test_context_has_totals_and_top_lists`: uses the `add_test_gsc_totals` fixture
    pattern from `tests/analysis/test_weekly.py`. Assert that `totals.current.gsc.clicks`
    equals the stored sum and that `len(top_pages) <= 25`.
  - `test_render_context_respects_limit`: 300 queries with limit 5,000 →
    `len(output) <= 5000` and `json.loads` works.
  - `test_context_empty_site`: `has_data is False` and the top lists are empty.
  - `test_context_numbers_normalizes`: `Decimal("0.1600")` and `12` become `{"0.16", "12"}`.
- [ ] **Step 2: Run them.** Expect failures.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expect them to pass.
- [ ] **Step 5: Commit** with `feat(insights): compact per-site data context`.

### Task 4: Prompts, schemas and insight service

**Files:**
- Create: `backend/app/insights/prompts.py`, `backend/app/insights/service.py`
- Test: `backend/tests/insights/test_service.py`

**Interfaces:**
- `prompts.py`:
  - `SYSTEM_PROMPT: str`, an English analyst prompt that encodes the spec §4 rules.
  - `class Evidence(BaseModel): metric: str; value: str | float; period: str`
  - `class InsightDraft(BaseModel)`: `title` (max 200), `problem`, `evidence` (at least
    1), `advice`, `target_url: str | None`, `target_kpi`, and
    `priority: Literal["high", "medium", "low"]`.
  - `class ChatReply(BaseModel)`: `answer_markdown`, `suggested_questions` (2–3),
    `insights` (0–5).
  - `class WeeklyReply(BaseModel)`: `summary_markdown`, `insights` (1–8),
    `suggested_questions` (exactly 3).
  - `def chat_messages(context_json: str, history: list[AiMessage], question: str) -> list[dict]`
  - `def weekly_messages(context_json: str, report: dict) -> list[dict]`. Each embeds the
    JSON schema from `model_json_schema()`.
- `service.py`:
  - `def clean_question(text: str) -> str`: strips control characters other than
    newlines and tabs, and trims. Raises `ValueError` if the result is empty or longer
    than 2,000 characters.
  - `def ask(db, site, user, question, conversation_id: UUID | None, window, client, settings) -> AiMessage`.
    It creates the conversation if needed (title = first 80 characters of the
    question), sends the last 6 messages as history, and calls `generate_json(...,
    ChatReply)`. Then it stores the user message and the assistant message
    (`content=answer_markdown`, `suggested_questions`,
    `context_summary={"window": ..., "has_data": ...}`, `model`), plus insights with
    `source="chat"` and `message_id`, all in one commit **after** the LLM succeeds.
    Raises `LookupError` for a conversation ID that belongs to another site.
  - `def generate_weekly(db, site, client, settings) -> WeeklyReport`. It uses the
    latest `WeeklyReport` (raising `LookupError` if there is none), builds the context
    for that report's `windows.current`, and calls `generate_json(..., WeeklyReply)`.
    It sets `ai_summary` and replaces any `source="weekly"` insights with the same
    `report_date`. One commit.
  - `def ground(evidence: list[Evidence], numbers: set[str]) -> list[dict]`: adds
    `grounded: bool` to each item. A numeric value is grounded when its normalized form,
    or the value rounded to 2 or 0 decimals, is in `numbers`. Non-numeric values are
    grounded.

- [ ] **Step 1: Write failing tests** using a fake client that returns fixed JSON:
  - `test_ask_stores_conversation_messages_and_insights`: 1 conversation, 2 messages,
    1 insight with `source == "chat"` and `status == "new"`.
  - `test_ask_sends_last_six_messages`: after 4 earlier exchanges, the call has system +
    6 history messages + 1 user message.
  - `test_failed_ask_stores_nothing`: a client that always returns invalid JSON →
    `LlmError`, and every AI table is empty.
  - `test_ungrounded_evidence_is_flagged`: evidence value `999999` (not in the context)
    → stored with `grounded is False`; a value equal to the stored clicks → `True`.
  - `test_clean_question_rejects_empty_and_long`: `"\x00 "` → `ValueError`; 2,001
    characters → `ValueError`.
  - `test_generate_weekly_sets_summary_and_replaces_insights`: run twice → the same
    number of weekly insights, not double, and `ai_summary` is set.
  - `test_generate_weekly_without_report_raises`.
- [ ] **Step 2: Run them.** Expect failures.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expect them to pass.
- [ ] **Step 5: Commit** with `feat(insights): chat and weekly analysis service with grounded evidence`.

### Task 5: Insights API

**Files:**
- Create: `backend/app/routers/insights.py`
- Modify: `backend/app/main.py` (include the router), `backend/app/routers/sites.py` and
  any shared module (import `require_manager`; move it to `app/access.py` if that avoids
  a circular import)
- Test: `backend/tests/test_insights_api.py`

**Interfaces:**
- The prefix is `/api/sites/{slug}/insights`. Routes follow spec §5. Responses:
  - `GET /status` → `UsageInfo`.
  - `POST /ask` body `{question: str, conversation_id?: UUID, start?: date, end?: date}`
    → `{conversation_id, message: {id, role, content, suggested_questions, model, created_at}, insights: [...]}`.
  - `GET /conversations` → `[{id, title, created_at, last_message_at}]` newest first;
    `GET /conversations/{id}` → `{id, title, messages: [...]}` (404 if it belongs to another site).
  - `GET /` takes the query parameters `status?`, `source?`, `limit=50` (≤ 200) and
    `offset`, and returns insights newest first.
  - `PATCH /{insight_id}` body `{status}`.
  - `POST /weekly` → `{report_date, ai_summary, insights}`.
- Inject the client with `def get_chat_client() -> ChatClient` (returning
  `OpenRouterClient(get_settings())`) so tests can override it with
  `app.dependency_overrides`.
- Errors map as follows. `LlmError.not_configured` → 503 "AI is not configured on the
  server." `quota_exhausted` → 429 "Today's AI request limit is used up. It resets at
  midnight UTC." `unavailable` and `invalid_output` → 502 "The AI could not answer
  right now. Try again later." `LookupError` → 404. `ValueError` from
  `clean_question` → 422. Ask with `has_data False` → 409 "No data stored for this
  website yet. Run an import first." This check happens before reserving the budget.

- [ ] **Step 1: Write failing tests**, using the `client` and `login_as` fixtures and a
  fake client override:
  - `test_viewer_can_read_but_not_ask` (GET 200, POST ask 403)
  - `test_ask_requires_origin`
  - `test_ask_returns_message_and_suggestions`
  - `test_ask_without_data_returns_409` (the fake client is never called)
  - `test_quota_exhausted_returns_429`
  - `test_not_configured_returns_503`
  - `test_patch_status_validates_value` (`"bogus"` → 422)
  - `test_insights_hidden_for_unlinked_site` (404 "Site not found")
  - `test_error_never_contains_key` (the response text has no `sk-or`)
- [ ] **Step 2: Run them.** Expect them to fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite.** Expect everything to pass.
- [ ] **Step 5: Commit** with `feat(api): insights chat, list, status and weekly endpoints`.

### Task 6: CLI opt-in for the weekly AI analysis

**Files:**
- Modify: `backend/app/analysis/main.py`
- Test: `backend/tests/analysis/test_weekly.py`

**Interfaces:**
- Add a `--with-ai` flag to `weekly`. After `save_report`, if it's set, call
  `generate_weekly(db, site, OpenRouterClient(settings), settings)`. An `LlmError` logs
  `"%s: AI analysis skipped: %s"` with the safe message, sets the exit status to 1, and
  the report stays saved.
- Without `--with-ai`, nothing changes.

- [ ] **Step 1: Write a failing test**, `test_cli_with_ai_without_key_keeps_report`: run
  the CLI with `--with-ai` and `OPENROUTER_API_KEY` set to empty → exit code 1, the
  stderr contains `"AI analysis skipped"`, and the `weekly_reports` row exists.
- [ ] **Step 2: Run it.** Expect it to fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run it.** Expect it to pass.
- [ ] **Step 5: Commit** with `feat(cli): optional --with-ai weekly analysis`.

### Task 7: Frontend API, types, helpers and proxy timeout

**Files:**
- Modify: `frontend/lib/api.ts`, `frontend/lib/types.ts`, `frontend/next.config.ts`
  (`experimental: { proxyTimeout: 180_000 }`)
- Create: `frontend/lib/insights.ts`
- Test: `frontend/tests/insights.test.ts`

**Interfaces:**
- `request()` gets an optional `timeoutMs = 20_000` used in `AbortSignal.timeout`.
- The API adds `insightsStatus`, `conversations`, `conversation`, `ask` (180,000 ms),
  `insights`, `updateInsight`, and `generateWeekly` (180,000 ms).
- The types are `UsageInfo`, `AiMessage`, `AiInsight` (with `evidence: {metric, value, period, grounded}[]`),
  `Conversation`, and `AskResponse`. `WeeklyReport` gains `ai_summary?: string | null`.
  This means `/report/latest` must include `ai_summary`: add it in
  `routers/analytics.py` by merging the column into the returned dict, and add a
  backend test.
- `lib/insights.ts`:
  - `quotaLabel(u: UsageInfo): string` returns `"AI not configured"`,
    `"Daily AI limit reached"`, or `"N AI requests left today"`.
  - `sortInsights(list)` orders by priority (high > medium > low), then newest first.
  - `STARTER_QUESTIONS: string[]` holds the three questions from spec §7.

- [ ] **Step 1: Write failing tests** for `quotaLabel` (three cases), `sortInsights`
  ordering, the starter questions being exactly the 3 spec strings, and `createApi`
  with a fake transport: `ask` posts JSON to `/api/sites/s/insights/ask`. Add the
  backend test `test_latest_report_includes_ai_summary`.
- [ ] **Step 2: Run** `npx vitest run tests/insights.test.ts`. Expect it to fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npx vitest run && npm run -s typecheck`. Expect it to pass.
  Afterwards, run `git checkout frontend/next-env.d.ts` if the typecheck changed it.
- [ ] **Step 5: Commit** with `feat(frontend): insights API client and helpers`.

### Task 8: Insights tab and AI section in the weekly report

**Files:**
- Modify: `frontend/app/(dashboard)/sites/[slug]/page.tsx` (add the tab
  `["insights", "Insights"]` and render `<InsightsPanel slug canManage />`),
  `frontend/components/weekly-report.tsx`, and `frontend/package.json` (add
  `react-markdown`, pinned to an exact version that's at least two weeks old)
- Create: `frontend/components/insights-panel.tsx`, `frontend/components/insight-card.tsx`,
  `frontend/components/markdown.tsx` (wraps `react-markdown` with `skipHtml`)

**Interfaces:**
- `InsightsPanel({ slug, canManage }: { slug: string; canManage: boolean })` is a
  `"use client"` component. It shows the quota label, conversation history, a question
  form (`maxLength={2000}`, disabled while busy or when `!canManage` or quota is out),
  the answer rendered with `<Markdown>`, suggested questions as buttons that submit
  them, starter questions on an empty chat, and the insight list via `<InsightCard>`.
  The list uses status buttons (Accept, Dismiss, Done) when `canManage`, and marks
  ungrounded evidence "unverified".
- `WeeklyReport` gets an "AI analysis" section. It shows `ai_summary` with `<Markdown>`
  and links to the Insights tab, or offers a "Generate AI analysis" button for managers
  when it's missing.
- Get `canManage` from the existing site connection data (`SiteConnection.can_manage`).
- Follow the existing tokens and classes (`badge-*`, `border-accent`) and the existing
  empty and error states from `components/states.tsx`.

- [ ] **Step 1: Implement the components.**
- [ ] **Step 2: Run** `npx vitest run && npm run -s typecheck && npm run -s lint`.
  Expect it to pass.
- [ ] **Step 3: Check in the browser.** Start the backend and `npm run dev`, then open
  `/sites/dcemergencylockanddoor-com?tab=insights`. Check that the starter question
  returns an answer with chips, that an insight appears and its status button works, and
  that the layout fits at 390 px width and in dark mode. Take one screenshot for the PR.
- [ ] **Step 4: Commit** with `feat(frontend): insights tab and AI section in weekly report`.

### Task 9: Docs and live check

**Files:**
- Modify: `README.md` (an "AI insights" section covering what it does, the settings and
  the quota; update the Database view list and the branch table), `backend/README.md`
  (endpoints, CLI `--with-ai`, new tables)

- [ ] **Step 1: Update the docs.**
- [ ] **Step 2: Run** `alembic upgrade head` on the real `seops` database (back it up
  first with `pg_dump -Fc` into `.seops-local/backups/`). Make one live ask through the
  API and one `--with-ai` weekly run for `dcemergencylockanddoor-com`. Record the
  results and the remaining quota in the PR description.
- [ ] **Step 3: Run** the full backend and frontend suites, then `graphify update .` from
  the hammi root.
- [ ] **Step 4: Commit** with `docs: AI insights usage and configuration`, then push
  `feat/ai-insights`.
