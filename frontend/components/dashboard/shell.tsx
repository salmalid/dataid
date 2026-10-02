"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Logo } from "@/components/landing/nav";
import { ThemeToggle } from "@/components/theme-provider";
import { Badge } from "@/components/ui/primitives";
import { CommandPalette } from "./command-palette";
import {
  IconBook,
  IconGrid,
  IconKey,
  IconLayers,
  IconPulse,
  IconSearch,
  IconSettings,
  IconShield,
} from "@/components/icons";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Projects", icon: IconGrid, exact: true },
  { href: "/dashboard/registry", label: "Model registry", icon: IconLayers },
  { href: "/dashboard/monitoring", label: "Monitoring", icon: IconPulse },
  { href: "/dashboard/audit", label: "Audit log", icon: IconShield },
  { href: "/dashboard/keys", label: "API keys", icon: IconKey },
  { href: "/dashboard/settings", label: "Settings", icon: IconSettings },
];

export function DashboardShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [health, setHealth] = useState<{ llm_provider: string; active_runs: number } | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const poll = () =>
      api
        .health()
        .then((result) => {
          if (cancelled) return;
          setHealth(result);
          setOffline(false);
        })
        .catch(() => !cancelled && setOffline(true));
    poll();
    const timer = window.setInterval(poll, 12_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((value) => !value);
      }
      if (event.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r px-3 py-4 lg:flex">
        <div className="px-2">
          <Logo />
        </div>

        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          className="mt-6 flex items-center gap-2.5 rounded-xl border px-3 py-2 text-[13px] text-muted transition-colors hover:bg-black/[0.03] focus-ring dark:hover:bg-white/[0.05]"
        >
          <IconSearch className="h-4 w-4" />
          <span className="flex-1 text-left">Search…</span>
          <span className="kbd">⌘K</span>
        </button>

        <nav className="mt-4 flex-1 space-y-0.5">
          {NAV.map((item) => {
            const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] transition-colors",
                  active
                    ? "bg-brand-500/[0.10] font-medium text-brand-600 dark:text-brand-300"
                    : "text-secondary hover:bg-black/[0.03] dark:hover:bg-white/[0.05]",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="space-y-2 border-t pt-3">
          <Link
            href="/#docs"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13.5px] text-secondary transition-colors hover:bg-black/[0.03] dark:hover:bg-white/[0.05]"
          >
            <IconBook className="h-4 w-4" />
            Documentation
          </Link>
          <div className="flex items-center justify-between px-3 py-1">
            <span className="flex items-center gap-2 text-[11.5px] text-muted">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{
                  background: offline ? "var(--status-critical)" : "var(--status-good)",
                }}
              />
              {offline ? "API offline" : `LLM: ${health?.llm_provider ?? "…"}`}
            </span>
            <ThemeToggle className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted transition-colors hover:bg-black/[0.04] dark:hover:bg-white/[0.06]" />
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass sticky top-0 z-30 flex h-14 items-center gap-3 border-b px-4 lg:hidden">
          <Logo />
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="ml-auto flex h-9 w-9 items-center justify-center rounded-lg border"
            aria-label="Search"
          >
            <IconSearch className="h-4 w-4" />
          </button>
          <ThemeToggle />
        </header>

        {offline && (
          <div
            className="flex items-center gap-2 border-b px-5 py-2.5 text-[12.5px]"
            style={{ background: "color-mix(in srgb, var(--status-critical) 10%, transparent)" }}
          >
            <Badge tone="critical">API offline</Badge>
            <span className="text-secondary">
              Start the backend with{" "}
              <code className="rounded bg-black/[0.06] px-1.5 py-0.5 font-mono text-[11.5px] dark:bg-white/[0.08]">
                uvicorn backend.api.main:app --port 8000
              </code>
            </span>
          </div>
        )}

        <main className="min-w-0 flex-1">{children}</main>
      </div>

      <nav className="glass fixed inset-x-0 bottom-0 z-30 flex border-t lg:hidden">
        {NAV.slice(0, 5).map((item) => {
          const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-1 flex-col items-center gap-1 py-2.5 text-[10.5px]",
                active ? "text-brand-500 dark:text-brand-400" : "text-muted",
              )}
            >
              <Icon className="h-4.5 w-4.5" style={{ width: 18, height: 18 }} />
              {item.label.split(" ")[0]}
            </Link>
          );
        })}
      </nav>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}

export function PageHeader({
  title,
  description,
  action,
  breadcrumb,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  breadcrumb?: { label: string; href: string }[];
}) {
  return (
    <div className="border-b px-5 py-6 lg:px-8">
      {breadcrumb && (
        <nav className="mb-2 flex items-center gap-1.5 text-[12.5px] text-muted">
          {breadcrumb.map((crumb, index) => (
            <span key={crumb.href} className="flex items-center gap-1.5">
              {index > 0 && <span aria-hidden>/</span>}
              <Link href={crumb.href} className="transition-colors hover:text-[color:var(--ink)]">
                {crumb.label}
              </Link>
            </span>
          ))}
        </nav>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[24px] font-semibold tracking-[-0.01em]">{title}</h1>
          {description && <p className="mt-1.5 text-[13.5px] text-secondary">{description}</p>}
        </div>
        {action}
      </div>
    </div>
  );
}
