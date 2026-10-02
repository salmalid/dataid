"""Experiment Manager — trains the whole shortlist, ranks it, tunes the winner."""
from __future__ import annotations

import time
import warnings
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, RandomizedSearchCV, StratifiedKFold, cross_val_score

from ..core import config
from ..core.context import (
    LOWER_IS_BETTER,
    ProjectContext,
    TaskFamily,
    TaskType,
    family_of,
)
from ..core.metrics import (
    best_threshold,
    calibration_points,
    classification_metrics,
    fairness_slices,
    pr_curve_points,
    regression_metrics,
    roc_curve_points,
)
from ..core.unsupervised_metrics import (
    anomaly_metrics,
    cluster_profiles,
    clustering_metrics,
    forecast_metrics,
    ranking_metrics,
)
from . import model_zoo
from .base import Agent

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


class ExperimentManagerAgent(Agent):
    name = "experiment_manager"
    label = "Experiment Manager"
    description = "Trains every shortlisted model, cross-validates, ranks the leaderboard and tunes the winner."

    def run(self, ctx: ProjectContext) -> None:
        n_rows = int(ctx.X_train.shape[0])
        pool = model_zoo.candidates_for(ctx.task_type.value, n_rows)
        shortlist_keys = [c["key"] for c in ctx.research.get("shortlist", [])]
        candidates = [c for c in pool if c.key in shortlist_keys] or pool
        primary = ctx.research.get("primary_metric", "roc_auc")
        imbalanced = (ctx.research.get("imbalance_ratio") or 1.0) < 0.35
        unsupervised = family_of(ctx.task_type) is TaskFamily.UNSUPERVISED

        rows: List[Dict[str, Any]] = []
        trained: Dict[str, Any] = {}
        total = len(candidates)

        for i, candidate in enumerate(candidates, start=1):
            self.progress(ctx, f"Training {candidate.label} ({i}/{total})", i / (total + 2),
                          model=candidate.label)
            result = (self._train_unsupervised(ctx, candidate) if unsupervised
                      else self._train_one(ctx, candidate, imbalanced))
            if result is None:
                continue
            model, row = result
            trained[candidate.key] = model
            rows.append(row)

        if not rows:
            raise RuntimeError("Every candidate model failed to train.")

        leaderboard = pd.DataFrame(rows)
        ascending = primary in LOWER_IS_BETTER
        if primary not in leaderboard.columns:
            # Falling back to "whatever column happens to sit at index 2" silently ranked
            # ranking runs by alphabetical family name and crowned the wrong model. A missing
            # primary metric is a bug in the scoring path, so say so instead of guessing.
            raise RuntimeError(
                f"primary metric '{primary}' is missing from the leaderboard; "
                f"scored columns are {sorted(leaderboard.columns)}"
            )
        leaderboard = leaderboard.sort_values(primary, ascending=ascending).reset_index(drop=True)
        leaderboard.insert(0, "rank", leaderboard.index + 1)

        best_key = leaderboard.iloc[0]["key"]
        best_model = trained[best_key]
        ctx.best_model_name = str(leaderboard.iloc[0]["model"])

        if ctx.tune:
            best_candidate = next(c for c in candidates if c.key == best_key)
            if best_candidate.param_grid:
                self.progress(ctx, f"Tuning {best_candidate.label}", 0.92)
                best_model = self._tune(ctx, best_candidate, best_model)

        ctx.best_model = best_model
        ctx.leaderboard = leaderboard

        self.progress(ctx, "Scoring the winner on the holdout set", 0.97)
        ctx.metrics = self._final_metrics(ctx, best_model)
        self._fairness(ctx, best_model)

    # ------------------------------------------------------------------ unsupervised
    def _train_unsupervised(self, ctx: ProjectContext, candidate):
        """Fit, then score by how well the structure holds on rows the model never saw.

        Not every estimator here can generalise: DBSCAN, Agglomerative and MeanShift have no
        `predict`, so they are fit on the holdout directly. That is the honest thing to do —
        those algorithms genuinely cannot assign a new point without refitting.
        """
        try:
            model = candidate.builder()
        except TypeError:
            return None

        started = time.perf_counter()
        try:
            labels_test = self._fit_and_label(ctx, model)
        except Exception as exc:  # noqa: BLE001
            ctx.log(self.name, f"{candidate.label} failed: {exc}")
            return None
        if labels_test is None:
            return None
        fit_seconds = time.perf_counter() - started

        row: Dict[str, Any] = {
            "key": candidate.key,
            "model": candidate.label,
            "family": candidate.family,
            "fit_seconds": round(fit_seconds, 3),
        }

        if ctx.task_type == TaskType.CLUSTERING:
            scores = clustering_metrics(ctx.X_test, labels_test)
            row.update({k: v for k, v in scores.items()
                        if isinstance(v, (int, float)) or v is None})
        else:
            raw = self._anomaly_scores(model, ctx.X_test)
            scores = anomaly_metrics(raw, labels_test, ctx.y_test)
            row.update({k: v for k, v in scores.items() if isinstance(v, (int, float))})
            if scores.get("labelled_evaluation"):
                row["labelled_f1"] = scores["labelled_evaluation"]["f1"]
        return model, row

    def _fit_and_label(self, ctx: ProjectContext, model) -> Optional[np.ndarray]:
        if hasattr(model, "fit_predict") and not hasattr(model, "predict"):
            return np.asarray(model.fit_predict(ctx.X_test))
        model.fit(ctx.X_train)
        if hasattr(model, "predict"):
            return np.asarray(model.predict(ctx.X_test))
        if hasattr(model, "labels_"):
            return np.asarray(model.fit_predict(ctx.X_test))
        return None

    def _anomaly_scores(self, model, X) -> np.ndarray:
        for attr in ("score_samples", "decision_function"):
            if hasattr(model, attr):
                try:
                    return np.asarray(getattr(model, attr)(X), dtype=float)
                except Exception:  # noqa: BLE001
                    continue
        return np.zeros(len(X), dtype=float)

    # ------------------------------------------------------------------
    def _train_one(self, ctx: ProjectContext, candidate, imbalanced: bool):
        kwargs: Dict[str, Any] = {}
        if imbalanced and candidate.supports_class_weight:
            kwargs["class_weight"] = "balanced"
        try:
            model = candidate.builder(**kwargs)
        except TypeError:
            model = candidate.builder()

        started = time.perf_counter()
        try:
            model.fit(ctx.X_train, ctx.y_train)
        except Exception as exc:  # noqa: BLE001
            ctx.log(self.name, f"{candidate.label} failed: {exc}")
            return None
        fit_seconds = time.perf_counter() - started

        infer_start = time.perf_counter()
        y_pred = model.predict(ctx.X_test)
        infer_ms = (time.perf_counter() - infer_start) / max(len(ctx.X_test), 1) * 1000

        row: Dict[str, Any] = {
            "key": candidate.key,
            "model": candidate.label,
            "family": candidate.family,
            "fit_seconds": round(fit_seconds, 3),
            "inference_ms_per_row": round(infer_ms, 5),
        }

        if ctx.task_type == TaskType.CLASSIFICATION:
            proba = self._proba(model, ctx.X_test)
            scores = classification_metrics(ctx.y_test, y_pred, proba)
            row.update({k: round(v, 5) for k, v in scores.items() if isinstance(v, (int, float))})
            train_pred = model.predict(ctx.X_train)
            row["train_accuracy"] = round(float((train_pred == ctx.y_train).mean()), 5)
            row["overfit_gap"] = round(row["train_accuracy"] - row.get("accuracy", 0.0), 5)
        else:
            scores = regression_metrics(ctx.y_test, y_pred)
            row.update({k: round(v, 5) for k, v in scores.items()})
            if ctx.task_type == TaskType.RANKING:
                # NDCG is the primary metric here, so every candidate has to carry it.
                # Without it the sort below has nothing to rank on.
                groups = (ctx.groups_test if ctx.groups_test is not None
                          else np.zeros(len(y_pred)))
                row.update({k: round(v, 5)
                            for k, v in ranking_metrics(ctx.y_test, y_pred, groups).items()
                            if isinstance(v, (int, float))})
            train_pred = model.predict(ctx.X_train)
            from sklearn.metrics import r2_score
            row["train_r2"] = round(float(r2_score(ctx.y_train, train_pred)), 5)
            row["overfit_gap"] = round(row["train_r2"] - row.get("r2", 0.0), 5)

        row["cv_mean"], row["cv_std"] = self._cross_validate(ctx, model)
        return model, row

    def _cv_splitter(self, ctx: ProjectContext):
        """Forecasting must never shuffle — rolling origin, always training on the past."""
        if ctx.task_type == TaskType.FORECASTING:
            from sklearn.model_selection import TimeSeriesSplit

            return TimeSeriesSplit(n_splits=config.CV_FOLDS)
        if ctx.task_type == TaskType.CLASSIFICATION:
            return StratifiedKFold(n_splits=config.CV_FOLDS, shuffle=True,
                                   random_state=config.RANDOM_STATE)
        return KFold(n_splits=config.CV_FOLDS, shuffle=True, random_state=config.RANDOM_STATE)

    def _cross_validate(self, ctx: ProjectContext, model) -> tuple[Optional[float], Optional[float]]:
        if len(ctx.X_train) > 50_000:
            return None, None
        try:
            cv = self._cv_splitter(ctx)
            if ctx.task_type == TaskType.CLASSIFICATION:
                scoring = "roc_auc" if len(np.unique(ctx.y_train)) == 2 else "f1_macro"
            elif ctx.task_type == TaskType.FORECASTING:
                scoring = "neg_mean_absolute_error"
            else:
                scoring = "r2"
            groups = ctx.groups_train if ctx.task_type == TaskType.RANKING else None
            scores = cross_val_score(model, ctx.X_train, ctx.y_train, cv=cv, scoring=scoring,
                                     n_jobs=-1, groups=groups)
            return round(float(scores.mean()), 5), round(float(scores.std()), 5)
        except Exception:
            return None, None

    def _tune(self, ctx: ProjectContext, candidate, fallback):
        if family_of(ctx.task_type) is TaskFamily.UNSUPERVISED:
            # the leaderboard already swept k and contamination — that was the search
            return fallback
        try:
            cv = self._cv_splitter(ctx)
            search = RandomizedSearchCV(
                candidate.builder(), candidate.param_grid, n_iter=6, cv=cv,
                random_state=config.RANDOM_STATE, n_jobs=-1,
                scoring="roc_auc" if ctx.task_type == TaskType.CLASSIFICATION
                and len(np.unique(ctx.y_train)) == 2 else None,
            )
            search.fit(ctx.X_train, ctx.y_train)
            ctx.research["tuning"] = {
                "best_params": {k: str(v) for k, v in search.best_params_.items()},
                "best_cv_score": round(float(search.best_score_), 5),
            }
            return search.best_estimator_
        except Exception as exc:  # noqa: BLE001
            ctx.log(self.name, f"tuning skipped: {exc}")
            return fallback

    # ------------------------------------------------------------------
    def _proba(self, model, X) -> Optional[np.ndarray]:
        if hasattr(model, "predict_proba"):
            try:
                return model.predict_proba(X)
            except Exception:
                return None
        if hasattr(model, "decision_function"):
            try:
                raw = model.decision_function(X)
                if raw.ndim == 1:
                    p = 1 / (1 + np.exp(-raw))
                    return np.column_stack([1 - p, p])
            except Exception:
                return None
        return None

    def _final_metrics(self, ctx: ProjectContext, model) -> Dict[str, Any]:
        family = family_of(ctx.task_type)
        if family is TaskFamily.UNSUPERVISED:
            return self._unsupervised_final(ctx, model)

        y_pred = model.predict(ctx.X_test)

        if ctx.task_type == TaskType.FORECASTING:
            out = forecast_metrics(ctx.y_test, y_pred)
            out["forecast_vs_actual"] = [
                {"step": i, "actual": round(float(a), 4), "predicted": round(float(p), 4)}
                for i, (a, p) in enumerate(zip(ctx.y_test, y_pred))
            ][:500]
            out["holdout_rows"] = int(len(ctx.y_test))
            return out

        if ctx.task_type == TaskType.RANKING:
            out = ranking_metrics(ctx.y_test, y_pred, ctx.groups_test
                                  if ctx.groups_test is not None else np.zeros(len(y_pred)))
            out.update(regression_metrics(ctx.y_test, y_pred))
            out["holdout_rows"] = int(len(ctx.y_test))
            return out

        if ctx.task_type == TaskType.CLASSIFICATION:
            proba = self._proba(model, ctx.X_test)
            out = classification_metrics(ctx.y_test, y_pred, proba)
            labels = out["labels"]
            if proba is not None and len(labels) == 2:
                scores = proba[:, 1]
                positive = np.unique(ctx.y_test)[-1]
                out["roc_curve"] = roc_curve_points(ctx.y_test, scores, positive)
                out["pr_curve"] = pr_curve_points(ctx.y_test, scores, positive)
                out["calibration"] = calibration_points(ctx.y_test, scores, positive)
                out["threshold_f1"] = best_threshold(ctx.y_test, scores, positive, "f1")
                out["threshold_recall"] = best_threshold(ctx.y_test, scores, positive, "youden")
                out["positive_label"] = str(positive)
        else:
            out = regression_metrics(ctx.y_test, y_pred)
            sample = min(len(y_pred), 500)
            idx = np.linspace(0, len(y_pred) - 1, sample).astype(int)
            out["predicted_vs_actual"] = [
                {"actual": round(float(ctx.y_test[i]), 4), "predicted": round(float(y_pred[i]), 4)}
                for i in idx
            ]
            residuals = np.asarray(ctx.y_test, dtype=float) - np.asarray(y_pred, dtype=float)
            counts, edges = np.histogram(residuals, bins=25)
            out["residual_histogram"] = {
                "bins": [round(float(v), 4) for v in (edges[:-1] + edges[1:]) / 2],
                "counts": [int(c) for c in counts],
            }
        out["holdout_rows"] = int(len(ctx.y_test))
        return out

    def _unsupervised_final(self, ctx: ProjectContext, model) -> Dict[str, Any]:
        labels = self._fit_and_label(ctx, model)
        if labels is None:
            return {"holdout_rows": int(len(ctx.X_test))}

        if ctx.task_type == TaskType.CLUSTERING:
            out = clustering_metrics(ctx.X_test, labels)
            ctx.labels_test = labels
            profiles = cluster_profiles(ctx.raw_X_test, labels) if ctx.raw_X_test is not None else []
            ctx.segments = {"kind": "cluster", "profiles": profiles,
                            "n_clusters": out.get("n_clusters", 0)}
            out["cluster_profiles"] = profiles
        else:
            scores = self._anomaly_scores(model, ctx.X_test)
            out = anomaly_metrics(scores, labels, ctx.y_test)
            ctx.labels_test = labels
            ctx.scores_test = scores
            ctx.segments = {"kind": "anomaly",
                            "flagged": int(out.get("n_flagged", 0)),
                            "examples": self._anomaly_examples(ctx, scores, labels)}
            out["flagged_examples"] = ctx.segments["examples"]

        out["holdout_rows"] = int(len(ctx.X_test))
        return out

    def _anomaly_examples(self, ctx: ProjectContext, scores: np.ndarray,
                          labels: np.ndarray, limit: int = 10) -> List[Dict[str, Any]]:
        """The most anomalous rows, in their original units — the thing an analyst acts on."""
        if ctx.raw_X_test is None:
            return []
        flagged = np.flatnonzero(labels == -1)
        if not len(flagged):
            return []
        order = flagged[np.argsort(scores[flagged])][:limit]
        out = []
        for rank, idx in enumerate(order, start=1):
            record = ctx.raw_X_test.iloc[int(idx)].to_dict()
            out.append({
                "rank": rank,
                "row": int(idx),
                "score": round(float(scores[idx]), 5),
                "values": {str(k): (None if pd.isna(v) else
                                    (float(v) if isinstance(v, (int, float, np.number)) else str(v)))
                           for k, v in list(record.items())[:14]},
            })
        return out

    def _fairness(self, ctx: ProjectContext, model) -> None:
        column = ctx.sensitive_column
        if family_of(ctx.task_type) is TaskFamily.UNSUPERVISED:
            ctx.fairness = {"enabled": False,
                            "reason": "fairness needs a ground-truth target to slice against"}
            return
        if not column or ctx.raw_X_test is None or column not in ctx.raw_X_test.columns:
            ctx.fairness = {"enabled": False, "reason": "no sensitive attribute selected"}
            return
        y_pred = model.predict(ctx.X_test)
        ctx.fairness = {
            "enabled": True,
            "column": column,
            # forecasting and ranking produce continuous predictions, so they slice like regression
            **fairness_slices(np.asarray(ctx.y_test), np.asarray(y_pred),
                              ctx.raw_X_test[column],
                              "classification" if ctx.task_type == TaskType.CLASSIFICATION
                              else "regression"),
        }
        if ctx.fairness.get("verdict") == "fail":
            ctx.add_issue("critical", "fairness", column,
                          f"Performance gap of {ctx.fairness['max_gap']:.3f} across '{column}' groups "
                          "exceeds the 0.10 release threshold.")
