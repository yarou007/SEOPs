// Site sections shown in the sidebar. URLs keep the existing scheme (?tab=...).
export const SECTIONS = [
  { key: "overview", label: "Overview", hint: "The big picture" },
  { key: "search", label: "Search", hint: "Pages and searches on Google" },
  { key: "traffic", label: "Traffic", hint: "Visits from Google Analytics" },
  { key: "analysis", label: "Analysis", hint: "Deeper checks" },
  { key: "insights", label: "AI Insights", hint: "Ask questions, get advice" },
  { key: "ahrefs", label: "Ahrefs", hint: "Import and view Ahrefs data" },
  { key: "setup", label: "Setup", hint: "Connect your data" },
  { key: "status", label: "Data status", hint: "Last imports" },
] as const;
export type SectionKey = (typeof SECTIONS)[number]["key"];

const OFFSETS = ["pagesOffset", "queriesOffset", "trafficOffset"];
const isSection = (key: string | null): key is SectionKey =>
  SECTIONS.some((section) => section.key === key);

export function sectionHref(
  slug: string,
  key: string,
  query: URLSearchParams = new URLSearchParams(),
): string {
  const base = `/sites/${encodeURIComponent(slug)}`;
  if (key === "setup") return `${base}/settings`;
  const params = new URLSearchParams();
  for (const [name, value] of query)
    if (value && name !== "tab" && !OFFSETS.includes(name))
      params.set(name, value);
  if (key !== "overview") params.set("tab", key);
  return params.size ? `${base}?${params}` : base;
}

export function activeSection(
  pathname: string,
  tab: string | null,
): SectionKey {
  if (/^\/sites\/[^/]+\/settings\/?$/.test(pathname)) return "setup";
  return isSection(tab) && tab !== "setup" ? tab : "overview";
}

export function slugFromPath(pathname: string): string | null {
  const match = /^\/sites\/([^/]+)/.exec(pathname);
  if (!match || match[1] === "new") return null;
  return decodeURIComponent(match[1]);
}
