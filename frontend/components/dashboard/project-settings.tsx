"use client";

import { useState } from "react";
import { Button, Card, CardHeader, Field, Input, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { formatBytes, formatNumber, formatRelativeTime } from "@/lib/utils";

export function ProjectSettingsPanel({
  project,
  onChange,
  onDeleted,
}: {
  project: Project;
  onChange: (project: Project) => void;
  onDeleted: () => void;
}) {
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateProject(project.id, {
        name: name.trim(),
        description: description.trim(),
      });
      onChange(updated);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2200);
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    try {
      await api.deleteProject(project.id);
      onDeleted();
    } catch (exception) {
      setError((exception as Error).message);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <Card>
        <CardHeader title="Project details" />
        <form onSubmit={save} className="space-y-4 p-5">
          <Field label="Name">
            <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} />
          </Field>
          <Field label="Description">
            <Textarea
              rows={3}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>
          {error && (
            <p className="text-[12.5px]" style={{ color: "var(--status-critical)" }}>
              {error}
            </p>
          )}
          <div className="flex items-center gap-3">
            <Button type="submit" loading={saving} disabled={!name.trim()}>
              Save changes
            </Button>
            {saved && (
              <span className="text-[12.5px]" style={{ color: "var(--success-text)" }}>
                Saved
              </span>
            )}
          </div>
        </form>
      </Card>

      <Card>
        <CardHeader title="Dataset" />
        <dl className="divide-y px-5 pb-5">
          {[
            ["File", project.dataset_name ?? "none"],
            ["Rows", project.rows ? formatNumber(project.rows) : "—"],
            ["Columns", project.columns || "—"],
            ["Target", project.target_column ?? "not selected"],
            ["Sensitive attribute", project.sensitive_column ?? "none"],
            ["Task type", project.task_type ?? "not inferred"],
            ["Created", formatRelativeTime(project.created_at)],
            ["Last updated", formatRelativeTime(project.updated_at)],
          ].map(([label, value]) => (
            <div key={String(label)} className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-[13px] text-secondary">{label}</dt>
              <dd className="text-[13px] font-medium">{String(value)}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card style={{ borderColor: "var(--status-critical)" }}>
        <CardHeader
          title="Danger zone"
          subtitle="Deleting a project removes its runs, chat history and registry entries."
        />
        <div className="p-5">
          {confirming ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-[13px] text-secondary">
                Delete <strong>{project.name}</strong> permanently?
              </span>
              <Button variant="danger" size="sm" onClick={remove}>
                Yes, delete it
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button variant="danger" size="sm" onClick={() => setConfirming(true)}>
              Delete project
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
