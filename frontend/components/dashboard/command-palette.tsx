"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  IconArrowRight,
  IconGrid,
  IconKey,
  IconLayers,
  IconPulse,
  IconSearch,
  IconSettings,
  IconShield,
} from "@/components/icons";

interface Command {
  id: string;
  label: string;
  hint?: string;
  group: string;
  icon: typeof IconGrid;
  run: () => void;
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const [projects, setProjects] = useState<Project[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setCursor(0);
    inputRef.current?.focus();
    api
      .listProjects()
      .then((result) => setProjects(result.projects))
      .catch(() => setProjects([]));
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const navigate = (href: string) => () => {
      router.push(href);
      onClose();
    };
    return [
      { id: "projects", label: "Go to projects", group: "Navigate", icon: IconGrid, run: navigate("/dashboard") },
      { id: "registry", label: "Model registry", group: "Navigate", icon: IconLayers, run: navigate("/dashboard/registry") },
      { id: "monitoring", label: "Monitoring", group: "Navigate", icon: IconPulse, run: navigate("/dashboard/monitoring") },
      { id: "audit", label: "Audit log", group: "Navigate", icon: IconShield, run: navigate("/dashboard/audit") },
      { id: "keys", label: "API keys", group: "Navigate", icon: IconKey, run: navigate("/dashboard/keys") },
      { id: "settings", label: "Settings", group: "Navigate", icon: IconSettings, run: navigate("/dashboard/settings") },
      ...projects.map((project) => ({
        id: project.id,
        label: project.name,
        hint: project.dataset_name ?? "no dataset",
        group: "Projects",
        icon: IconArrowRight,
        run: navigate(`/dashboard/${project.id}`),
      })),
    ];
  }, [projects, router, onClose]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter(
      (command) =>
        command.label.toLowerCase().includes(needle) ||
        command.hint?.toLowerCase().includes(needle),
    );
  }, [commands, query]);

  useEffect(() => setCursor(0), [query]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setCursor((value) => Math.min(value + 1, filtered.length - 1));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setCursor((value) => Math.max(value - 1, 0));
      } else if (event.key === "Enter") {
        event.preventDefault();
        filtered[cursor]?.run();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, filtered, cursor]);

  if (!open) return null;

  let lastGroup = "";

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/45 p-4 pt-[12vh] backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-2xl border bg-raised shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
      >
        <div className="flex items-center gap-3 border-b px-4">
          <IconSearch className="h-4 w-4 shrink-0 text-muted" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search projects and commands…"
            className="flex-1 bg-transparent py-3.5 text-[14px] outline-none placeholder:text-[color:var(--ink-muted)]"
          />
          <span className="kbd">esc</span>
        </div>

        <div className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 && (
            <p className="px-3 py-8 text-center text-[13px] text-muted">No matches.</p>
          )}
          {filtered.map((command, index) => {
            const showGroup = command.group !== lastGroup;
            lastGroup = command.group;
            const Icon = command.icon;
            return (
              <div key={command.id}>
                {showGroup && (
                  <p className="px-3 pb-1 pt-3 text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
                    {command.group}
                  </p>
                )}
                <button
                  onMouseEnter={() => setCursor(index)}
                  onClick={command.run}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-[13.5px] transition-colors",
                    index === cursor
                      ? "bg-brand-500/[0.12] text-brand-600 dark:text-brand-300"
                      : "text-secondary",
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="flex-1 truncate">{command.label}</span>
                  {command.hint && (
                    <span className="shrink-0 truncate text-[11.5px] text-muted">{command.hint}</span>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
