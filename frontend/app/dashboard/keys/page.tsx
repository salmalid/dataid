"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/dashboard/shell";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataTable,
  EmptyState,
  Field,
  Input,
  Skeleton,
} from "@/components/ui/primitives";
import { IconCheck, IconKey, IconX } from "@/components/icons";
import { api } from "@/lib/api";
import type { ApiKey } from "@/lib/types";
import { formatRelativeTime } from "@/lib/utils";

export default function KeysPage() {
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [issued, setIssued] = useState<ApiKey | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    api
      .listKeys()
      .then((result) => setKeys(result.keys))
      .catch(() => setKeys([]));
  }, []);

  useEffect(load, [load]);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setCreating(true);
    try {
      const key = await api.createKey(name.trim());
      setIssued(key);
      setName("");
      load();
    } finally {
      setCreating(false);
    }
  };

  const revoke = async (id: string) => {
    await api.revokeKey(id);
    load();
  };

  return (
    <>
      <PageHeader
        title="API keys"
        description="Programmatic access to the control plane. Only a hash is stored — the token is shown once."
      />

      <div className="px-5 py-6 lg:px-8">
        {issued?.token && (
          <Card className="mb-6 p-5" style={{ borderColor: "var(--status-good)" }}>
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="flex items-center gap-2 text-[14px] font-semibold">
                  <IconCheck className="h-4 w-4" style={{ color: "var(--status-good)" }} />
                  Key created — copy it now
                </p>
                <p className="mt-1.5 text-[12.5px] text-secondary">
                  This is the only time the full token is shown. dataid stores a SHA-256 hash and
                  cannot recover it.
                </p>
                <code className="mt-3 block overflow-x-auto rounded-lg border bg-black/[0.03] px-3 py-2 font-mono text-[12px] dark:bg-white/[0.05]">
                  {issued.token}
                </code>
              </div>
              <button
                onClick={() => setIssued(null)}
                aria-label="Dismiss"
                className="shrink-0 rounded-lg p-1.5 text-muted hover:bg-black/[0.05] dark:hover:bg-white/[0.07]"
              >
                <IconX className="h-4 w-4" />
              </button>
            </div>
            <Button
              size="sm"
              variant="secondary"
              className="mt-4"
              onClick={() => {
                navigator.clipboard?.writeText(issued.token ?? "");
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1800);
              }}
            >
              {copied ? "Copied" : "Copy token"}
            </Button>
          </Card>
        )}

        <Card className="mb-6">
          <CardHeader title="Create a key" subtitle="Name it after where it will be used." />
          <form onSubmit={create} className="flex flex-wrap items-end gap-3 p-5">
            <Field label="Key name">
              <Input
                required
                maxLength={80}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="ci-pipeline"
                className="w-64"
              />
            </Field>
            <Button type="submit" loading={creating} disabled={!name.trim()}>
              <IconKey className="h-4 w-4" />
              Generate key
            </Button>
          </form>
        </Card>

        {keys === null ? (
          <Skeleton className="h-48" />
        ) : keys.length === 0 ? (
          <EmptyState
            icon={<IconKey className="h-9 w-9" />}
            title="No keys yet"
            description="Generate one above to call the API from a script or CI job."
          />
        ) : (
          <Card>
            <CardHeader title={`${keys.length} keys`} />
            <div className="mt-4">
              <DataTable
                columns={[
                  { key: "name", header: "Name" },
                  {
                    key: "prefix",
                    header: "Prefix",
                    render: (row) => (
                      <code className="font-mono text-[11.5px]">{String(row.prefix)}…</code>
                    ),
                  },
                  {
                    key: "scopes",
                    header: "Scopes",
                    render: (row) => (
                      <span className="flex gap-1.5">
                        {(row.scopes as string[]).map((scope) => (
                          <Badge key={scope} tone="neutral">
                            {scope}
                          </Badge>
                        ))}
                      </span>
                    ),
                  },
                  {
                    key: "revoked",
                    header: "Status",
                    render: (row) =>
                      row.revoked ? (
                        <Badge tone="critical">revoked</Badge>
                      ) : (
                        <Badge tone="good">active</Badge>
                      ),
                  },
                  {
                    key: "created_at",
                    header: "Created",
                    align: "right",
                    render: (row) => formatRelativeTime(String(row.created_at)),
                  },
                  {
                    key: "actions",
                    header: "",
                    align: "right",
                    render: (row) =>
                      row.revoked ? null : (
                        <Button size="sm" variant="ghost" onClick={() => revoke(String(row.id))}>
                          Revoke
                        </Button>
                      ),
                  },
                ]}
                rows={keys as unknown as Record<string, unknown>[]}
              />
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
