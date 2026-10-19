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
}
export interface Result<T> {
  data: T | null;
  error: string | null;
  status?: number;
}
