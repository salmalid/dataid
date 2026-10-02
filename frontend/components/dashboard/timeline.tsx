"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Badge, Card, EmptyState } from "@/components/ui/primitives";
import { IconBolt, IconCheck, IconClock, IconX } from "@/components/icons";
import { api } from "@/lib/api";
import type { TimelineEvent } from "@/lib/types";
import { cn, formatClock, formatDuration } from "@/lib/utils";

const AGENT_LABELS: Record<string, string> = {
  pipeline: "Pipeline",
  data_detective: "Data Detective",
  data_cleaner: "Data Cleaner",
  feature_engineer: "Feature Engineer",
  ml_researcher: "ML Researcher",
  experiment_manager: "Experiment Manager",
  explainability: "Explainability Agent",
  deployment: "Deployment Agent",
  monitoring: "Monitoring Agent",
  generators: "Artifact Generators",
};

const ORDER = [
  "pipeline",
  "data_detective",
  "data_cleaner",
  "feature_engineer",
  "ml_researcher",
  "experiment_manager",
  "explainability",
  "deployment",
  "monitoring",
  "generators",
];

interface Stage {
  agent: string;
  status: TimelineEvent["status"];
  latest: string;
  progress: number;
  duration?: number;
  startedAt: string;
  events: TimelineEvent[];
}

/** Live run timeline. Subscribes to server-sent events, falls back to polling history. */
export function RunTimeline({
  runId,
  onFinished,
}: {
  runId: string | null;
  onFinished?: (status: "success" | "failed") => void;
}) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const finishedRef = useRef(false);

  useEffect(() => {
    if (!runId) return;
    setEvents([]);
    finishedRef.current = false;

    api
      .runTimeline(runId)
      .then((result) => setEvents(result.events))
      .catch(() => undefined);

    const unsubscribe = api.streamRun(
      runId,
      (event) => {
        setConnected(true);
        setEvents((current) => [...current, event]);
        if (event.step === "pipeline" && (event.status === "success" || event.status === "failed")) {
          if (!finishedRef.current) {
            finishedRef.current = true;
            onFinished?.(event.status);
          }
        }
      },
      () => setConnected(false),
    );

    return () => {
      unsubscribe();
      setConnected(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  const stages = useMemo<Stage[]>(() => {
    const byAgent = new Map<string, Stage>();
    for (const event of events) {
      const existing = byAgent.get(event.agent);
      const duration = event.detail?.duration as number | undefined;
      if (!existing) {
        byAgent.set(event.agent, {
          agent: event.agent,
          status: event.status,
          latest: event.message,
          progress: event.progress,
          duration,
          startedAt: event.timestamp,
          events: [event],
        });
      } else {
        existing.status = event.status;
        existing.latest = event.message || existing.latest;
        existing.progress = Math.max(existing.progress, event.progress);
        if (duration !== undefined) existing.duration = duration;
        existing.events.push(event);
      }
    }
    return [...byAgent.values()].sort(
      (a, b) => ORDER.indexOf(a.agent) - ORDER.indexOf(b.agent),
    );
  }, [events]);

  if (!runId) {
    return (
      <EmptyState
        icon={<IconClock className="h-9 w-9" />}
        title="No run selected"
        description="Start a run to watch the agents work in real time."
      />
    );
  }

  if (!stages.length) {
    return (
      <Card className="p-5">
        <div className="flex items-center gap-2.5 text-[13px] text-secondary">
          <IconBolt className="h-4 w-4 animate-pulse text-brand-400" />
          Waiting for the first agent to report…
        </div>
      </Card>
    );
  }

  const pipeline = stages.find((stage) => stage.agent === "pipeline");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Badge
          tone={
            pipeline?.status === "failed"
              ? "critical"
              : pipeline?.status === "success"
                ? "good"
                : "warning"
          }
        >
          {pipeline?.status === "running" && (
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
          )}
          {pipeline?.status ?? "queued"}
        </Badge>
        <span className="font-mono text-[12px] text-muted">run {runId}</span>
        {connected && <span className="text-[11.5px] text-muted">live</span>}
        {pipeline?.duration && (
          <span className="tnum ml-auto text-[12px] text-muted">
            {formatDuration(pipeline.duration)}
          </span>
        )}
      </div>

      <ol className="space-y-0">
        {stages
          .filter((stage) => stage.agent !== "pipeline")
          .map((stage) => (
            <StageRow key={stage.agent} stage={stage} />
          ))}
      </ol>

      {pipeline?.status === "failed" && (
        <Card className="p-4" style={{ borderColor: "var(--status-critical)" }}>
          <p className="text-[13px] font-medium" style={{ color: "var(--status-critical)" }}>
            Pipeline failed
          </p>
          <p className="mt-1 text-[12.5px] text-secondary">{pipeline.latest}</p>
        </Card>
      )}
    </div>
  );
}

function StageRow({ stage }: { stage: Stage }) {
  const [open, setOpen] = useState(false);
  const label = AGENT_LABELS[stage.agent] ?? stage.agent;

  const tone =
    stage.status === "success"
      ? "var(--status-good)"
      : stage.status === "failed"
        ? "var(--status-critical)"
        : "var(--series-1)";

  return (
    <li className="timeline-item">
      <div className="timeline-rail relative flex gap-4 pb-5">
        <span
          className="relative z-10 mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2"
          style={{ borderColor: tone, background: "var(--surface)" }}
        >
          {stage.status === "success" ? (
            <IconCheck className="h-3.5 w-3.5" style={{ color: tone }} />
          ) : stage.status === "failed" ? (
            <IconX className="h-3.5 w-3.5" style={{ color: tone }} />
          ) : (
            <span
              className="h-2 w-2 animate-pulse rounded-full"
              style={{ background: tone }}
            />
          )}
        </span>

        <div className="min-w-0 flex-1">
          <button
            onClick={() => setOpen((value) => !value)}
            className="flex w-full items-baseline justify-between gap-3 text-left"
          >
            <span className="text-[13.5px] font-medium">{label}</span>
            <span className="tnum shrink-0 text-[11.5px] text-muted">
              {stage.duration !== undefined
                ? formatDuration(stage.duration)
                : formatClock(stage.startedAt)}
            </span>
          </button>

          <p className="mt-0.5 truncate text-[12.5px] text-secondary">{stage.latest}</p>

          {stage.status === "running" && (
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-black/[0.07] dark:bg-white/[0.09]">
              <div
                className="h-full rounded-full bg-brand-gradient transition-all duration-500"
                style={{ width: `${Math.max(stage.progress * 100, 6)}%` }}
              />
            </div>
          )}

          {open && stage.events.length > 1 && (
            <ul className="mt-3 space-y-1 border-l pl-3.5">
              {stage.events.map((event, index) => (
                <li key={index} className="flex gap-2.5 text-[12px] text-muted">
                  <span className="tnum shrink-0">{formatClock(event.timestamp)}</span>
                  <span className="min-w-0">{event.message}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </li>
  );
}
