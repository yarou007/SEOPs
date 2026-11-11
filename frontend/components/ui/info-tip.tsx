"use client";

import { useId, useState } from "react";
import { Info } from "lucide-react";

/** A small ⓘ button that explains a term in plain words. Works with keyboard and touch. */
export function InfoTip({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        className="inline-flex size-5 items-center justify-center rounded-full text-muted hover:text-foreground"
        aria-label={`What is ${label}?`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((value) => !value)}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
      >
        <Info size={14} aria-hidden />
      </button>
      <span
        id={id}
        role="tooltip"
        hidden={!open}
        className="absolute left-1/2 top-6 z-30 w-64 -translate-x-1/2 rounded-md border border-border bg-surface p-3 text-left text-xs font-normal leading-relaxed text-foreground shadow-lg"
      >
        {children}
      </span>
    </span>
  );
}
