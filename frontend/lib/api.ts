import type { AxisKey, AxisResponse } from "./analysis";
import type {
  DateRange,
  DayMetrics,
  Device,
  Ga4Page,
  GscPage,
  GscQuery,
  Site,
  SourceStatus,
  Summary,
  User,
  WeeklyReport,
  ConnectionInput,
  CreateSiteInput,
  SetupInfo,
  SiteConnection,
  SyncJob,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export type Transport = (path: string, init: RequestInit) => Promise<Response>;
type Params = Record<string, string | number | undefined>;

function errorDetail(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object" || !("detail" in body)) return fallback;
  const detail = body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((issue: unknown) => {
        if (
          issue &&
          typeof issue === "object" &&
          "msg" in issue &&
          typeof issue.msg === "string"
        )
          return issue.msg;
        return "Invalid request";
      })
      .join(". ");
  }
  return fallback;
}

export function createApi(transport: Transport = fetch) {
  async function request<T>(
    path: string,
    init: RequestInit = {},
    params: Params = {},
  ): Promise<T> {
    if (!path.startsWith("/api/"))
      throw new Error("API paths must be relative /api/ URLs");
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params))
      if (value !== undefined && value !== "") query.set(key, String(value));
    let response: Response;
    try {
      response = await transport(path + (query.size ? `?${query}` : ""), {
        ...init,
        cache: "no-store",
        credentials: "include",
        signal: AbortSignal.timeout(20_000),
      });
    } catch {
      throw new ApiError(503, "Could not reach the API. Please try again.");
    }
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      throw new ApiError(
        response.status,
        errorDetail(
          body,
          `Request failed (${response.status}). Please try again.`,
        ),
      );
    }
    if (response.status === 204) return undefined as T;
    try {
      return (await response.json()) as T;
    } catch {
      throw new ApiError(502, "The API returned an invalid response.");
    }
  }
  const sitePath = (slug: string) => `/api/sites/${encodeURIComponent(slug)}`;
  return {
    me: () => request<User>("/api/auth/me"),
    login: (email: string, password: string) =>
      request<User>("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      }),
    logout: () => request<void>("/api/auth/logout", { method: "POST" }),
    sites: () => request<Site[]>("/api/sites"),
    setup: () => request<SetupInfo>("/api/sites/setup"),
    createSite: (payload: CreateSiteInput) =>
      request<Site>("/api/sites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    connection: (slug: string) =>
      request<SiteConnection>(`${sitePath(slug)}/connection`),
    saveConnection: (slug: string, payload: ConnectionInput) =>
      request<SiteConnection>(`${sitePath(slug)}/connection`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    syncSite: (slug: string) =>
      request<SyncJob>(`${sitePath(slug)}/sync`, { method: "POST" }),
    status: (slug: string) => request<SourceStatus>(`${sitePath(slug)}/status`),
    summary: (slug: string, range: Partial<DateRange> = {}) =>
      request<Summary>(`${sitePath(slug)}/summary`, {}, { ...range }),
    timeseries: (slug: string, range: Partial<DateRange>) =>
      request<DayMetrics[]>(`${sitePath(slug)}/timeseries`, {}, { ...range }),
    gscPages: (
      slug: string,
      range: Partial<DateRange>,
      device: Device | undefined,
      limit: number,
      offset: number,
    ) =>
      request<GscPage[]>(
        `${sitePath(slug)}/gsc/pages`,
        {},
        { ...range, device, limit, offset },
      ),
    gscQueries: (
      slug: string,
      range: Partial<DateRange>,
      device: Device | undefined,
      limit: number,
      offset: number,
    ) =>
      request<GscQuery[]>(
        `${sitePath(slug)}/gsc/queries`,
        {},
        { ...range, device, limit, offset },
      ),
    ga4Pages: (
      slug: string,
      range: Partial<DateRange>,
      limit: number,
      offset: number,
    ) =>
      request<Ga4Page[]>(
        `${sitePath(slug)}/ga4/pages`,
        {},
        { ...range, limit, offset },
      ),
    axis: (slug: string, axis: AxisKey, range: Partial<DateRange>) =>
      request<AxisResponse>(`${sitePath(slug)}/axes/${axis}`, {}, { ...range }),
    uploadAxisCsv: (
      slug: string,
      kind: "internal-links" | "backlinks",
      csv: string,
    ) =>
      request<{ id: string }>(`${sitePath(slug)}/axes/imports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, csv }),
      }),
    report: (slug: string) =>
      request<WeeklyReport>(`${sitePath(slug)}/report/latest`),
  };
}
export const api = createApi();
