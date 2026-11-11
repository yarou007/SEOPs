import type { PillState } from "@/components/ui/status-pill";
import type { ConnectionTest, SiteConnection } from "./types";

type Source = "gsc" | "ga4";
const PROPERTY = { gsc: "gsc_property", ga4: "ga4_property_id" } as const;

/** One source's state for the setup steps, from saved settings, the last test and the sync. */
export function sourceState(
  connection: SiteConnection,
  source: Source,
  test?: ConnectionTest,
): PillState {
  if (!connection[PROPERTY[source]]) return "off";
  if (connection.sync.running) return "syncing";
  if (test && !test.ok) return "error";
  if (connection.sync.results[source]?.status === "error") return "error";
  if (!connection.credentials[source].configured) return "action";
  return "connected";
}

export function setupProgress(states: PillState[]): { done: number; total: 3 } {
  return {
    done: states.filter((state) => state === "connected").length,
    total: 3,
  };
}
