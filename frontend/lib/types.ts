export interface User {
  id: string;
  email: string;
  role: "admin" | "viewer";
}
export interface Site {
  slug: string;
  domain: string;
  display_name: string;
}
export interface ConnectionInput {
  gsc_property: string | null;
  ga4_property_id: string | null;
}
export interface CreateSiteInput extends ConnectionInput {
  display_name: string;
  domain: string;
}
export interface CredentialInfo {
  configured: boolean;
  service_account_email: string | null;
  message: string;
}
export type SetupInfo = Record<"gsc" | "ga4", CredentialInfo>;
export interface SyncJob {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  results: Record<
    string,
    { status: string; rows_loaded: number | null; message: string }
  >;
}
export interface SiteConnection extends Site, ConnectionInput {
  can_manage: boolean;
  credentials: SetupInfo;
  sync: SyncJob;
}
export interface DateRange {
  start: string;
  end: string;
}
export type Device = "MOBILE" | "DESKTOP" | "TABLET";
export interface GscMetrics {
  clicks: number;
  impressions: number;
  ctr: number | null;
  avg_position: number | null;
}
export interface Ga4Metrics {
  sessions: number;
  total_users: number;
  conversions: number;
}
export interface PeriodTotals {
  gsc: GscMetrics | null;
  ga4: Ga4Metrics | null;
}
export interface Summary {
  current_window: DateRange;
  previous_window: DateRange;
  current: PeriodTotals;
  previous: PeriodTotals;
}
export interface DayMetrics {
  data_date: string;
  gsc_clicks: number | null;
  gsc_impressions: number | null;
  ga4_sessions: number | null;
  ga4_users: number | null;
}
export interface GscPage extends GscMetrics {
  page: string;
}
export interface GscQuery extends GscMetrics {
  query: string;
  top_page: string;
}
export interface Ga4Page extends Ga4Metrics {
  page_path: string;
  engagement_rate: number | null;
}
export interface SyncLog {
  site: string;
  last_loaded_date: string | null;
  last_run_at: string | null;
  status: string | null;
  rows_loaded: number | null;
  error: string | null;
}
export interface SourceStatus {
  gsc: SyncLog | null;
  ga4: SyncLog | null;
}
export interface PageFlag extends GscPage {
  check: string;
  reason: string;
  position_band: string | null;
  median_ctr_for_band: number | null;
  impressions_lost: number;
  drop_percent?: number;
  previous_clicks?: number;
  last7_clicks?: number;
  prev7_clicks?: number;
  mobile_ctr?: number;
  desktop_ctr?: number;
  mobile_impressions?: number;
  desktop_impressions?: number;
}
export interface QueryCandidate extends GscQuery {
  reason: string;
}
export interface WeeklyReport {
  site: Site;
  report_date: string;
  generated_at: string;
  windows: Record<"current" | "previous" | "last7" | "prev7", DateRange>;
  sync_status: Record<"gsc" | "ga4", { log: SyncLog | null; stale: boolean }>;
  warnings: string[];
  totals: { current: PeriodTotals; previous: PeriodTotals };
  flagged_pages_count: number;
  top_pages: PageFlag[];
  device_split: Record<"MOBILE" | "DESKTOP", GscMetrics | null>;
  query_candidates: QueryCandidate[];
  data_notes: string[];
  ai_summary?: string | null;
}
export interface Result<T> {
  data: T | null;
  error: string | null;
  status?: number;
}

export interface UsageInfo {
  configured: boolean;
  model: string;
  used: number;
  budget: number;
  remaining: number;
  exhausted: boolean;
}
export interface AiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  suggested_questions: string[];
  model: string | null;
  created_at: string;
}
export type InsightStatus = "new" | "accepted" | "dismissed" | "done";
export interface AiEvidence {
  metric: string;
  value: string | number;
  period: string;
  grounded: boolean;
}
export interface AiInsight {
  id: string;
  source: "weekly" | "chat";
  report_date: string | null;
  message_id: string | null;
  title: string;
  problem: string;
  evidence: AiEvidence[];
  advice: string;
  target_url: string | null;
  target_kpi: string;
  priority: "high" | "medium" | "low";
  status: InsightStatus;
  model: string;
  created_at: string;
  updated_at: string;
}
export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  last_message_at: string | null;
}
export interface Conversation {
  id: string;
  title: string;
  messages: AiMessage[];
}
export interface AskInput {
  question: string;
  conversation_id?: string;
  start?: string;
  end?: string;
}
export interface AskResponse {
  conversation_id: string;
  message: AiMessage;
  insights: AiInsight[];
}
export interface WeeklyAiResponse {
  report_date: string;
  ai_summary: string | null;
  insights: AiInsight[];
}

export interface ConnectionTest {
  ok: boolean;
  message: string;
}
export type ConnectionTestResult = Record<"gsc" | "ga4", ConnectionTest>;
export interface Ga4PropertyOption {
  id: string;
  name: string;
  account: string;
}
export interface ConnectionOptions {
  gsc: { properties: string[]; error: string | null };
  ga4: { properties: Ga4PropertyOption[]; error: string | null };
}
export type WebAnalyticsReport =
  | "top_pages"
  | "entry_pages"
  | "exit_pages"
  | "channels"
  | "sources"
  | "devices"
  | "browsers"
  | "os"
  | "countries"
  | "cities"
  | "continents"
  | "languages"
  | "utm_campaign"
  | "utm_content"
  | "utm_medium"
  | "utm_source"
  | "utm_term"
  | "events"
  | "outbound_links";
export interface WebAnalyticsRow {
  page?: string;
  href?: string;
  name?: string;
  visitors?: number;
  views?: number;
  entrances?: number;
  exits?: number;
  count?: number;
  exit_rate?: number;
  bounce_rate?: number;
  visit_duration?: number;
  time_on_page?: number;
  conversion_rate?: number;
}
export interface WebAnalyticsTotals {
  visitors: number;
  phone_clicks: number;
  pages: number;
}
export interface WebAnalyticsImport {
  id: string;
  period_start: string;
  period_end: string;
  imported_at: string;
  totals: WebAnalyticsTotals;
  reports: Partial<Record<WebAnalyticsReport, WebAnalyticsRow[]>>;
  files: { recognised: number; empty: string[]; unknown: string[] };
}
export interface Change {
  now: number | null;
  before: number | null;
  change_percent: number | null;
}
export interface AhrefsData {
  web_analytics: WebAnalyticsImport | null;
  previous: {
    period_start: string;
    period_end: string;
    totals: WebAnalyticsTotals;
  } | null;
  changes: {
    visitors?: Change;
    phone_clicks?: Change;
    bounce_rate?: Change;
    pages?: { page: string; visitors_now: number; visitors_before: number }[];
  };
  history: {
    period_start: string;
    period_end: string;
    visitors: number;
    phone_clicks: number;
  }[];
  backlinks: { imported_at: string; rows: number } | null;
  internal_links: { imported_at: string; rows: number } | null;
}
export interface WebAnalyticsFile {
  name: string;
  content: string;
}
