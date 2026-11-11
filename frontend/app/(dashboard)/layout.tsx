import { Suspense } from "react";
import { requireUser, result, serverApi } from "@/lib/server-api";
import { Sidebar } from "@/components/shell/sidebar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireUser();
  const sites = await result((await serverApi()).sites());
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
      <Suspense>
        <Sidebar sites={sites.data ?? []} user={user} />
      </Suspense>
      <main
        id="main"
        className="mx-auto w-full min-w-0 max-w-[1280px] px-4 py-6 sm:px-8 sm:py-9"
      >
        {children}
      </main>
    </div>
  );
}
