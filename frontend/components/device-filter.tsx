"use client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export function DeviceFilter() {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  return (
    <label className="flex items-center gap-3 text-sm">
      <span className="text-muted">Device</span>
      <select
        aria-label="Device"
        value={search.get("device") ?? ""}
        onChange={(event) => {
          const params = new URLSearchParams(search.toString());
          if (event.target.value) params.set("device", event.target.value);
          else params.delete("device");
          params.delete("pagesOffset");
          params.delete("queriesOffset");
          router.push(`${pathname}?${params}`, { scroll: false });
        }}
      >
        <option value="">All devices</option>
        <option value="MOBILE">Mobile</option>
        <option value="DESKTOP">Desktop</option>
        <option value="TABLET">Tablet</option>
      </select>
    </label>
  );
}
