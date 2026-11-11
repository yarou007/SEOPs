"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Activity,
  BarChart3,
  Database,
  KeyRound,
  LayoutDashboard,
  Link2,
  Menu,
  MousePointerClick,
  PlugZap,
  Sparkles,
  X,
} from "lucide-react";
import { Logout } from "@/components/logout";
import { SECTIONS, activeSection, sectionHref, slugFromPath } from "@/lib/nav";
import type { Site, User } from "@/lib/types";

const ICONS = {
  overview: LayoutDashboard,
  search: MousePointerClick,
  traffic: Activity,
  analysis: BarChart3,
  insights: Sparkles,
  ahrefs: Link2,
  setup: PlugZap,
  status: Database,
} as const;

function Brand() {
  return (
    <Link href="/sites" className="flex items-center gap-2.5 px-2">
      <span className="flex size-8 items-center justify-center rounded-md bg-brass text-ink">
        <KeyRound size={17} aria-hidden />
      </span>
      <span className="text-lg font-semibold tracking-tight text-ink-foreground">
        SEOPs
      </span>
    </Link>
  );
}

function Navigation({ sites, user }: { sites: Site[]; user: User }) {
  const pathname = usePathname();
  const query = useSearchParams();
  const router = useRouter();
  const slug = slugFromPath(pathname);
  const site = sites.find((item) => item.slug === slug);
  const current = activeSection(pathname, query.get("tab"));
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <Brand />
      {sites.length > 0 && (
        <div>
          <label
            htmlFor="site-switcher"
            className="mb-1.5 block px-2 text-xs text-ink-muted"
          >
            Website
          </label>
          <select
            id="site-switcher"
            className="w-full border-ink-raised bg-ink-raised text-ink-foreground"
            value={site?.slug ?? ""}
            onChange={(event) => {
              const next = event.target.value;
              router.push(
                next
                  ? sectionHref(next, slug ? current : "overview", query)
                  : "/sites",
              );
            }}
          >
            <option value="">All websites</option>
            {sites.map((item) => (
              <option key={item.slug} value={item.slug}>
                {item.display_name}
              </option>
            ))}
          </select>
        </div>
      )}
      {site ? (
        <nav aria-label="Website sections" className="-mx-1 flex-1">
          <ul className="space-y-0.5">
            {SECTIONS.map((section) => {
              const Icon = ICONS[section.key];
              const active = section.key === current;
              return (
                <li key={section.key}>
                  <Link
                    href={sectionHref(site.slug, section.key, query)}
                    aria-current={active ? "page" : undefined}
                    className={`flex items-center gap-3 rounded-md border-l-2 px-3 py-2 text-sm ${active ? "border-brass bg-ink-raised font-semibold text-ink-foreground" : "border-transparent text-ink-muted hover:bg-ink-raised hover:text-ink-foreground"}`}
                  >
                    <Icon size={17} aria-hidden />
                    {section.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      ) : (
        <nav aria-label="Main" className="-mx-1 flex-1">
          <Link
            href="/sites"
            aria-current={pathname === "/sites" ? "page" : undefined}
            className="flex items-center gap-3 rounded-md border-l-2 border-brass bg-ink-raised px-3 py-2 text-sm font-semibold text-ink-foreground"
          >
            <LayoutDashboard size={17} aria-hidden />
            All websites
          </Link>
        </nav>
      )}
      <div className="border-t border-ink-raised pt-4">
        <p className="truncate px-2 text-xs text-ink-foreground">
          {user.email}
        </p>
        <p className="mb-3 px-2 text-xs capitalize text-ink-muted">
          {user.role}
        </p>
        <Logout className="w-full border-ink-raised bg-ink-raised text-ink-foreground hover:bg-ink-raised hover:opacity-90" />
      </div>
    </div>
  );
}

export function Sidebar({ sites, user }: { sites: Site[]; user: User }) {
  const [open, setOpen] = useState(false);
  const drawer = useRef<HTMLElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  // Phone drawer: move focus in when it opens, close on Escape, give focus back on close.
  useEffect(() => {
    if (!open) return;
    drawer.current?.querySelector<HTMLElement>("a, select, button")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      toggle.current?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);
  return (
    <>
      <div className="sticky top-0 z-40 flex items-center justify-between bg-ink px-4 py-3 lg:hidden">
        <Brand />
        <button
          ref={toggle}
          type="button"
          className="rounded-md p-2 text-ink-foreground"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls="sidebar"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X size={22} aria-hidden /> : <Menu size={22} aria-hidden />}
        </button>
      </div>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          aria-hidden
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        ref={drawer}
        id="sidebar"
        // Close the phone drawer once a link or the website switcher is used.
        onClick={(event) =>
          (event.target as HTMLElement).closest("a") && setOpen(false)
        }
        onChange={() => setOpen(false)}
        className={`fixed inset-y-0 left-0 z-50 w-64 overflow-y-auto bg-ink transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${open ? "visible translate-x-0" : "invisible -translate-x-full lg:visible"}`}
      >
        <Navigation sites={sites} user={user} />
      </aside>
    </>
  );
}
