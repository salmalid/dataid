"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/dashboard/shell";
import { BarChart, StatTile } from "@/components/ui/charts";
import { Badge, Card, CardHeader, DataTable, EmptyState, Select, Skeleton } from "@/components/ui/primitives";
import { IconPulse } from "@/components/icons";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { driftTone, formatMetric, formatNumber } from "@/lib/utils";

type MonitoringData = Awaited<ReturnType<typeof api.monitoring>>;

export default function MonitoringPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [data, setData] = useState<MonitoringData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listProjects()
      .then((result) => {
        const trained = result.projects.filter((project) => project.status === "ready");
        setProjects(trained);
        if (trained.length) setSelected(trained[0].id);
      })
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setData(null);
    setError(null);
    api
      .monitoring(selected)
      .then(setData)
      .catch((exception) => setError((exception as Error).message));
  }, [selected]);

  if (projects === null) {
    return (
      <>
        <PageHeader title="Monitoring" />
        <div className="p-8">
          <Skeleton className="h-64" />
        </div>
      </>
    );
  }

  if (projects.length === 0) {
    return (
      <>
        <PageHeader title="Monitoring" />
        <div className="p-8">
          <EmptyState
            icon={<IconPulse className="h-9 w-9" />}
            title="No deployed models to monitor"
            description="Finish a run and its reference distribution and alert rules land here."
            action={
              <Link href="/dashboard" className="text-[13px] text-brand-500 underline-offset-2 hover:underline">
                Go to projects
              </Link>
            }
          />
        </div>
      </>
    );
  }

  const drift = data?.monitoring?.drift;
  const tone = drift ? driftTone(drift.status) : "good";

  return (
    <>
      <PageHeader
        title="Monitoring"
        description="Drift, decay and latency for models that have completed a run."
        action={
          <Select
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
            className="h-9 w-56 text-[13px]"
            aria-label="Select project"
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </Select>
        }
      />

      <div className="px-5 py-6 lg:px-8">
        {error && (
          <Card className="p-4 text-[13px] text-secondary" style={{ borderColor: "var(--status-critical)" }}>
            {error}
          </Card>
        )}

        {!data && !error && <Skeleton className="h-64" />}

        {data && (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile
                label={`Baseline ${data.baseline?.metric ?? ""}`}
                value={formatMetric(data.baseline?.metric ?? "", data.baseline?.value)}
                caption="captured at release"
              />
              <StatTile
                label="Max PSI"
                value={drift?.max_psi ?? 0}
                caption={drift?.status ?? "unknown"}
                tone={tone === "good" ? undefined : tone}
              />
              <StatTile
                label="Predictions served"
                value={formatNumber(data.prediction_count)}
                caption="through the control plane"
              />
              <StatTile
                label="p95 latency"
                value={`${data.latency?.p95_ms_per_row ?? "—"} ms`}
                caption="per row at training time"
              />
            </div>

            {drift && drift.features.length > 0 && (
              <BarChart
                data={drift.features.slice(0, 14).map((entry) => ({
                  label: entry.feature,
                  value: entry.psi,
                }))}
                title="Population Stability Index"
                subtitle="Above 0.10 warns · above 0.25 triggers a retrain"
                color="var(--status-warning)"
                formatValue={(value) => value.toFixed(4)}
              />
            )}

            <Card>
              <CardHeader title="Alert rules" subtitle="Shipped with the model, not invented during an incident." />
              <div className="mt-4">
                <DataTable
                  columns={[
                    { key: "signal", header: "Signal" },
                    { key: "warn", header: "Warn", align: "right" },
                    { key: "critical", header: "Critical", align: "right" },
                    { key: "action", header: "Action" },
                  ]}
                  rows={(data.monitoring?.alerts ?? []) as unknown as Record<string, unknown>[]}
                />
              </div>
            </Card>

            <Card>
              <CardHeader
                title="Recent predictions"
                subtitle="Every call through /predict is logged with its latency."
              />
              <div className="mt-4">
                <DataTable
                  columns={[
                    { key: "prediction", header: "Prediction" },
                    {
                      key: "confidence",
                      header: "Confidence",
                      align: "right",
                      render: (row) =>
                        row.confidence == null ? "—" : Number(row.confidence).toFixed(4),
                    },
                    {
                      key: "latency_ms",
                      header: "Latency",
                      align: "right",
                      render: (row) => `${Number(row.latency_ms).toFixed(2)} ms`,
                    },
                    { key: "created_at", header: "When", align: "right" },
                  ]}
                  rows={(data.recent_predictions ?? []) as Record<string, unknown>[]}
                  emptyMessage="No predictions scored yet."
                />
              </div>
            </Card>
          </div>
        )}
      </div>
    </>
  );
}
