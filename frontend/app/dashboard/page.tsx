"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/dashboard/shell";
import { StatTile } from "@/components/ui/charts";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  Skeleton,
  Textarea,
} from "@/components/ui/primitives";
import { IconDatabase, IconGrid, IconPlus, IconX } from "@/components/icons";
import { api } from "@/lib/api";
import type { Project, WorkspaceStats } from "@/lib/types";
import { cn, formatDuration, formatMetric, formatNumber, formatRelativeTime, seriesVar } from "@/lib/utils";

const STATUS_TONE: Record<string, "neutral" | "brand" | "good" | "warning"> = {
  draft: "neutral",
  ready_to_run: "brand",
  running: "warning",
  ready: "good",
};

const STATUS_LABEL: Record<string, string> = {
  draft: "No dataset",
  ready_to_run: "Ready to run",
  running: "Running",
  ready: "Trained",
};

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [stats, setStats] = useState<WorkspaceStats | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listProjects()
      .then((result) => setProjects(result.projects))
      .catch((exception) => {
        setProjects([]);
        setError(exception.message);
      });
    api.stats().then(setStats).catch(() => setStats(null));
  }, []);

  useEffect(load, [load]);

  return (
    <>
      <PageHeader
        title="Projects"
        description="Each project owns a dataset, its run history and the models it produced."
        action={
          <Button onClick={() => setCreating(true)}>
            <IconPlus className="h-4 w-4" />
            New project
          </Button>
        }
      />

      <div className="px-5 py-6 lg:px-8">
        {stats && (
          <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Projects" value={formatNumber(stats.projects)} caption="in this workspace" />
            <StatTile
              label="Runs completed"
              value={formatNumber(stats.successful_runs)}
              caption={`${stats.success_rate}% success rate`}
            />
            <StatTile
              label="Models registered"
              value={formatNumber(stats.models)}
              caption={`${stats.models_in_production} in production`}
            />
            <StatTile
              label="Average run"
              value={formatDuration(stats.avg_run_seconds)}
              caption="end to end"
            />
          </div>
        )}

        {stats && stats.active_runs.length > 0 && (
          <Card className="mb-6 flex flex-wrap items-center gap-3 p-4">
            <Badge tone="warning">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
              {stats.active_runs.length} running
            </Badge>
            {stats.active_runs.map((run) => (
              <Link
                key={run.run_id}
                href={`/dashboard/${run.project_id}?tab=timeline&run=${run.run_id}`}
                className="text-[13px] text-secondary underline-offset-2 hover:underline"
              >
                {run.project_name}
              </Link>
            ))}
          </Card>
        )}

        {error && (
          <Card className="mb-6 p-4 text-[13px]" style={{ borderColor: "var(--status-critical)" }}>
            <span className="font-medium" style={{ color: "var(--status-critical)" }}>
              Could not reach the API.
            </span>{" "}
            <span className="text-secondary">{error}</span>
          </Card>
        )}

        {projects === null ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((index) => (
              <Card key={index} className="p-5">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="mt-3 h-3 w-2/3" />
                <Skeleton className="mt-8 h-7 w-1/3" />
              </Card>
            ))}
          </div>
        ) : projects.length === 0 ? (
          <EmptyState
            icon={<IconGrid className="h-10 w-10" />}
            title="No projects yet"
            description="Create one, drop in a CSV, and the agents take it from there."
            action={
              <Button onClick={() => setCreating(true)}>
                <IconPlus className="h-4 w-4" />
                New project
              </Button>
            }
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project, index) => (
              <ProjectCard key={project.id} project={project} tone={index} />
            ))}
          </div>
        )}
      </div>

      {creating && (
        <NewProjectDialog
          onClose={() => setCreating(false)}
          onCreated={(project) => router.push(`/dashboard/${project.id}`)}
        />
      )}
    </>
  );
}

function ProjectCard({ project, tone }: { project: Project; tone: number }) {
  const status = project.status ?? "draft";
  return (
    <Link href={`/dashboard/${project.id}`} className="group block">
      <Card className="h-full p-5 transition-all group-hover:-translate-y-0.5 group-hover:border-brand-500/40">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-[15px] font-semibold">{project.name}</h3>
            <p className="mt-0.5 truncate text-[12px] text-muted">
              {project.dataset_name ?? "No dataset uploaded"}
            </p>
          </div>
          <span
            className="mt-1 h-2 w-2 shrink-0 rounded-full"
            style={{ background: seriesVar(tone) }}
            aria-hidden
          />
        </div>

        {project.description && (
          <p className="mt-3 line-clamp-2 text-[12.5px] text-secondary">{project.description}</p>
        )}

        <div className="mt-5">
          {project.best_metric != null ? (
            <>
              <p className="tnum text-[22px] font-semibold leading-none">
                {formatMetric(project.best_metric_name ?? "", project.best_metric)}
              </p>
              <p className="mt-1.5 text-[12px] text-secondary">
                {project.best_metric_name} · {project.best_model}
              </p>
            </>
          ) : (
            <p className="text-[13px] text-muted">Not trained yet</p>
          )}
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2 border-t pt-4">
          <Badge tone={STATUS_TONE[status] ?? "neutral"}>{STATUS_LABEL[status] ?? status}</Badge>
          {project.rows > 0 && (
            <span className="tnum text-[11.5px] text-muted">
              {formatNumber(project.rows)} × {project.columns}
            </span>
          )}
          {(project.run_count ?? 0) > 0 && (
            <span className="text-[11.5px] text-muted">
              {project.run_count} run{project.run_count === 1 ? "" : "s"}
            </span>
          )}
          <span className="ml-auto text-[11.5px] text-muted">
            {formatRelativeTime(project.updated_at)}
          </span>
        </div>
      </Card>
    </Link>
  );
}

function NewProjectDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (project: Project) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const project = await api.createProject({ name: name.trim(), description: description.trim() });
      onCreated(project);
    } catch (exception) {
      setError((exception as Error).message);
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <Card
        className="w-full max-w-md p-6"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Create project"
      >
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-[17px] font-semibold">New project</h2>
            <p className="mt-1 text-[13px] text-secondary">
              You will upload the dataset on the next screen.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-muted transition-colors hover:bg-black/[0.05] dark:hover:bg-white/[0.07]"
          >
            <IconX className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <Field label="Project name">
            <Input
              autoFocus
              required
              maxLength={120}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Customer Churn"
            />
          </Field>
          <Field label="Description" hint="Optional — what decision is this model supporting?">
            <Textarea
              rows={3}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Predict which subscribers are likely to cancel in the next 30 days."
            />
          </Field>

          {error && (
            <p className="text-[12.5px]" style={{ color: "var(--status-critical)" }}>
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={busy} disabled={!name.trim()}>
              Create project
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
