"""Monitoring — establishes the production baseline and the drift/alerting contract."""
from __future__ import annotations

import json
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..core import config
from ..core.context import ProjectContext, TaskType, LOWER_IS_BETTER
from ..core.utils import coerce_json, psi, psi_reference
from .base import Agent


class MonitoringAgent(Agent):
    name = "monitoring"
    label = "Monitoring Agent"
    description = "Captures the training reference distribution and defines drift and performance alerts."
    critical = False

    def run(self, ctx: ProjectContext) -> None:
        self.progress(ctx, "Capturing the reference distribution", 0.3)
        reference = self._reference(ctx)

        self.progress(ctx, "Simulating drift against the holdout", 0.6)
        drift = self._drift_report(ctx, reference)

        self.progress(ctx, "Defining alert rules", 0.85)
        primary = ctx.research.get("primary_metric", "roc_auc")
        baseline = float(ctx.metrics.get(primary, ctx.metrics.get("accuracy", ctx.metrics.get("r2", 0.0))))
        direction = 1 if primary in LOWER_IS_BETTER else -1
        delta = max(abs(baseline), 1e-6)
        # y_test is None on an unlabelled clustering or anomaly run; the holdout still exists.
        captured = len(ctx.y_test) if ctx.y_test is not None else int(ctx.metrics.get(
            "holdout_rows", len(ctx.X_test) if ctx.X_test is not None else 0))

        ctx.monitoring = {
            "reference": reference,
            "drift": drift,
            "baseline": {"metric": primary, "value": round(baseline, 5),
                         "captured_rows": int(captured)},
            "alerts": [
                {"id": "psi_drift", "signal": "feature PSI",
                 "warn": config.DRIFT_PSI_WARN, "critical": config.DRIFT_PSI_ALERT,
                 "action": "Retrain on the most recent window."},
                {"id": "metric_decay", "signal": primary,
                 "warn": round(baseline + direction * delta * 0.05, 5),
                 "critical": round(baseline + direction * delta * 0.10, 5),
                 "comparison": "above" if direction == 1 else "below",
                 "action": "Roll back to the previous registry version and investigate."},
                {"id": "latency_p95", "signal": "p95 latency (ms)", "warn": 250, "critical": 750,
                 "action": "Scale replicas or switch to a lighter model in the registry."},
                {"id": "null_rate", "signal": "request null rate", "warn": 0.05, "critical": 0.2,
                 "action": "Inspect the upstream feature pipeline."},
                {"id": "prediction_shift", "signal": "mean prediction delta",
                 "warn": 0.1, "critical": 0.25, "action": "Check for concept drift in the label definition."},
            ],
            "schedule": {"drift_check": "hourly", "performance_check": "daily",
                         "retrain_review": "weekly"},
        }

        path = ctx.artifacts_dir / "monitoring_reference.json"
        path.write_text(json.dumps(coerce_json(ctx.monitoring), indent=2), encoding="utf-8")
        ctx.register_artifact("monitoring_reference", path)

    # ------------------------------------------------------------------
    def _reference(self, ctx: ProjectContext) -> Dict[str, Any]:
        source = ctx.df.iloc[ctx.train_indices].drop(columns=[ctx.target_column], errors="ignore")
        numeric = source.select_dtypes(include=[np.number])
        stats: List[Dict[str, Any]] = []
        for col in numeric.columns[:40]:
            s = numeric[col].dropna()
            if s.empty:
                continue
            stats.append({
                "column": str(col),
                "mean": round(float(s.mean()), 5),
                "std": round(float(s.std()), 5),
                "p05": round(float(s.quantile(0.05)), 5),
                "p50": round(float(s.median()), 5),
                "p95": round(float(s.quantile(0.95)), 5),
                "null_rate": round(float(numeric[col].isna().mean()), 5),
                # the real binned distribution, so live drift scores against observed data
                # rather than a normal curve reconstructed from mean and std
                "bins": psi_reference(s.to_numpy(dtype=float)),
            })
        categorical: List[Dict[str, Any]] = []
        for col in source.select_dtypes(include=["object", "category"]).columns[:20]:
            share = source[col].astype(str).value_counts(normalize=True).head(10)
            categorical.append({"column": str(col),
                                "distribution": {str(k): round(float(v), 5) for k, v in share.items()}})
        return {"numeric": stats, "categorical": categorical,
                "captured_rows": int(len(source))}

    def _drift_report(self, ctx: ProjectContext, reference: Dict[str, Any]) -> Dict[str, Any]:
        """PSI of the holdout against the training split — the zero-drift sanity baseline."""
        if ctx.raw_X_test is None:
            return {"features": [], "max_psi": 0.0, "status": "unknown"}

        train_source = ctx.df.iloc[ctx.train_indices].drop(columns=[ctx.target_column], errors="ignore")
        rows: List[Dict[str, Any]] = []
        for entry in reference["numeric"]:
            col = entry["column"]
            if col not in ctx.raw_X_test.columns:
                continue
            value = psi(train_source[col].to_numpy(dtype=float, na_value=np.nan),
                        ctx.raw_X_test[col].to_numpy(dtype=float, na_value=np.nan))
            status = ("critical" if value >= config.DRIFT_PSI_ALERT
                      else "warning" if value >= config.DRIFT_PSI_WARN else "stable")
            rows.append({"feature": col, "psi": round(value, 5), "status": status})

        rows.sort(key=lambda r: r["psi"], reverse=True)
        max_psi = rows[0]["psi"] if rows else 0.0
        return {
            "features": rows[:25],
            "max_psi": max_psi,
            "status": ("critical" if max_psi >= config.DRIFT_PSI_ALERT
                       else "warning" if max_psi >= config.DRIFT_PSI_WARN else "stable"),
            "note": "Holdout vs training reference. In production this same PSI runs against live traffic.",
        }
