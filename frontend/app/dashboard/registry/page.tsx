"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/dashboard/shell";
import { StatTile } from "@/components/ui/charts";
import { Badge, Button, Card, CardHeader, DataTable, EmptyState, Skeleton } from "@/components/ui/primitives";
import { IconLayers } from "@/components/icons";
import { api } from "@/lib/api";
import type { RegistryEntry } from "@/lib/types";
import { formatMetric, formatRelativeTime } from "@/lib/utils";

const STAGE_TONE = {
  production: "good",
  staging: "brand",
  archived: "neutral",
} as const;

export default function RegistryPage() {
  const [models, setModels] = useState<RegistryEntry[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .registry()
      .then((result) => setModels(result.models))
      .catch(() => setModels([]));
  }, []);

  useEffect(load, [load]);

  const promote = async (id: string, stage: "staging" | "production" | "archived") => {
    setBusy(id);
    try {
      await api.promote(id, stage);
      load();
    } finally {
      setBusy(null);
    }
  };

  const production = models?.filter((model) => model.stage === "production").length ?? 0;
  const staging = models?.filter((model) => model.stage === "staging").length ?? 0;

  return (
    <>
      <PageHeader
        title="Model registry"
        description="Every successful run registers its winner. Promote one to production when it earns it."
      />

      <div className="px-5 py-6 lg:px-8">
        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          <StatTile label="Registered models" value={models?.length ?? "—"} caption="all versions" />
          <StatTile label="In production" value={production} caption="one per project" />
          <StatTile label="In staging" value={staging} caption="awaiting promotion" />
        </div>

        {models === null ? (
          <Skeleton className="h-64" />
        ) : models.length === 0 ? (
          <EmptyState
            icon={<IconLayers className="h-9 w-9" />}
            title="Nothing registered yet"
            description="Finish a run and its winning model lands here automatically."
            action={
              <Link href="/dashboard">
                <Button>Go to projects</Button>
              </Link>
            }
          />
        ) : (
          <Card>
            <CardHeader
              title="All models"
              subtitle="Promoting to production archives whatever held the slot before it."
            />
            <div className="mt-4">
              <DataTable
                columns={[
                  { key: "name", header: "Model" },
                  {
                    key: "version",
                    header: "Version",
                    render: (row) => `v${String(row.version)}`,
                  },
                  {
                    key: "stage",
                    header: "Stage",
                    render: (row) => (
                      <Badge tone={STAGE_TONE[row.stage as keyof typeof STAGE_TONE] ?? "neutral"}>
                        {String(row.stage)}
                      </Badge>
                    ),
                  },
                  {
                    key: "metric_value",
                    header: "Metric",
                    align: "right",
                    render: (row) =>
                      `${row.metric_name} ${formatMetric(String(row.metric_name), Number(row.metric_value))}`,
                  },
                  {
                    key: "project_id",
                    header: "Project",
                    render: (row) => (
                      <Link
                        href={`/dashboard/${row.project_id}`}
                        className="font-mono text-[11.5px] underline-offset-2 hover:underline"
                      >
                        {String(row.project_id).slice(0, 12)}
                      </Link>
                    ),
                  },
                  {
                    key: "created_at",
                    header: "Registered",
                    align: "right",
                    render: (row) => formatRelativeTime(String(row.created_at)),
                  },
                  {
                    key: "actions",
                    header: "",
                    align: "right",
                    render: (row) => (
                      <div className="flex justify-end gap-1.5">
                        {row.stage !== "production" && (
                          <Button
                            size="sm"
                            variant="subtle"
                            loading={busy === row.id}
                            onClick={() => promote(String(row.id), "production")}
                          >
                            Promote
                          </Button>
                        )}
                        {row.stage !== "archived" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => promote(String(row.id), "archived")}
                          >
                            Archive
                          </Button>
                        )}
                      </div>
                    ),
                  },
                ]}
                rows={models as unknown as Record<string, unknown>[]}
              />
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
