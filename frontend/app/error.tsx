"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main id="main" className="mx-auto max-w-xl px-4 py-24">
      <section className="panel p-6">
        <h1 className="text-xl font-semibold">Could not load this view</h1>
        <p className="mt-2 text-muted">
          The service may be unavailable. Please try again.
        </p>
        <button className="button mt-5" onClick={reset}>
          Try again
        </button>
      </section>
    </main>
  );
}
