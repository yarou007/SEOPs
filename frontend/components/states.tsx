import Link from "next/link";

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="panel px-5 py-9 text-center text-muted">{children}</div>
  );
}
export function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-md border border-bad/30 bg-bad-soft px-4 py-4 text-bad"
    >
      {message} <span>Use the browser reload button to try again.</span>
    </div>
  );
}
export function SiteNotFound() {
  return (
    <section className="panel mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-semibold">Site not found</h1>
      <p className="mt-2 text-muted">This site could not be found.</p>
      <Link className="button mt-5" href="/sites">
        Back to sites
      </Link>
    </section>
  );
}
