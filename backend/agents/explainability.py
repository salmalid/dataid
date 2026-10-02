"""Explainability — global importance, SHAP, local attributions, counterfactuals, plain-English story."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from ..core import config
from ..core.context import ProjectContext, TaskFamily, TaskType, family_of
from ..core.llm import narrate
from .base import Agent


class ExplainabilityAgent(Agent):
    name = "explainability"
    label = "Explainability Agent"
    description = "Explains the winning model globally and per prediction, in numbers and in English."
    critical = False

    def run(self, ctx: ProjectContext) -> None:
        if family_of(ctx.task_type) is TaskFamily.UNSUPERVISED:
            self._explain_unsupervised(ctx)
            return

        self.progress(ctx, "Computing global feature importance", 0.2)
        importance = self._global_importance(ctx)

        self.progress(ctx, "Running SHAP attribution", 0.45)
        shap_summary = self._shap(ctx)

        self.progress(ctx, "Building local explanations", 0.65)
        local = self._local_explanations(ctx, importance)

        self.progress(ctx, "Searching counterfactuals", 0.8)
        counterfactuals = self._counterfactuals(ctx, importance)

        top_names = [f["feature"] for f in importance[:5]]
        ctx.explainability = {
            "method": shap_summary.get("method", "permutation"),
            "global_importance": importance,
            "shap": shap_summary,
            "local_explanations": local,
            "counterfactuals": counterfactuals,
            "partial_dependence": self._partial_dependence(ctx, top_names),
            "business_summary": self._business_summary(ctx, top_names),
        }

    # ------------------------------------------------------------------ unsupervised
    def _explain_unsupervised(self, ctx: ProjectContext) -> None:
        """Permutation importance needs a ground truth to permute against, so it cannot run here.

        The question changes shape: not "which features drive the prediction" but "which
        features separate the groups the model found". An F-statistic across the discovered
        labels answers that directly and needs no target.
        """
        self.progress(ctx, "Ranking the features that separate the groups", 0.3)
        importance = self._separation_importance(ctx)

        self.progress(ctx, "Profiling what the model found", 0.7)
        clustering = ctx.task_type == TaskType.CLUSTERING
        profiles = ctx.segments.get("profiles", []) if clustering else []
        examples = ctx.segments.get("examples", []) if not clustering else []

        ctx.explainability = {
            "method": "between-group F-statistic",
            "global_importance": importance,
            "shap": {"available": False,
                     "reason": "SHAP explains a prediction against a target; this run has none."},
            "local_explanations": [],
            "counterfactuals": [],
            "partial_dependence": [],
            "cluster_profiles": profiles,
            "flagged_examples": examples,
            "business_summary": self._unsupervised_summary(ctx, importance, profiles, examples),
        }

    def _separation_importance(self, ctx: ProjectContext) -> List[Dict[str, Any]]:
        """How strongly each feature differs across the discovered groups."""
        labels = ctx.labels_test
        if labels is None or ctx.X_test is None:
            return []
        labels = np.asarray(labels)
        groups = [g for g in np.unique(labels) if g >= 0 or ctx.task_type == TaskType.ANOMALY]
        if len(groups) < 2:
            return []

        from scipy import stats

        names = ctx.feature_names
        out: List[Dict[str, Any]] = []
        for i, name in enumerate(names):
            column = ctx.X_test[:, i]
            samples = [column[labels == g] for g in groups]
            samples = [s for s in samples if len(s) > 1]
            if len(samples) < 2:
                continue
            try:
                f_stat, p_value = stats.f_oneway(*samples)
            except Exception:  # noqa: BLE001
                continue
            if not np.isfinite(f_stat):
                continue
            out.append({"feature": str(name), "importance": round(float(f_stat), 6),
                        "p_value": round(float(p_value), 8) if np.isfinite(p_value) else None,
                        "source": "f_statistic"})
        out.sort(key=lambda d: d["importance"], reverse=True)
        return out[:30]

    def _unsupervised_summary(self, ctx: ProjectContext, importance: List[Dict[str, Any]],
                              profiles: List[Dict[str, Any]],
                              examples: List[Dict[str, Any]]) -> str:
        drivers = ", ".join(f["feature"] for f in importance[:3]) or "no single feature"
        if ctx.task_type == TaskType.CLUSTERING:
            n = ctx.metrics.get("n_clusters", len(profiles))
            silhouette = ctx.metrics.get("silhouette")
            quality = ("well separated" if isinstance(silhouette, (int, float)) and silhouette > 0.5
                       else "loosely separated" if isinstance(silhouette, (int, float))
                       and silhouette > 0.25 else "weakly separated")
            lines = [f"{ctx.best_model_name} split the data into {n} {quality} segments "
                     f"(silhouette {silhouette}). The features that separate them most are "
                     f"{drivers}."]
            for profile in profiles[:4]:
                top = profile["distinguishing_features"][:2]
                traits = "; ".join(f"{t['feature']} {t['direction']}" for t in top)
                lines.append(f"Segment {profile['cluster']} holds {profile['size']} rows "
                             f"({profile['share_pct']}%) and is characterised by {traits}.")
            return "\n\n".join(lines)

        flagged = ctx.metrics.get("n_flagged", 0)
        pct = ctx.metrics.get("flagged_pct", 0)
        separation = ctx.metrics.get("anomaly_separation")
        summary = (f"{ctx.best_model_name} flagged {flagged} of {ctx.metrics.get('holdout_rows', 0)} "
                   f"holdout rows ({pct}%) as anomalous, separating them from normal rows by "
                   f"{separation} pooled standard deviations. The features that most distinguish "
                   f"flagged rows are {drivers}.")
        labelled = ctx.metrics.get("labelled_evaluation")
        if labelled:
            summary += (f" Checked against the supplied labels, the detector reaches "
                        f"precision {labelled['precision']} and recall {labelled['recall']}.")
        elif examples:
            summary += " The highest-scoring flagged rows are listed for review."
        return summary

    # ------------------------------------------------------------------
    def _global_importance(self, ctx: ProjectContext) -> List[Dict[str, Any]]:
        model = ctx.best_model
        names = ctx.feature_names

        native = getattr(model, "feature_importances_", None)
        if native is not None and len(native) == len(names):
            pairs = sorted(zip(names, native), key=lambda p: abs(p[1]), reverse=True)
            return [{"feature": str(n), "importance": round(float(v), 6), "source": "native"}
                    for n, v in pairs[:30]]

        coef = getattr(model, "coef_", None)
        if coef is not None:
            flat = np.ravel(coef) if np.ndim(coef) == 1 else np.abs(coef).mean(axis=0)
            if len(flat) == len(names):
                pairs = sorted(zip(names, flat), key=lambda p: abs(p[1]), reverse=True)
                return [{"feature": str(n), "importance": round(float(abs(v)), 6),
                         "signed": round(float(v), 6), "source": "coefficient"} for n, v in pairs[:30]]

        sample = min(len(ctx.X_test), 2000)
        result = permutation_importance(model, ctx.X_test[:sample], ctx.y_test[:sample],
                                        n_repeats=5, random_state=config.RANDOM_STATE, n_jobs=-1)
        pairs = sorted(zip(names, result.importances_mean, result.importances_std),
                       key=lambda p: p[1], reverse=True)
        return [{"feature": str(n), "importance": round(float(m), 6), "std": round(float(s), 6),
                 "source": "permutation"} for n, m, s in pairs[:30]]

    def _shap(self, ctx: ProjectContext) -> Dict[str, Any]:
        try:
            import shap  # noqa: F401
        except ImportError:
            return {"available": False, "method": "permutation",
                    "reason": "shap is not installed — permutation importance used instead"}

        import shap

        try:
            sample_n = min(len(ctx.X_test), 300)
            background = ctx.X_train[:min(len(ctx.X_train), 100)]
            X = ctx.X_test[:sample_n]
            model = ctx.best_model

            if hasattr(model, "feature_importances_"):
                explainer = shap.TreeExplainer(model)
                values = explainer.shap_values(X)
            else:
                predict = model.predict_proba if hasattr(model, "predict_proba") else model.predict
                explainer = shap.KernelExplainer(predict, shap.sample(background, 50))
                values = explainer.shap_values(X[:100], nsamples=100)

            arr = np.array(values)
            if arr.ndim == 3:
                arr = np.abs(arr).mean(axis=0) if arr.shape[0] <= 10 else np.abs(arr).mean(axis=2)
            mean_abs = np.abs(arr).mean(axis=0)
            order = np.argsort(mean_abs)[::-1][:25]
            return {
                "available": True,
                "method": "shap",
                "sample_size": int(arr.shape[0]),
                "top_features": [
                    {"feature": ctx.feature_names[i] if i < len(ctx.feature_names) else f"f{i}",
                     "mean_abs_shap": round(float(mean_abs[i]), 6)}
                    for i in order
                ],
                "beeswarm": [
                    {"feature": ctx.feature_names[i] if i < len(ctx.feature_names) else f"f{i}",
                     "values": [round(float(v), 5) for v in arr[:120, i]]}
                    for i in order[:10]
                ],
            }
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "method": "permutation", "reason": str(exc)}

    def _local_explanations(self, ctx: ProjectContext, importance: List[Dict[str, Any]],
                            n: int = 5) -> List[Dict[str, Any]]:
        """LIME-style local surrogate: perturb around a row and fit a weighted linear model."""
        from sklearn.linear_model import Ridge

        model = ctx.best_model
        rng = np.random.default_rng(config.RANDOM_STATE)
        out: List[Dict[str, Any]] = []
        n = min(n, len(ctx.X_test))
        stds = ctx.X_train.std(axis=0)
        stds[stds == 0] = 1.0

        predict = (lambda X: model.predict_proba(X)[:, -1]) if hasattr(model, "predict_proba") \
            else (lambda X: model.predict(X))

        for i in range(n):
            row = ctx.X_test[i]
            noise = rng.normal(0, 0.5, size=(300, len(row))) * stds
            neighbourhood = row + noise
            try:
                y_local = predict(neighbourhood)
            except Exception:
                break
            distances = np.linalg.norm(noise / stds, axis=1)
            weights = np.exp(-(distances ** 2) / (2 * (0.75 * np.sqrt(len(row))) ** 2))
            surrogate = Ridge(alpha=1.0).fit(neighbourhood, y_local, sample_weight=weights)
            contributions = surrogate.coef_ * row
            order = np.argsort(np.abs(contributions))[::-1][:8]

            prediction = model.predict(row.reshape(1, -1))[0]
            confidence = None
            if hasattr(model, "predict_proba"):
                confidence = round(float(model.predict_proba(row.reshape(1, -1)).max()), 4)

            out.append({
                "index": i,
                "prediction": str(prediction) if ctx.task_type == TaskType.CLASSIFICATION
                else round(float(prediction), 4),
                "actual": str(ctx.y_test[i]) if ctx.task_type == TaskType.CLASSIFICATION
                else round(float(ctx.y_test[i]), 4),
                "confidence": confidence,
                "contributions": [
                    {"feature": ctx.feature_names[j] if j < len(ctx.feature_names) else f"f{j}",
                     "contribution": round(float(contributions[j]), 5),
                     "direction": "increases" if contributions[j] > 0 else "decreases"}
                    for j in order
                ],
            })
        return out

    def _counterfactuals(self, ctx: ProjectContext, importance: List[Dict[str, Any]],
                         n: int = 3) -> List[Dict[str, Any]]:
        """Smallest single-feature nudge that flips the prediction."""
        if ctx.task_type != TaskType.CLASSIFICATION or ctx.best_model is None:
            return []
        model = ctx.best_model
        name_to_idx = {name: i for i, name in enumerate(ctx.feature_names)}
        top_idx = [name_to_idx[f["feature"]] for f in importance[:6] if f["feature"] in name_to_idx]
        if not top_idx:
            return []

        stds = ctx.X_train.std(axis=0)
        stds[stds == 0] = 1.0
        out: List[Dict[str, Any]] = []

        for i in range(min(n, len(ctx.X_test))):
            row = ctx.X_test[i].copy()
            original = model.predict(row.reshape(1, -1))[0]
            found: Optional[Dict[str, Any]] = None
            for j in top_idx:
                for delta in (0.5, 1.0, 1.5, 2.0, 3.0):
                    for sign in (1, -1):
                        probe = row.copy()
                        probe[j] = row[j] + sign * delta * stds[j]
                        if model.predict(probe.reshape(1, -1))[0] != original:
                            found = {
                                "feature": ctx.feature_names[j],
                                "shift_in_std": round(sign * delta, 2),
                                "from_prediction": str(original),
                                "to_prediction": str(model.predict(probe.reshape(1, -1))[0]),
                            }
                            break
                    if found:
                        break
                if found:
                    break
            out.append({"index": i, "original_prediction": str(original),
                        "counterfactual": found,
                        "note": "no single-feature flip found within 3 standard deviations"
                        if not found else ""})
        return out

    def _partial_dependence(self, ctx: ProjectContext, features: List[str]) -> List[Dict[str, Any]]:
        name_to_idx = {name: i for i, name in enumerate(ctx.feature_names)}
        model = ctx.best_model
        out: List[Dict[str, Any]] = []
        base = ctx.X_test[:min(len(ctx.X_test), 300)]
        predict = (lambda X: model.predict_proba(X)[:, -1]) if hasattr(model, "predict_proba") \
            else (lambda X: model.predict(X))

        for name in features[:4]:
            j = name_to_idx.get(name)
            if j is None:
                continue
            grid = np.quantile(ctx.X_train[:, j], np.linspace(0.05, 0.95, 12))
            points = []
            for value in np.unique(grid):
                probe = base.copy()
                probe[:, j] = value
                try:
                    points.append({"x": round(float(value), 4),
                                   "y": round(float(np.mean(predict(probe))), 5)})
                except Exception:
                    break
            if points:
                out.append({"feature": name, "points": points})
        return out

    def _business_summary(self, ctx: ProjectContext, top_features: List[str]) -> str:
        m = ctx.metrics
        if ctx.task_type == TaskType.CLASSIFICATION:
            metric_line = (f"accuracy {m.get('accuracy', 0):.1%}, "
                           f"recall {m.get('recall', 0):.1%}")
        elif ctx.task_type == TaskType.FORECASTING:
            # R² is close to meaningless on a trending series; MASE against the naive
            # forecast is the number a forecasting team is actually held to.
            mase = m.get("mase_naive")
            verdict = ("beats the naive forecast" if m.get("beats_naive")
                       else "does not yet beat simply repeating the last value")
            metric_line = (f"MAE {m.get('mae', 0):,.2f}, sMAPE {m.get('smape', 0):.1f}%"
                           + (f", MASE {mase:.2f} — {verdict}" if mase is not None else ""))
        elif ctx.task_type == TaskType.RANKING:
            metric_line = (f"NDCG {m.get('ndcg', 0):.3f}, MAP {m.get('map', 0):.3f} "
                           f"across {m.get('n_queries', 0)} holdout queries")
        else:
            metric_line = (f"R² {m.get('r2', 0):.3f}, MAE {m.get('mae', 0):,.2f}")
        drivers = ", ".join(top_features[:3]) or "the engineered features"
        prose = narrate(
            f"Explain to a non-technical executive why a {ctx.best_model_name} model predicting "
            f"'{ctx.target_column}' at {metric_line} is trustworthy, and that {drivers} drive it."
        )
        # The first sentence is computed from the run; the second is written by the model.
        # When no narrator is configured the computed part stands alone rather than being
        # padded out to look like a longer analysis.
        summary = (f"The selected model is **{ctx.best_model_name}**, scoring {metric_line} on data "
                   f"it never saw during training. Its decisions are driven mainly by {drivers}.")
        return f"{summary}\n\n{prose}" if prose.strip() else summary
