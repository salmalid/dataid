"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/dashboard/shell";
import { ChatPanel } from "@/components/dashboard/chat";
import { DatasetPanel } from "@/components/dashboard/dataset";
import { RunTimeline } from "@/components/dashboard/timeline";
import {
  DataPanel,
  DeployPanel,
  ExplainPanel,
  FairnessPanel,
  ModelsPanel,
  MonitoringPanel,
  OverviewPanel,
} from "@/components/dashboard/panels";
import { ExperimentsPanel } from "@/components/dashboard/experiments";
import { ProjectSettingsPanel } from "@/components/dashboard/project-settings";
import { Badge, Button, Card, EmptyState, Skeleton, Tabs } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { Project, RunResult, RunSummary } from "@/lib/types";
import { formatMetric, formatNumber } from "@/lib/utils";

type Loaded = {
  project: Project;
  runs: RunSummary[];
  latest_result: RunResult | null;
};

export default function ProjectPage() {
  const params = useParams<{ projectId: string }>();
  const router = useRouter();
  const search = useSearchParams();
  const projectId = params.projectId;

  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<string | null>(search.get("run"));
  const [tab, setTab] = useState(search.get("tab") ?? "dataset");
  const [selectedResult, setSelectedResult] = useState<RunResult | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await api.getProject(projectId);
      setData(result);
      setSelectedResult((current) => current ?? result.latest_result);
      if (!search.get("tab")) {
        setTab(result.latest_result ? "overview" : "dataset");
      }
    } catch (exception) {
      setError((exception as Error).message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const onRunStarted = useCallback((runId: string) => {
    setActiveRun(runId);
    setTab("timeline");
  }, []);

  const onRunFinished = useCallback(
    async (status: "success" | "failed") => {
      // Unguarded, this is the one path that can reject into an unhandled runtime error:
      // the run ends, the fetch lands while the API is unavailable, and the overlay takes
      // over a page whose data is otherwise fine.
      try {
        await load();
        if (status === "success") {
          const refreshed = await api.getProject(projectId);
          setSelectedResult(refreshed.latest_result);
          setTab("overview");
        }
      } catch (exception) {
        setError((exception as Error).message);
      }
    },
    [load, projectId],
  );

  const result = selectedResult;

  const tabs = useMemo(() => {
    const base: { id: string; label: string; count?: number }[] = [
      { id: "dataset", label: "Dataset" },
      { id: "chat", label: "AI Chat" },
      { id: "timeline", label: "Timeline" },
    ];
    if (result) {
      base.splice(0, 0, { id: "overview", label: "Overview" });
      base.push(
        { id: "data", label: "Data quality", count: result.issues?.length },
        { id: "models", label: "Models", count: result.leaderboard?.length },
        { id: "explain", label: "Explainability" },
        { id: "fairness", label: "Fairness" },
        { id: "deploy", label: "Deploy" },
        { id: "monitoring", label: "Monitoring" },
      );
    }
    base.push(
      { id: "experiments", label: "Experiments", count: data?.runs.length },
      { id: "settings", label: "Settings" },
    );
    return base;
  }, [result, data?.runs.length]);

  if (error) {
    return (
      <div className="p-8">
        <EmptyState
          title="Could not load this project"
          description={error}
          action={
            <Button
              onClick={() => {
                setError(null);
                load();
              }}
            >
              Try again
            </Button>
          }
        />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-6 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
        <div className="grid gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((index) => (
            <Skeleton key={index} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-72" />
      </div>
    );
  }

  const { project, runs } = data;
  const latestRun = runs[0];

  return (
    <>
      <PageHeader
        breadcrumb={[
          { label: "Projects", href: "/dashboard" },
          { label: project.name, href: `/dashboard/${project.id}` },
        ]}
        title={project.name}
        description={project.description || undefined}
        action={
          <div className="flex flex-wrap items-center gap-2">
            {project.rows > 0 && (
              <Badge tone="neutral">
                {formatNumber(project.rows)} × {project.columns}
              </Badge>
            )}
            {project.task_type && <Badge tone="brand">{project.task_type}</Badge>}
            {latestRun?.primary_value != null && (
              <Badge tone="good">
                {latestRun.primary_metric} {formatMetric(latestRun.primary_metric ?? "", latestRun.primary_value)}
              </Badge>
            )}
          </div>
        }
      />

      <div className="px-5 lg:px-8">
        <Tabs
          tabs={tabs}
          active={tab}
          onChange={(next) => {
            setTab(next);
            router.replace(`/dashboard/${projectId}?tab=${next}`, { scroll: false });
          }}
        />
      </div>

      <div className="px-5 py-6 lg:px-8">
        {tab === "overview" && result && (
          <OverviewPanel result={result} runId={result.run_id} />
        )}
        {tab === "dataset" && (
          <DatasetPanel
            project={project}
            onProjectChange={(next) => setData((current) => (current ? { ...current, project: next } : current))}
            onRunStarted={onRunStarted}
          />
        )}
        {tab === "chat" && <ChatPanel project={project} onRunStarted={onRunStarted} />}
        {tab === "timeline" && (
          <RunTimeline runId={activeRun ?? latestRun?.id ?? null} onFinished={onRunFinished} />
        )}
        {tab === "data" && result && <DataPanel result={result} />}
        {tab === "models" && result && <ModelsPanel result={result} />}
        {tab === "explain" && result && <ExplainPanel result={result} />}
        {tab === "fairness" && result && <FairnessPanel result={result} />}
        {tab === "deploy" && result && <DeployPanel result={result} runId={result.run_id} />}
        {tab === "monitoring" && result && <MonitoringPanel result={result} />}
        {tab === "experiments" && (
          <ExperimentsPanel
            runs={runs}
            projectId={projectId}
            onSelect={(runResult) => {
              setSelectedResult(runResult);
              setTab("overview");
            }}
          />
        )}
        {tab === "settings" && (
          <ProjectSettingsPanel
            project={project}
            onChange={(next) =>
              setData((current) => (current ? { ...current, project: next } : current))
            }
            onDeleted={() => router.push("/dashboard")}
          />
        )}
      </div>
    </>
  );
}
