"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Button, Card, CardHeader, DataTable, Field, Select, Toggle } from "@/components/ui/primitives";
import { StatTile } from "@/components/ui/charts";
import { IconAlert, IconCheck, IconDatabase, IconSparkle, IconUpload } from "@/components/icons";
import { api } from "@/lib/api";
import type { ArtifactOption, DatasetUnderstanding, Project, TaskOption } from "@/lib/types";
import { cn, formatBytes, formatDuration, formatNumber } from "@/lib/utils";

export function DatasetPanel({
  project,
  onProjectChange,
  onRunStarted,
}: {
  project: Project;
  onProjectChange: (project: Project) => void;
  onRunStarted: (runId: string) => void;
}) {
  const [understanding, setUnderstanding] = useState<DatasetUnderstanding | null>(null);
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof api.previewDataset>> | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState(project.target_column ?? "");
  const [sensitive, setSensitive] = useState(project.sensitive_column ?? "");
  const [tune, setTune] = useState(false);
  const [starting, setStarting] = useState(false);
  const [options, setOptions] = useState<ArtifactOption[]>([]);
  const [artifacts, setArtifacts] = useState<string[] | null>(null);
  const [tasks, setTasks] = useState<TaskOption[]>([]);
  const [task, setTask] = useState<string>("");
  const [timeColumn, setTimeColumn] = useState("");
  const [groupColumn, setGroupColumn] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const activeTask = tasks.find((t) => t.key === task) ?? null;
  // With no explicit task the backend infers classification vs regression, which needs a target.
  const needsTarget = activeTask ? activeTask.needs_target : true;

  // The catalog is served by the backend so the checkboxes can never drift from what the
  // pipeline actually knows how to generate. Everything starts selected.
  useEffect(() => {
    let cancelled = false;
    api
      .agents()
      .then((result) => {
        if (cancelled) return;
        setOptions(result.artifacts ?? []);
        setArtifacts((current) => current ?? (result.artifacts ?? []).map((a) => a.key));
        setTasks(result.tasks ?? []);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = artifacts ?? [];
  const toggleArtifact = (key: string) =>
    setArtifacts((current) => {
      const base = current ?? options.map((a) => a.key);
      return base.includes(key) ? base.filter((k) => k !== key) : [...base, key];
    });

  const loadDataset = useCallback(() => {
    if (!project.dataset_path) return;
    api.understanding(project.id).then(setUnderstanding).catch(() => undefined);
    api.previewDataset(project.id, 25).then(setPreview).catch(() => undefined);
  }, [project.id, project.dataset_path]);

  useEffect(loadDataset, [loadDataset]);

  const upload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const result = await api.uploadDataset(project.id, file);
      setUnderstanding(result.understanding);
      onProjectChange(result.project);
      setTarget(result.understanding.suggested_target ?? "");
      const preview = await api.previewDataset(project.id, 25);
      setPreview(preview);
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const startRun = async () => {
    setStarting(true);
    setError(null);
    try {
      const { run } = await api.startRun(project.id, {
        target_column: needsTarget || target ? target || undefined : undefined,
        sensitive_column: sensitive || null,
        tune,
        artifacts: selected,
        task_type: task || undefined,
        time_column: activeTask?.needs_time ? timeColumn || null : null,
        group_column: activeTask?.needs_group ? groupColumn || null : null,
      });
      onRunStarted(run.id);
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setStarting(false);
    }
  };

  if (!project.dataset_path) {
    return (
      <div className="space-y-5">
        <DropZone
          dragging={dragging}
          uploading={uploading}
          onDragChange={setDragging}
          onFile={upload}
          inputRef={inputRef}
        />
        {error && (
          <Card className="p-4" style={{ borderColor: "var(--status-critical)" }}>
            <p className="text-[13px]" style={{ color: "var(--status-critical)" }}>
              {error}
            </p>
          </Card>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {understanding && <UnderstandingCard understanding={understanding} />}

      <Card className="p-5">
        <h3 className="text-[15px] font-semibold">Run configuration</h3>
        <p className="mt-1.5 text-[13px] text-secondary">
          The suggestion below is a starting point — override anything before launching.
        </p>

        {tasks.length > 0 && (
          <div className="mt-5">
            <p className="text-[13px] font-semibold">What are you trying to do?</p>
            <p className="mt-0.5 text-[12.5px] text-secondary">
              Leave this on auto-detect and dataid infers classification or regression from the
              target. Pick one explicitly to reach the other families.
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              <button
                type="button"
                onClick={() => setTask("")}
                className={cn(
                  "rounded-xl border p-3 text-left transition-colors",
                  task === "" ? "border-[var(--brand)] bg-[var(--brand-subtle)]"
                              : "hover:bg-black/[0.02] dark:hover:bg-white/[0.03]",
                )}
              >
                <span className="block text-[13px] font-medium">Auto-detect</span>
                <span className="mt-0.5 block text-[12px] text-secondary">
                  Classification or regression, inferred from the target.
                </span>
              </button>
              {tasks.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => setTask(option.key)}
                  className={cn(
                    "rounded-xl border p-3 text-left transition-colors",
                    task === option.key ? "border-[var(--brand)] bg-[var(--brand-subtle)]"
                                        : "hover:bg-black/[0.02] dark:hover:bg-white/[0.03]",
                  )}
                >
                  <span className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[13px] font-medium">{option.label}</span>
                    {!option.needs_target && (
                      <span className="rounded-full border px-1.5 text-[10px] text-muted">
                        no target
                      </span>
                    )}
                  </span>
                  <span className="mt-0.5 block text-[12px] text-secondary">{option.example}</span>
                </button>
              ))}
            </div>
            {activeTask && (
              <p className="mt-2.5 text-[12.5px] text-secondary">{activeTask.description}</p>
            )}
          </div>
        )}

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Field
            label={needsTarget ? "Target column" : "Target column (optional)"}
            hint={
              needsTarget
                ? "What the model predicts."
                : activeTask?.key === "anomaly"
                  ? "Not required. Supply a label and precision/recall are reported against it."
                  : "Not required for this task — it is kept out of the features either way."
            }
          >
            <Select value={target} onChange={(event) => setTarget(event.target.value)}>
              <option value="">{needsTarget ? "Select a column…" : "None"}</option>
              {(understanding?.column_names ?? []).map((name) => (
                <option key={name} value={name}>
                  {name}
                  {name === understanding?.suggested_target ? "  (suggested)" : ""}
                </option>
              ))}
            </Select>
          </Field>

          {activeTask?.needs_time && (
            <Field label="Time column" hint="Rows are ordered by this; the holdout is the most recent slice.">
              <Select value={timeColumn} onChange={(event) => setTimeColumn(event.target.value)}>
                <option value="">Select a date column…</option>
                {(understanding?.column_names ?? [])
                  .filter((name) => name !== target)
                  .map((name) => (
                    <option key={name} value={name}>{name}</option>
                  ))}
              </Select>
            </Field>
          )}

          {activeTask?.needs_group && (
            <Field label="Group column" hint="Identifies the query. Whole groups are held out together.">
              <Select value={groupColumn} onChange={(event) => setGroupColumn(event.target.value)}>
                <option value="">Select a group column…</option>
                {(understanding?.column_names ?? [])
                  .filter((name) => name !== target)
                  .map((name) => (
                    <option key={name} value={name}>{name}</option>
                  ))}
              </Select>
            </Field>
          )}

          <Field
            label="Sensitive attribute"
            hint="Optional. Enables the fairness audit."
          >
            <Select value={sensitive} onChange={(event) => setSensitive(event.target.value)}>
              <option value="">None</option>
              {(understanding?.column_names ?? [])
                .filter((name) => name !== target)
                .map((name) => (
                  <option key={name} value={name}>
                    {name}
                    {understanding?.sensitive_candidates.includes(name) ? "  (candidate)" : ""}
                  </option>
                ))}
            </Select>
          </Field>
        </div>

        <div className="mt-5 border-t pt-5">
          <Toggle
            checked={tune}
            onChange={setTune}
            label="Hyperparameter search on the winner"
            description="Adds a randomised search after the leaderboard is decided. Slower, usually worth it."
          />
        </div>

        {options.length > 0 && (
          <div className="mt-5 border-t pt-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <p className="text-[13px] font-semibold">Outputs to generate</p>
                <p className="mt-0.5 text-[12.5px] text-secondary">
                  The model is always trained. These are the documents written alongside it.
                </p>
              </div>
              <button
                type="button"
                className="text-[12.5px] text-muted underline-offset-2 hover:underline"
                onClick={() =>
                  setArtifacts(
                    selected.length === options.length ? [] : options.map((a) => a.key),
                  )
                }
              >
                {selected.length === options.length ? "Clear all" : "Select all"}
              </button>
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {options.map((option) => {
                const checked = selected.includes(option.key);
                return (
                  <label
                    key={option.key}
                    className={cn(
                      "flex cursor-pointer items-start gap-2.5 rounded-xl border p-3 transition-colors",
                      checked ? "border-[var(--brand)] bg-[var(--brand-subtle)]" : "hover:bg-black/[0.02] dark:hover:bg-white/[0.03]",
                    )}
                  >
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--brand)]"
                      checked={checked}
                      onChange={() => toggleArtifact(option.key)}
                    />
                    <span className="min-w-0">
                      <span className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[13px] font-medium">{option.label}</span>
                        <span className="text-[11px] text-muted">{option.formats.join(" ")}</span>
                      </span>
                      <span className="mt-0.5 block text-[12px] text-secondary">
                        {option.description}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>

            {selected.length === 0 && (
              <p className="mt-3 text-[12.5px] text-muted">
                Nothing selected — the run will train and register the model, then stop. You can
                generate documents later from a finished run.
              </p>
            )}
          </div>
        )}

        {error && (
          <p className="mt-4 text-[12.5px]" style={{ color: "var(--status-critical)" }}>
            {error}
          </p>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button
            onClick={startRun}
            loading={starting}
            disabled={
              (needsTarget && !target) ||
              (activeTask?.needs_time === true && !timeColumn) ||
              (activeTask?.needs_group === true && !groupColumn)
            }
            size="lg"
          >
            <IconSparkle className="h-4 w-4" />
            Run the pipeline
          </Button>
          <Button variant="ghost" onClick={() => inputRef.current?.click()}>
            Replace dataset
          </Button>
          {understanding && (
            <span className="text-[12.5px] text-muted">
              Estimated {formatDuration(understanding.estimated_seconds)}
            </span>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.tsv,.txt,.xlsx,.xls,.parquet,.json,.jsonl"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) upload(file);
            event.target.value = "";
          }}
        />
      </Card>

      {preview && (
        <>
          <Card>
            <CardHeader
              title="Columns"
              subtitle={`${preview.columns.length} columns · ${formatNumber(preview.total_rows)} rows`}
            />
            <div className="mt-4">
              <DataTable
                columns={[
                  { key: "name", header: "Column" },
                  { key: "dtype", header: "Type" },
                  {
                    key: "missing_pct",
                    header: "Missing",
                    align: "right",
                    render: (row) => `${Number(row.missing_pct).toFixed(2)}%`,
                  },
                  {
                    key: "unique",
                    header: "Unique",
                    align: "right",
                    render: (row) => formatNumber(Number(row.unique)),
                  },
                ]}
                rows={preview.columns as unknown as Record<string, unknown>[]}
              />
            </div>
          </Card>

          <Card>
            <CardHeader title="Preview" subtitle="First 25 rows, exactly as parsed." />
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-[12px] tnum">
                <thead>
                  <tr className="border-b">
                    {preview.columns.map((column) => (
                      <th key={column.name} className="whitespace-nowrap px-3 py-2 text-left font-semibold">
                        {column.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, index) => (
                    <tr key={index} className="border-b last:border-0">
                      {preview.columns.map((column) => (
                        <td
                          key={column.name}
                          className="max-w-[220px] truncate whitespace-nowrap px-3 py-1.5 text-secondary"
                        >
                          {row[column.name] === null || row[column.name] === undefined ? (
                            <span className="text-muted">null</span>
                          ) : (
                            String(row[column.name])
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function UnderstandingCard({ understanding }: { understanding: DatasetUnderstanding }) {
  return (
    <div className="space-y-5">
      <Card className="p-6">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-gradient">
            <IconSparkle className="h-4.5 w-4.5 text-white" style={{ width: 18, height: 18 }} />
          </span>
          <div className="min-w-0">
            <h3 className="text-[15px] font-semibold">What dataid read from your file</h3>
            <p className="mt-2 text-[13.5px] leading-relaxed text-secondary">
              I found <strong>{formatNumber(understanding.rows)} rows</strong> across{" "}
              <strong>{understanding.columns} columns</strong>. The problem looks like{" "}
              <strong>{understanding.problem_statement}</strong>, with{" "}
              <code className="rounded bg-black/[0.05] px-1.5 py-0.5 font-mono text-[12px] dark:bg-white/[0.07]">
                {understanding.suggested_target}
              </code>{" "}
              as the target — {understanding.target_reason} (confidence{" "}
              {understanding.target_confidence}).
            </p>
          </div>
        </div>

        {understanding.leakage_candidates.length > 0 && (
          <div
            className="mt-5 flex items-start gap-3 rounded-xl border p-4"
            style={{ borderColor: "var(--status-critical)" }}
          >
            <IconAlert
              className="mt-0.5 h-4 w-4 shrink-0"
              style={{ color: "var(--status-critical)" }}
            />
            <div>
              <p className="text-[13px] font-medium">Potential leakage</p>
              <p className="mt-1 text-[12.5px] text-secondary">
                {understanding.leakage_candidates
                  .map((name) => `\`${name}\``)
                  .join(", ")
                  .replace(/`/g, "")}{" "}
                — these look like they are recorded at or after the outcome. The Detective will
                confirm and drop them.
              </p>
            </div>
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          <span className="text-[12.5px] text-muted">Recommended models:</span>
          {understanding.recommended_models.map((model) => (
            <Badge key={model} tone="brand">
              {model}
            </Badge>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Rows" value={formatNumber(understanding.rows)} caption="after parsing" />
        <StatTile label="Columns" value={understanding.columns} caption="including the target" />
        <StatTile
          label="Missing cells"
          value={formatNumber(understanding.missing_cells)}
          caption="across the frame"
        />
        <StatTile
          label="Duplicate rows"
          value={formatNumber(understanding.duplicate_rows)}
          caption="will be removed"
        />
      </div>
    </div>
  );
}

function DropZone({
  dragging,
  uploading,
  onDragChange,
  onFile,
  inputRef,
}: {
  dragging: boolean;
  uploading: boolean;
  onDragChange: (value: boolean) => void;
  onFile: (file: File) => void;
  inputRef: React.RefObject<HTMLInputElement>;
}) {
  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        onDragChange(true);
      }}
      onDragLeave={() => onDragChange(false)}
      onDrop={(event) => {
        event.preventDefault();
        onDragChange(false);
        const file = event.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-20 text-center transition-all",
        dragging
          ? "border-brand-500 bg-brand-500/[0.06]"
          : "hover:border-brand-500/45 hover:bg-brand-500/[0.02]",
      )}
    >
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-gradient shadow-glow">
        <IconUpload className="h-6 w-6 text-white" />
      </span>
      <p className="mt-5 text-[16px] font-semibold">
        {uploading ? "Reading your file…" : "Drop a dataset here"}
      </p>
      <p className="mt-2 max-w-sm text-[13px] text-secondary">
        CSV, TSV, Excel, Parquet or JSON, up to 512 MB. dataid reads it and tells you what it thinks
        the problem is before anything runs.
      </p>
      <Button className="mt-6" loading={uploading} onClick={() => inputRef.current?.click()}>
        <IconDatabase className="h-4 w-4" />
        Choose a file
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.tsv,.txt,.xlsx,.xls,.parquet,.json,.jsonl"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.target.value = "";
        }}
      />
      <p className="mt-6 text-[12px] text-muted">
        Five sample datasets ship with the repo — see <code className="font-mono">sample_data/</code>
      </p>
    </div>
  );
}
