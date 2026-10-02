"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/dashboard/shell";
import { Badge, Button, Card, CardHeader, Input, Skeleton } from "@/components/ui/primitives";
import { useTheme } from "@/components/theme-provider";
import { Toggle } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { AgentInfo } from "@/lib/types";
import { titleCase } from "@/lib/utils";

const SHORTCUTS = [
  { keys: "⌘ K", action: "Open the command palette" },
  { keys: "↑ ↓", action: "Move through results" },
  { keys: "↵", action: "Open the highlighted result" },
  { keys: "Esc", action: "Close the palette" },
];

export default function SettingsPage() {
  const { theme, toggle } = useTheme();
  const [health, setHealth] = useState<Awaited<ReturnType<typeof api.health>> | null>(null);
  const [agents, setAgents] = useState<AgentInfo[] | null>(null);
  const [token, setToken] = useState("");
  const [connection, setConnection] = useState("");
  const [connecting, setConnecting] = useState(false);

  const connect = async (event: React.FormEvent) => {
    event.preventDefault();
    setConnecting(true);
    setConnection("");
    try {
      const response = await fetch("/api/session", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Connection failed");
      setToken("");
      window.location.reload();
    } catch (error) {
      setConnection(error instanceof Error ? error.message : "Connection failed");
    } finally {
      setConnecting(false);
    }
  };

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api
      .agents()
      .then((result) => setAgents(result.agents))
      .catch(() => setAgents([]));
  }, []);

  return (
    <>
      <PageHeader
        title="Settings"
        description="Workspace configuration and what the backend currently has available."
      />

      <div className="max-w-3xl space-y-6 px-5 py-6 lg:px-8">
        <Card>
          <CardHeader title="Workspace access" subtitle="Connect with an API key when this workspace requires authentication." />
          <form onSubmit={connect} className="space-y-3 p-5">
            <label htmlFor="workspace-token" className="text-sm">API key</label>
            <Input id="workspace-token" type="password" value={token} autoComplete="off"
              onChange={(event) => setToken(event.target.value)} required />
            <div className="flex gap-3">
              <Button type="submit" disabled={connecting || !token.trim()}>Connect</Button>
              <Button type="button" variant="secondary" onClick={async () => {
                try {
                  const response = await fetch("/api/session", { method: "DELETE" });
                  if (!response.ok) throw new Error("Disconnect failed");
                  window.location.reload();
                } catch { setConnection("Could not disconnect. Check the backend connection."); }
              }}>Disconnect</Button>
            </div>
            {connection && <p role="alert" className="text-sm">{connection}</p>}
          </form>
        </Card>
        <Card>
          <CardHeader title="Appearance" />
          <div className="p-5">
            <Toggle
              checked={theme === "dark"}
              onChange={toggle}
              label="Dark mode"
              description="Charts re-step their palette for the dark surface rather than inverting."
            />
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Backend"
            subtitle="Optional libraries degrade gracefully — nothing here is required."
          />
          <div className="p-5">
            {health === null ? (
              <Skeleton className="h-24" />
            ) : (
              <dl className="divide-y">
                <Row label="Status">
                  <Badge tone="good">{health.status}</Badge>
                </Row>
                <Row label="LLM provider">
                  <Badge tone={health.llm_provider === "none" ? "neutral" : "brand"}>
                    {health.llm_provider}
                  </Badge>
                </Row>
                <Row label="Active runs">{health.active_runs}</Row>
                {Object.entries(health.boosting_libraries).map(([name, present]) => (
                  <Row key={name} label={titleCase(name)}>
                    <Badge tone={present ? "good" : "neutral"}>
                      {present ? "installed" : "not installed"}
                    </Badge>
                  </Row>
                ))}
              </dl>
            )}
            {health?.llm_provider === "none" && (
              <p className="mt-4 rounded-xl border p-3.5 text-[12.5px] text-secondary">
                Running without an LLM. Every number, model and artifact is produced identically
                either way — runs simply report them without written analysis rather than
                substituting generated prose. Set{" "}
                <code className="font-mono">DATAID_LLM_PROVIDER=ollama</code> for a free local model.
              </p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Agents" subtitle="The pipeline, in execution order." />
          <ol className="divide-y p-5 pt-0">
            {agents === null ? (
              <Skeleton className="mt-5 h-40" />
            ) : (
              agents.map((agent, index) => (
                <li key={agent.name} className="flex gap-4 py-3.5">
                  <span className="tnum mt-0.5 text-[12px] text-muted">{index + 1}</span>
                  <div className="min-w-0">
                    <p className="text-[13.5px] font-medium">{agent.label}</p>
                    <p className="mt-0.5 text-[12.5px] text-secondary">{agent.description}</p>
                  </div>
                  {!agent.critical && (
                    <Badge tone="neutral" className="ml-auto shrink-0 self-start">
                      optional
                    </Badge>
                  )}
                </li>
              ))
            )}
          </ol>
        </Card>

        <Card>
          <CardHeader title="Keyboard shortcuts" />
          <dl className="divide-y p-5 pt-0">
            {SHORTCUTS.map((shortcut) => (
              <div key={shortcut.keys} className="flex items-center justify-between py-3">
                <dt className="text-[13px] text-secondary">{shortcut.action}</dt>
                <dd>
                  <span className="kbd">{shortcut.keys}</span>
                </dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>
    </>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <dt className="text-[13px] text-secondary">{label}</dt>
      <dd className="text-[13px] font-medium">{children}</dd>
    </div>
  );
}
