import { StatusPill, type PillState } from "./status-pill";

/** One numbered setup step: the order matters, so the number is real information. */
export function Step({
  number,
  title,
  description,
  state,
  children,
}: {
  number: number;
  title: string;
  description: React.ReactNode;
  state: PillState;
  children: React.ReactNode;
}) {
  return (
    <section
      className="panel min-w-0 p-5 sm:p-6"
      aria-labelledby={`step-${number}`}
    >
      <div className="flex flex-wrap items-start gap-4">
        <span
          aria-hidden
          className={`flex size-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${state === "connected" ? "bg-good-soft text-good" : "bg-brass-soft text-brass"}`}
        >
          {number}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id={`step-${number}`} className="text-lg font-semibold">
              <span className="sr-only">Step {number}: </span>
              {title}
            </h2>
            <StatusPill state={state} />
          </div>
          <p className="mt-1 text-sm text-muted">{description}</p>
          <div className="mt-5 space-y-4">{children}</div>
        </div>
      </div>
    </section>
  );
}
