import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const INTEGER = new Intl.NumberFormat("en-US");

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (digits === 0) return INTEGER.format(Math.round(value));
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Metric-aware formatting: bounded scores get 4 decimals, magnitudes get thousands. */
export function formatMetric(name: string, value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const bounded = [
    "accuracy",
    "balanced_accuracy",
    "roc_auc",
    "pr_auc",
    "f1",
    "f1_macro",
    "precision",
    "recall",
    "r2",
    "mcc",
    "explained_variance",
    "cv_mean",
    "cv_std",
    "overfit_gap",
    "brier",
  ];
  if (bounded.includes(name)) return value.toFixed(4);
  if (name === "mape") return `${value.toFixed(2)}%`;
  if (Math.abs(value) >= 1000) return formatNumber(value, 0);
  return value.toFixed(4);
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value.toFixed(exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const deltaSeconds = Math.round((then - Date.now()) / 1000);
  const thresholds: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, "second"],
    [3600, "minute"],
    [86400, "hour"],
    [604800, "day"],
    [2629800, "week"],
    [31557600, "month"],
    [Infinity, "year"],
  ];
  const divisors = [1, 60, 3600, 86400, 604800, 2629800, 31557600];
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (let i = 0; i < thresholds.length; i += 1) {
    if (Math.abs(deltaSeconds) < thresholds[i][0]) {
      return formatter.format(Math.round(deltaSeconds / divisors[i]), thresholds[i][1]);
    }
  }
  return new Date(iso).toLocaleDateString();
}

export function formatClock(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "--:--";
  return date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

export function titleCase(text: string): string {
  return text
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase())
    .trim();
}

export function truncate(text: string, max = 42): string {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

/** Deterministic slot assignment — colour follows the entity, never its rank. */
export function seriesVar(index: number): string {
  return `var(--series-${(index % 8) + 1})`;
}

export function statusVar(level: "good" | "warning" | "serious" | "critical"): string {
  return `var(--status-${level})`;
}

export function severityTone(severity: string): "good" | "warning" | "serious" | "critical" {
  if (severity === "critical") return "critical";
  if (severity === "warning") return "warning";
  return "good";
}

export function driftTone(status: string): "good" | "warning" | "critical" {
  if (status === "critical") return "critical";
  if (status === "warning") return "warning";
  return "good";
}

export function download(url: string, filename: string) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}
