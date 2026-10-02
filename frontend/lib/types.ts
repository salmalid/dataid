export type TaskType =
  | "classification"
  | "regression"
  | "forecasting"
  | "clustering"
  | "anomaly"
  | "ranking";

export type TaskFamily = "supervised" | "unsupervised" | "temporal" | "ranking";

/** One selectable task. Served by /api/agents so the UI cannot offer what the pipeline lacks. */
export interface TaskOption {
  key: TaskType;
  label: string;
  description: string;
  needs_target: boolean;
  needs_time: boolean;
  needs_group: boolean;
  example: string;
}
export type RunStatus = "queued" | "running" | "success" | "failed";
export type Severity = "critical" | "warning" | "info";

/** One selectable output format. Served by /api/agents so the UI and pipeline cannot drift. */
export interface ArtifactOption {
  key: string;
  label: string;
  description: string;
  formats: string[];
}

export interface Project {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  dataset_path: string | null;
  dataset_name: string | null;
  target_column: string | null;
  sensitive_column: string | null;
  task_type: TaskType | null;
  rows: number;
  columns: number;
  status: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  run_count?: number;
  best_model?: string | null;
  best_metric?: number | null;
  best_metric_name?: string | null;
}

export interface Issue {
  severity: Severity;
  category: string;
  column: string | null;
  message: string;
  stat: number | null;
}

export interface TimelineEvent {
  run_id: string;
  agent: string;
  step: string;
  status: "queued" | "running" | "success" | "failed" | "skipped";
  message: string;
  progress: number;
  detail: Record<string, unknown>;
  timestamp: string;
}

export interface LeaderboardRow {
  rank: number;
  key: string;
  model: string;
  family: string;
  fit_seconds: number;
  inference_ms_per_row: number;
  cv_mean: number | null;
  cv_std: number | null;
  overfit_gap: number;
  [metric: string]: string | number | null;
}

export interface RunSummary {
  id: string;
  project_id: string;
  version: number;
  status: RunStatus;
  target_column: string;
  best_model: string | null;
  primary_metric: string | null;
  primary_value: number | null;
  duration_seconds: number | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface RunResult {
  run_id: string;
  status: string;
  task_type: TaskType;
  target_column: string;
  rows: number;
  columns: number;
  duration_seconds: number;
  issues: Issue[];
  profile: DatasetProfile;
  eda: Eda;
  research: Research;
  fairness: Fairness;
  monitoring: Monitoring;
  cleaning_summary: CleaningSummary;
  feature_summary: FeatureSummary;
  best_model: string;
  metrics: Metrics;
  leaderboard: LeaderboardRow[];
  explainability: Explainability;
  deployment: Deployment;
  artifacts: Record<string, string>;
  logs: { agent: string; message: string; timestamp: string }[];
}

export interface DatasetProfile {
  rows: number;
  memory_bytes: number;
  duplicate_rows: number;
  total_missing_cells: number;
  column_groups: Record<string, string[]>;
  /** Per-column detail. The scalar column *count* lives on RunResult.columns. */
  columns: ColumnProfile[];
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  role: string;
  missing: number;
  missing_pct: number;
  unique: number;
  is_target: boolean;
  min?: number;
  max?: number;
  mean?: number;
  std?: number;
  median?: number;
  skew?: number;
  histogram?: { bins: number[]; counts: number[] };
  top_values?: { value: string; count: number }[];
}

export interface Eda {
  correlation_matrix: { columns: string[]; values: number[][] };
  missing_by_column: { column: string; pct: number }[];
  class_balance?: { label: string; count: number; pct: number }[];
  target_correlation?: { feature: string; corr: number }[];
  collinear_pairs?: { a: string; b: string; corr: number }[];
  leakage_suspects?: { column: string; reasons: string[] }[];
  numeric_distributions?: { column: string; bins: number[]; counts: number[] }[];
  outliers?: { per_column_pct: Record<string, number>; multivariate_pct: number };
  sample_rows?: Record<string, unknown>[];
  target_summary?: Record<string, number>;
}

export interface Research {
  task_type: TaskType;
  primary_metric: string;
  validation: { scheme: string; folds: number; holdout_pct: number };
  imbalance_ratio: number | null;
  strategy: string[];
  n_train_rows: number;
  n_features: number;
  library_availability: Record<string, boolean>;
  shortlist: { key: string; label: string; family: string; notes: string }[];
  narrative: string;
  tuning?: { best_params: Record<string, string>; best_cv_score: number };
}

export interface CleaningSummary {
  shape_before: number[];
  shape_after: number[];
  rows_removed: number;
  columns_removed: number;
  dropped_columns: string[];
  actions: { action: string; detail: string }[];
  remaining_missing: number;
}

export interface FeatureSummary {
  created_features: string[];
  n_created: number;
  n_features_out: number;
  feature_names: string[];
  train_rows: number;
  test_rows: number;
  column_groups: Record<string, string[]>;
}

export interface Metrics {
  accuracy?: number;
  balanced_accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  f1_macro?: number;
  mcc?: number;
  roc_auc?: number;
  pr_auc?: number;
  log_loss?: number;
  brier?: number;
  r2?: number;
  mae?: number;
  mse?: number;
  rmse?: number;
  mape?: number;
  explained_variance?: number;
  holdout_rows?: number;
  n_classes?: number;
  labels?: string[];
  positive_label?: string;
  confusion_matrix?: number[][];
  per_class?: { label: string; precision: number; recall: number; f1: number; support: number }[];
  roc_curve?: { fpr: number; tpr: number }[];
  pr_curve?: { recall: number; precision: number }[];
  calibration?: { predicted: number; observed: number; count: number }[];
  threshold_f1?: ThresholdPoint;
  threshold_recall?: ThresholdPoint;
  predicted_vs_actual?: { actual: number; predicted: number }[];
  residual_histogram?: { bins: number[]; counts: number[] };
}

export interface ThresholdPoint {
  threshold: number;
  score: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface Explainability {
  method: string;
  global_importance: { feature: string; importance: number; source: string; std?: number }[];
  shap: {
    available: boolean;
    method: string;
    reason?: string;
    sample_size?: number;
    top_features?: { feature: string; mean_abs_shap: number }[];
    beeswarm?: { feature: string; values: number[] }[];
  };
  local_explanations: LocalExplanation[];
  counterfactuals: {
    index: number;
    original_prediction: string;
    note: string;
    counterfactual: {
      feature: string;
      shift_in_std: number;
      from_prediction: string;
      to_prediction: string;
    } | null;
  }[];
  partial_dependence: { feature: string; points: { x: number; y: number }[] }[];
  business_summary: string;
}

export interface LocalExplanation {
  index: number;
  prediction: string | number;
  actual: string | number;
  confidence: number | null;
  contributions: { feature: string; contribution: number; direction: string }[];
}

export interface Fairness {
  enabled: boolean;
  reason?: string;
  column?: string;
  metric?: string;
  max_gap?: number;
  verdict?: "pass" | "review" | "fail";
  slices?: Record<string, string | number | null>[];
}

export interface Deployment {
  model_path: string;
  schema_path: string;
  artifacts_dir: string;
  image_name: string;
  endpoints: { method: string; path: string; description: string }[];
  targets: string[];
  latency: {
    p50_ms_per_row?: number;
    p95_ms_per_row?: number;
    throughput_rows_per_sec?: number;
  };
  model_size_bytes: number;
  run_command: string;
  docker_command: string;
}

export interface Monitoring {
  reference: {
    numeric: {
      column: string;
      mean: number;
      std: number;
      p05: number;
      p50: number;
      p95: number;
      null_rate: number;
    }[];
    categorical: { column: string; distribution: Record<string, number> }[];
    captured_rows: number;
  };
  drift: {
    features: { feature: string; psi: number; status: string }[];
    max_psi: number;
    status: string;
    note?: string;
  };
  baseline: { metric: string; value: number; captured_rows: number };
  alerts: { id: string; signal: string; warn: number; critical: number; action: string }[];
  schedule: Record<string, string>;
}

export interface DatasetUnderstanding {
  rows: number;
  columns: number;
  memory_bytes: number;
  column_names: string[];
  column_groups: Record<string, string[]>;
  suggested_target: string | null;
  target_confidence: number;
  target_reason: string;
  inferred_task: TaskType | null;
  problem_statement: string;
  leakage_candidates: string[];
  sensitive_candidates: string[];
  recommended_models: string[];
  missing_cells: number;
  duplicate_rows: number;
  estimated_seconds: number;
  preview: Record<string, unknown>[];
}

export interface ChatMessage {
  id: string;
  project_id: string;
  role: "user" | "assistant";
  content: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface AgentInfo {
  name: string;
  label: string;
  description: string;
  critical: boolean;
}

export interface RegistryEntry {
  id: string;
  project_id: string;
  run_id: string;
  name: string;
  version: number;
  stage: "staging" | "production" | "archived";
  metric_name: string;
  metric_value: number;
  model_path: string;
  created_at: string;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  last_used_at: string | null;
  revoked: number;
  created_at: string;
  token?: string;
}

export interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface WorkspaceStats {
  projects: number;
  runs: number;
  successful_runs: number;
  models: number;
  models_in_production: number;
  predictions: number;
  avg_run_seconds: number;
  success_rate: number;
  active_runs: { run_id: string; project_id: string; project_name: string; status: string }[];
}
