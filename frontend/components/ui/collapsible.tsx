import { ChevronRight } from "lucide-react";

export function Collapsible({
  title,
  summary,
  open = false,
  children,
}: {
  title: React.ReactNode;
  summary?: React.ReactNode;
  open?: boolean;
  children: React.ReactNode;
}) {
  return (
    <details className="group panel min-w-0" open={open}>
      <summary className="flex cursor-pointer list-none items-center gap-3 p-4 sm:px-6 [&::-webkit-details-marker]:hidden">
        <ChevronRight
          size={16}
          aria-hidden
          className="shrink-0 text-muted transition-transform group-open:rotate-90"
        />
        <span className="min-w-0 flex-1">
          <span className="font-semibold">{title}</span>
          {summary && (
            <span className="mt-0.5 block text-sm text-muted">{summary}</span>
          )}
        </span>
      </summary>
      <div className="min-w-0 border-t border-border p-4 sm:p-6">
        {children}
      </div>
    </details>
  );
}
