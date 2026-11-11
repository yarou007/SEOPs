import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Loader2,
  XCircle,
} from "lucide-react";

export type PillState = "connected" | "action" | "off" | "syncing" | "error";
const PILLS: Record<
  PillState,
  { text: string; className: string; Icon: typeof CheckCircle2 }
> = {
  connected: { text: "Connected", className: "badge-good", Icon: CheckCircle2 },
  action: {
    text: "Needs action",
    className: "badge-warning",
    Icon: AlertTriangle,
  },
  off: { text: "Not set up", className: "badge-muted", Icon: CircleDashed },
  syncing: { text: "Syncing", className: "badge-muted", Icon: Loader2 },
  error: { text: "Not working", className: "badge-bad", Icon: XCircle },
};

export function StatusPill({
  state,
  text,
}: {
  state: PillState;
  text?: string;
}) {
  const { className, Icon, text: fallback } = PILLS[state];
  return (
    <span className={`badge gap-1 ${className}`}>
      <Icon
        size={13}
        aria-hidden
        className={state === "syncing" ? "motion-safe:animate-spin" : ""}
      />
      {text ?? fallback}
    </span>
  );
}
