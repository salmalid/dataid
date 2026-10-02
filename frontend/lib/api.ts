import type {
  AgentInfo,
  ApiKey,
  ArtifactOption,
  AuditEntry,
  ChatMessage,
  DatasetUnderstanding,
  Project,
  RegistryEntry,
  RunResult,
  RunSummary,
  TaskOption,
  TimelineEvent,
  WorkspaceStats,
} from "./types";

/** Same-origin: next.config.mjs rewrites /api/* to the FastAPI backend. */
const BASE = "";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Status 0 means the request never reached the backend — down, restarting, or no network. */
export const OFFLINE = 0;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function attempt<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    // fetch rejects with a bare TypeError("Failed to fetch") on a dropped connection.
    // Normalise it so callers only ever have to handle ApiError.
    throw new ApiError("Cannot reach the API — is the backend running?", OFFLINE);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // A GET that fails to connect is almost always the dev server bouncing; retry briefly
  // rather than surfacing a transient blip as a hard failure. Writes are never retried —
  // the request may have been applied server-side already.
  const retryable = !init?.method || init.method.toUpperCase() === "GET";
  const attempts = retryable ? 3 : 1;

  for (let i = 0; i < attempts; i += 1) {
    try {
      return await attempt<T>(path, init);
    } catch (exception) {
      const offline = exception instanceof ApiError && exception.status === OFFLINE;
      if (!offline || i === attempts - 1) throw exception;
      await sleep(400 * (i + 1));
    }
  }

  throw new ApiError("Cannot reach the API — is the backend running?", OFFLINE);
}

export const api = {
  health: () =>
    request<{
      status: string;
      llm_provider: string;
      boosting_libraries: Record<string, boolean>;
      active_runs: number;
    }>("/api/health"),

  agents: () =>
    request<{
      agents: AgentInfo[];
      commands: { key: string; label: string; agents: string[]; steps: string[] }[];
      artifacts: ArtifactOption[];
      tasks: TaskOption[];
    }>("/api/agents"),

  stats: () => request<WorkspaceStats>("/api/stats"),

  // ---------------------------------------------------------------- projects
  listProjects: () => request<{ projects: Project[] }>("/api/projects"),

  createProject: (body: { name: string; description?: string; tags?: string[] }) =>
    request<Project>("/api/projects", { method: "POST", body: JSON.stringify(body) }),

  getProject: (id: string) =>
    request<{
      project: Project;
      runs: RunSummary[];
      latest_result: RunResult | null;
      registry: RegistryEntry[];
    }>(`/api/projects/${id}`),

  updateProject: (id: string, body: Partial<Project>) =>
    request<Project>(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),

  deleteProject: (id: string) => request<void>(`/api/projects/${id}`, { method: "DELETE" }),

  // ---------------------------------------------------------------- dataset
  uploadDataset: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{
      project: Project;
      understanding: DatasetUnderstanding;
      size_bytes: number;
    }>(`/api/projects/${id}/dataset`, { method: "POST", body: form });
  },

  previewDataset: (id: string, limit = 50) =>
    request<{
      columns: { name: string; dtype: string; missing_pct: number; unique: number }[];
      rows: Record<string, unknown>[];
      total_rows: number;
    }>(`/api/projects/${id}/dataset/preview?limit=${limit}`),

  understanding: (id: string) =>
    request<DatasetUnderstanding>(`/api/projects/${id}/understanding`),

  // ---------------------------------------------------------------- runs
  startRun: (
    id: string,
    body: {
      target_column?: string;
      sensitive_column?: string | null;
      tune?: boolean;
      artifacts?: string[];
      task_type?: string;
      time_column?: string | null;
      group_column?: string | null;
    },
  ) =>
    request<{ run: RunSummary; stream_url: string }>(`/api/projects/${id}/runs`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listRuns: (id: string) => request<{ runs: RunSummary[] }>(`/api/projects/${id}/runs`),

  getRun: (runId: string) =>
    request<{
      run: RunSummary & { result?: RunResult };
      timeline: TimelineEvent[];
      active: boolean;
    }>(`/api/runs/${runId}`),

  runTimeline: (runId: string) =>
    request<{ events: TimelineEvent[] }>(`/api/runs/${runId}/timeline`),

  runArtifacts: (runId: string) =>
    request<{
      artifacts: { key: string; name: string; size_bytes: number; download_url: string }[];
    }>(`/api/runs/${runId}/artifacts`),

  compareRuns: (a: string, b: string) =>
    request<{
      left: { run_id: string; version: number; model: string };
      right: { run_id: string; version: number; model: string };
      deltas: {
        metric: string;
        left: number;
        right: number;
        delta: number;
        pct_change: number | null;
      }[];
    }>(`/api/runs/${a}/compare/${b}`),

  /** Live timeline over server-sent events. Returns an unsubscribe function. */
  streamRun: (
    runId: string,
    onEvent: (event: TimelineEvent) => void,
    onError?: () => void,
  ): (() => void) => {
    const source = new EventSource(`/api/runs/${runId}/stream`);
    source.onmessage = (message) => {
      try {
        const parsed = JSON.parse(message.data);
        if (parsed.type === "heartbeat") return;
        onEvent(parsed as TimelineEvent);
        if (parsed.step === "pipeline" && ["success", "failed"].includes(parsed.status)) {
          source.close();
        }
      } catch {
        /* ignore malformed frames */
      }
    };
    source.onerror = () => {
      source.close();
      onError?.();
    };
    return () => source.close();
  },

  // ---------------------------------------------------------------- chat
  getChat: (id: string) => request<{ messages: ChatMessage[] }>(`/api/projects/${id}/chat`),

  postChat: (id: string, message: string, autoExecute = true) =>
    request<{
      message: ChatMessage;
      response: {
        intent: string;
        label: string;
        action: string;
        agents: string[];
        steps: string[];
        reply: string;
        detail: string;
        params: Record<string, unknown>;
      };
      executed: { type: string; run_id?: string; [k: string]: unknown } | null;
    }>(`/api/projects/${id}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, auto_execute: autoExecute }),
    }),

  // ---------------------------------------------------------------- inference
  predict: (id: string, record: Record<string, unknown>) =>
    request<{
      prediction: unknown;
      probabilities?: Record<string, number>;
      confidence?: number;
      latency_ms: number;
    }>(`/api/projects/${id}/predict`, { method: "POST", body: JSON.stringify({ record }) }),

  predictions: (id: string) =>
    request<{
      predictions: {
        id: string;
        payload: Record<string, unknown>;
        prediction: string;
        confidence: number | null;
        latency_ms: number;
        created_at: string;
      }[];
    }>(`/api/projects/${id}/predictions`),

  // ---------------------------------------------------------------- ops
  monitoring: (id: string) =>
    request<{
      monitoring: RunResult["monitoring"];
      baseline: { metric: string; value: number };
      prediction_count: number;
      recent_predictions: unknown[];
      latency: Record<string, number>;
    }>(`/api/projects/${id}/monitoring`),

  registry: (projectId?: string) =>
    request<{ models: RegistryEntry[] }>(
      `/api/registry${projectId ? `?project_id=${projectId}` : ""}`,
    ),

  promote: (modelId: string, stage: "staging" | "production" | "archived") =>
    request<RegistryEntry>(`/api/registry/${modelId}/promote`, {
      method: "POST",
      body: JSON.stringify({ stage }),
    }),

  listKeys: () => request<{ keys: ApiKey[] }>("/api/keys"),

  createKey: (name: string, scopes: string[] = ["read", "write"]) =>
    request<ApiKey>("/api/keys", { method: "POST", body: JSON.stringify({ name, scopes }) }),

  revokeKey: (id: string) => request<void>(`/api/keys/${id}`, { method: "DELETE" }),

  audit: (limit = 100) => request<{ entries: AuditEntry[] }>(`/api/audit?limit=${limit}`),
};
