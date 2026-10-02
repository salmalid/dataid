"use client";

import { useState } from "react";
import { Badge, Button, Card, CardHeader, DataTable, EmptyState } from "@/components/ui/primitives";
import { IconClock, IconX } from "@/components/icons";
import { api } from "@/lib/api";
import type { RunResult, RunSummary } from "@/lib/types";
import { formatDuration, formatMetric, formatRelativeTime } from "@/lib/utils";

const STATUS_TONE = {
  success: "good",
  failed: "critical",
  running: "warning",
  queued: "neutral",
} as const;

export function ExperimentsPanel({
  runs,
  projectId,
  onSelect,
}: {
  runs: RunSummary[];
  projectId: string;
  onSelect: (result: RunResult) => void;
}) {
  const [compare, setCompare] = useState<string[]>([]);
  const [diff, setDiff] = useState<Awaited<ReturnType<typeof api.compareRuns>> | null>(null);
  const [loading, setLoading] = useState(false);

  const toggleCompare = (runId: string) => {
    setDiff(null);
    setCompare((current) =>
      current.includes(runId)
        ? current.filter((id) => id !== runId)
        : [...current, runId].slice(-2),
    );
  };

  const runCompare = async () => {
    if (compare.length !== 2) return;
    setLoading(true);
    try {
      setDiff(await api.compareRuns(compare[0], compare[1]));
    } catch {
      setDiff(null);
    } finally {
      setLoading(false);
    }
  };

  const open = async (runId: string) => {
    const { run } = await api.getRun(runId);
    if (run.result) onSelect(run.result);
  };

  if (!runs.length) {
    return (
      <EmptyState
        icon={<IconClock className="h-9 w-9" />}
        title="No runs yet"
        description="Upload a dataset and start a run — every version is kept here for comparison."
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Run history"
          subtitle="Every run is versioned. Select two to diff their metrics."
          action={
            compare.length === 2 && (
              <Button size="sm" loading={loading} onClick={runCompare}>
                Compare v
                {runs.find((run) => run.id === compare[0])?.version} ↔ v
                {runs.find((run) => run.id === compare[1])?.version}
              </Button>
            )
          }
        />
        <div className="mt-4">
          <DataTable
            columns={[
              {
                key: "select",
                header: "",
                render: (row) => (
                  <input
                    type="checkbox"
                    aria-label={`Compare run ${row.version}`}
                    checked={compare.includes(String(row.id))}
                    onChange={() => toggleCompare(String(row.id))}
                    className="h-3.5 w-3.5 cursor-pointer accent-[color:var(--series-1)]"
                  />
                ),
              },
              {
                key: "version",
                header: "Version",
                render: (row) => (
                  <button
                    onClick={() => open(String(row.id))}
                    className="font-medium underline-offset-2 hover:underline"
                  >
                    v{String(row.version)}
                  </button>
                ),
              },
              {
                key: "status",
                header: "Status",
                render: (row) => (
                  <Badge tone={STATUS_TONE[row.status as keyof typeof STATUS_TONE] ?? "neutral"}>
                    {String(row.status)}
                  </Badge>
                ),
              },
              { key: "best_model", header: "Winner", render: (row) => String(row.best_model ?? "—") },
              {
                key: "primary_value",
                header: "Metric",
                align: "right",
                render: (row) =>
                  row.primary_value == null
                    ? "—"
                    : `${row.primary_metric} ${formatMetric(String(row.primary_metric), Number(row.primary_value))}`,
              },
              {
                key: "duration_seconds",
                header: "Duration",
                align: "right",
                render: (row) => formatDuration(row.duration_seconds as number | null),
              },
              {
                key: "created_at",
                header: "Started",
                align: "right",
                render: (row) => formatRelativeTime(String(row.created_at)),
              },
            ]}
            rows={runs as unknown as Record<string, unknown>[]}
          />
        </div>
      </Card>

      {diff && (
        <Card>
          <CardHeader
            title={`v${diff.left.version} → v${diff.right.version}`}
            subtitle={`${diff.left.model} versus ${diff.right.model}`}
            action={
              <button
                onClick={() => setDiff(null)}
                aria-label="Close comparison"
                className="rounded-lg p-1.5 text-muted hover:bg-black/[0.05] dark:hover:bg-white/[0.07]"
              >
                <IconX className="h-4 w-4" />
              </button>
            }
          />
          <div className="mt-4">
            <DataTable
              columns={[
                { key: "metric", header: "Metric" },
                { key: "left", header: `v${diff.left.version}`, align: "right" },
                { key: "right", header: `v${diff.right.version}`, align: "right" },
                {
                  key: "delta",
                  header: "Δ",
                  align: "right",
                  render: (row) => {
                    const delta = Number(row.delta);
                    return (
                      <span
                        className="font-medium"
                        style={{
                          color:
                            delta === 0
                              ? "var(--ink-muted)"
                              : delta > 0
                                ? "var(--success-text)"
                                : "var(--status-critical)",
                        }}
                      >
                        {delta > 0 ? "+" : ""}
                        {delta.toFixed(5)}
                      </span>
                    );
                  },
                },
                {
                  key: "pct_change",
                  header: "% change",
                  align: "right",
                  render: (row) =>
                    row.pct_change == null ? "—" : `${Number(row.pct_change).toFixed(2)}%`,
                },
              ]}
              rows={diff.deltas as unknown as Record<string, unknown>[]}
            />
          </div>
          <p className="px-5 pb-5 pt-3 text-[12px] text-muted">
            A positive delta is not automatically better — for error metrics like MAE and RMSE, lower
            wins.
          </p>
        </Card>
      )}
    </div>
  );
}
