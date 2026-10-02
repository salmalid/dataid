"""ML Researcher — picks the task framing, the primary metric and the candidate shortlist."""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..core.context import (
    PRIMARY_METRIC,
    ProjectContext,
    TaskFamily,
    TaskType,
    family_of,
)
from ..core.llm import narrate
from . import model_zoo
from .base import Agent


class MLResearcherAgent(Agent):
    name = "ml_researcher"
    label = "ML Researcher"
    description = "Chooses the objective, the primary metric, the validation scheme and the model shortlist."

    def run(self, ctx: ProjectContext) -> None:
        self.progress(ctx, "Framing the problem", 0.2)
        n_rows, n_features = ctx.X_train.shape
        imbalance = self._imbalance(ctx)

        primary_metric = self._primary_metric(ctx, imbalance)
        strategy = self._strategy(ctx, n_rows, n_features, imbalance)

        self.progress(ctx, "Shortlisting candidate models", 0.6)
        candidates = model_zoo.candidates_for(ctx.task_type.value, n_rows)
        shortlist = self._shortlist(candidates, n_rows, n_features)

        ctx.research = {
            "task_type": ctx.task_type.value,
            "task_family": family_of(ctx.task_type).value,
            "primary_metric": primary_metric,
            "validation": {"scheme": self._validation_scheme(ctx), "folds": 3, "holdout_pct": 20},
            "imbalance_ratio": imbalance,
            "strategy": strategy,
            "n_train_rows": int(n_rows),
            "n_features": int(n_features),
            "library_availability": model_zoo.availability(),
            "shortlist": [
                {"key": c.key, "label": c.label, "family": c.family, "notes": c.notes}
                for c in shortlist
            ],
            "narrative": narrate(
                f"Frame a {ctx.task_type.value} problem on {n_rows} rows and {n_features} features "
                f"with imbalance ratio {imbalance}. Mention imbalance handling if relevant."
            ),
        }
        ctx.log(self.name, f"primary metric = {primary_metric}, {len(shortlist)} candidates queued")

    # ------------------------------------------------------------------
    def _validation_scheme(self, ctx: ProjectContext) -> str:
        return {
            TaskType.CLASSIFICATION: "stratified k-fold",
            TaskType.REGRESSION: "k-fold",
            TaskType.FORECASTING: "rolling-origin (time series split)",
            TaskType.RANKING: "grouped k-fold by query",
            TaskType.CLUSTERING: "holdout silhouette",
            TaskType.ANOMALY: "holdout score separation",
        }.get(ctx.task_type, "k-fold")

    def _imbalance(self, ctx: ProjectContext) -> float | None:
        if ctx.task_type != TaskType.CLASSIFICATION or ctx.y_train is None:
            return None
        counts = pd.Series(ctx.y_train).value_counts()
        if len(counts) < 2:
            return 1.0
        return round(float(counts.min() / counts.max()), 4)

    def _primary_metric(self, ctx: ProjectContext, imbalance: float | None) -> str:
        if ctx.task_type != TaskType.CLASSIFICATION:
            return PRIMARY_METRIC.get(ctx.task_type, "r2")
        n_classes = len(np.unique(ctx.y_train))
        if n_classes > 2:
            return "f1_macro"
        if imbalance is not None and imbalance < 0.2:
            return "pr_auc"
        return "roc_auc"

    def _strategy(self, ctx: ProjectContext, n_rows: int, n_features: int,
                  imbalance: float | None) -> List[str]:
        notes: List[str] = []
        family = family_of(ctx.task_type)

        if ctx.task_type == TaskType.CLUSTERING:
            notes.append("No target exists, so the leaderboard sweeps the cluster count and ranks "
                         "by holdout silhouette — choosing k is the experiment, not a prerequisite.")
            notes.append("Density methods (DBSCAN, Mean Shift) can label points as noise; a high "
                         "noise share usually means the data has no natural partition.")
            return notes
        if ctx.task_type == TaskType.ANOMALY:
            notes.append("Contamination is swept rather than assumed — the true outlier rate is "
                         "exactly the unknown, so the leaderboard picks the setting whose flagged "
                         "population separates most cleanly from the rest.")
            if ctx.y_test is not None:
                notes.append("A label column was supplied, so precision and recall against it are "
                             "reported alongside the unsupervised separation score.")
            return notes
        if family is TaskFamily.TEMPORAL:
            notes.append("Rows are ordered by time and the holdout is the most recent slice — a "
                         "shuffled split would train on the future and inflate every metric.")
            notes.append("Cross-validation is rolling-origin, so each fold trains only on data "
                         "that preceded the fold it scores.")
            notes.append("MASE against the naive forecast is the bar that matters: below 1.0 means "
                         "the model beats simply repeating the last observation.")
            return notes
        if family is TaskFamily.RANKING:
            notes.append("Whole query groups are held out together — splitting rows would let the "
                         "model memorise a query's ordering from its own training items.")
            notes.append("NDCG is averaged per query rather than pooled, so easy queries cannot "
                         "mask poor ordering on hard ones.")
            return notes

        if imbalance is not None and imbalance < 0.35:
            notes.append("Enable class weighting on every estimator that supports it; tune the decision "
                         "threshold after training instead of resampling first.")
        if n_features > n_rows / 10:
            notes.append("Feature count is high relative to sample size — favour regularised linear models "
                         "and shallow boosting to avoid variance blow-up.")
        if n_rows < 1000:
            notes.append("Small sample: cross-validated scores carry more weight than the single holdout.")
        if n_rows > 100_000:
            notes.append("Large sample: histogram-based boosting dominates on training time per point of lift.")
        if any(i.category == "leakage" for i in ctx.issues):
            notes.append("Leakage suspects were removed before training; metrics below are leakage-adjusted.")
        if not notes:
            notes.append("Standard tabular setup — the full model portfolio is viable, ranked by holdout metric.")
        return notes

    def _shortlist(self, candidates: List[Any], n_rows: int, n_features: int) -> List[Any]:
        skip: set[str] = set()
        if n_rows > 30_000:
            skip |= {"svm_rbf", "svr", "knn", "knn_regressor", "gradient_boosting",
                     "gradient_boosting_regressor"}
        if n_rows > 150_000:
            skip |= {"mlp", "mlp_regressor", "extra_trees", "extra_trees_regressor"}
        if n_features > 500:
            skip |= {"knn", "knn_regressor", "svm_rbf", "svr"}
        return [c for c in candidates if c.key not in skip]
