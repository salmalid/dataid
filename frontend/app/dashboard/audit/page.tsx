"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/dashboard/shell";
import { Badge, Card, CardHeader, DataTable, EmptyState, Input, Skeleton } from "@/components/ui/primitives";
import { IconShield } from "@/components/icons";
import { api } from "@/lib/api";
import type { AuditEntry } from "@/lib/types";
import { formatRelativeTime, titleCase } from "@/lib/utils";

const ACTION_TONE: Record<string, "brand" | "good" | "warning" | "critical" | "neutral"> = {
  create: "good",
  upload: "brand",
  start: "brand",
  update: "neutral",
  promote: "good",
  revoke: "warning",
  delete: "critical",
};

function toneFor(action: string) {
  const verb = action.split(".")[1] ?? "";
  return ACTION_TONE[verb] ?? "neutral";
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api
      .audit(200)
      .then((result) => setEntries(result.entries))
      .catch(() => setEntries([]));
  }, []);

  const filtered = (entries ?? []).filter((entry) => {
    const needle = query.trim().toLowerCase();
    if (!needle) return true;
    return (
      entry.action.toLowerCase().includes(needle) ||
      entry.actor.toLowerCase().includes(needle) ||
      entry.resource_id.toLowerCase().includes(needle)
    );
  });

  return (
    <>
      <PageHeader
        title="Audit log"
        description="Append-only record of every action taken in this workspace."
      />

      <div className="px-5 py-6 lg:px-8">
        {entries === null ? (
          <Skeleton className="h-72" />
        ) : entries.length === 0 ? (
          <EmptyState
            icon={<IconShield className="h-9 w-9" />}
            title="Nothing logged yet"
            description="Creating projects, uploading data, starting runs and promoting models all land here."
          />
        ) : (
          <Card>
            <CardHeader
              title={`${filtered.length} entries`}
              subtitle="Newest first."
              action={
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Filter…"
                  aria-label="Filter audit entries"
                  className="h-9 w-48 text-[13px]"
                />
              }
            />
            <div className="mt-4">
              <DataTable
                columns={[
                  {
                    key: "action",
                    header: "Action",
                    render: (row) => (
                      <Badge tone={toneFor(String(row.action))}>{String(row.action)}</Badge>
                    ),
                  },
                  { key: "actor", header: "Actor" },
                  {
                    key: "resource_type",
                    header: "Resource",
                    render: (row) => titleCase(String(row.resource_type)),
                  },
                  {
                    key: "resource_id",
                    header: "ID",
                    render: (row) => (
                      <code className="font-mono text-[11.5px] text-muted">
                        {String(row.resource_id)}
                      </code>
                    ),
                  },
                  {
                    key: "detail",
                    header: "Detail",
                    render: (row) => {
                      const detail = row.detail as Record<string, unknown>;
                      const summary = Object.entries(detail ?? {})
                        .slice(0, 2)
                        .map(([key, value]) => `${key}=${String(value)}`)
                        .join(" · ");
                      return <span className="text-secondary">{summary || "—"}</span>;
                    },
                  },
                  {
                    key: "created_at",
                    header: "When",
                    align: "right",
                    render: (row) => formatRelativeTime(String(row.created_at)),
                  },
                ]}
                rows={filtered as unknown as Record<string, unknown>[]}
                emptyMessage="No entries match that filter."
              />
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
