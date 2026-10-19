import Link from "next/link";
import { requireUser } from "@/lib/server-api";
import { Logout } from "@/components/logout";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireUser();
  return (
    <>
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-3 px-4 py-4 sm:px-8">
          <Link className="text-xl font-bold tracking-tight" href="/sites">
            SEOPs
          </Link>
          <div className="flex min-w-0 items-center gap-4">
            <span className="hidden truncate text-xs text-muted sm:block">
              {user.email} · {user.role}
            </span>
            <Logout />
          </div>
        </div>
      </header>
      <main
        id="main"
        className="mx-auto max-w-[1440px] px-4 py-7 sm:px-8 sm:py-9"
      >
        {children}
      </main>
    </>
  );
}
