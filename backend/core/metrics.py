"""Metric computation for every task family, plus threshold search and fairness slices."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn import metrics as skm


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                           y_proba: Optional[np.ndarray] = None) -> Dict[str, Any]:
    labels = sorted(set(np.unique(y_true)) | set(np.unique(y_pred)))
    binary = len(labels) == 2
    average = "binary" if binary else "macro"
    pos_label = labels[-1] if binary else None

    out: Dict[str, Any] = {
        "accuracy": float(skm.accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(skm.balanced_accuracy_score(y_true, y_pred)),
        "precision": float(skm.precision_score(y_true, y_pred, average=average,
                                               pos_label=pos_label, zero_division=0)),
        "recall": float(skm.recall_score(y_true, y_pred, average=average,
                                         pos_label=pos_label, zero_division=0)),
        "f1": float(skm.f1_score(y_true, y_pred, average=average,
                                 pos_label=pos_label, zero_division=0)),
        "f1_macro": float(skm.f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "mcc": float(skm.matthews_corrcoef(y_true, y_pred)) if len(labels) > 1 else 0.0,
        "n_classes": len(labels),
        "labels": [str(l) for l in labels],
    }

    if y_proba is not None:
        try:
            if binary:
                scores = y_proba[:, 1] if y_proba.ndim == 2 else y_proba
                y_bin = (np.asarray(y_true) == labels[-1]).astype(int)
                out["roc_auc"] = float(skm.roc_auc_score(y_bin, scores))
                out["pr_auc"] = float(skm.average_precision_score(y_bin, scores))
                out["log_loss"] = float(skm.log_loss(y_bin, np.clip(scores, 1e-9, 1 - 1e-9)))
                out["brier"] = float(skm.brier_score_loss(y_bin, scores))
            else:
                out["roc_auc"] = float(skm.roc_auc_score(y_true, y_proba, multi_class="ovr",
                                                         average="macro"))
                out["log_loss"] = float(skm.log_loss(y_true, y_proba))
        except Exception:
            pass

    out["confusion_matrix"] = skm.confusion_matrix(y_true, y_pred, labels=labels).tolist()
    out["per_class"] = _per_class(y_true, y_pred, labels)
    return out


def _per_class(y_true: np.ndarray, y_pred: np.ndarray, labels: List[Any]) -> List[Dict[str, Any]]:
    report = skm.classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    rows = []
    for label in labels:
        stats = report.get(str(label), {})
        rows.append({
            "label": str(label),
            "precision": round(float(stats.get("precision", 0.0)), 4),
            "recall": round(float(stats.get("recall", 0.0)), 4),
            "f1": round(float(stats.get("f1-score", 0.0)), 4),
            "support": int(stats.get("support", 0)),
        })
    return rows


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    residuals = y_true - y_pred
    mse = float(skm.mean_squared_error(y_true, y_pred))
    denom = np.where(np.abs(y_true) < 1e-9, np.nan, y_true)
    mape = float(np.nanmean(np.abs(residuals / denom)) * 100)
    return {
        "r2": float(skm.r2_score(y_true, y_pred)),
        "mae": float(skm.mean_absolute_error(y_true, y_pred)),
        "mse": mse,
        "rmse": float(np.sqrt(mse)),
        "mape": mape,
        "median_absolute_error": float(skm.median_absolute_error(y_true, y_pred)),
        "explained_variance": float(skm.explained_variance_score(y_true, y_pred)),
        "residual_mean": float(residuals.mean()),
        "residual_std": float(residuals.std()),
    }


def roc_curve_points(y_true: np.ndarray, scores: np.ndarray, positive_label: Any,
                     max_points: int = 200) -> List[Dict[str, float]]:
    y_bin = (np.asarray(y_true) == positive_label).astype(int)
    fpr, tpr, _ = skm.roc_curve(y_bin, scores)
    idx = np.linspace(0, len(fpr) - 1, min(len(fpr), max_points)).astype(int)
    return [{"fpr": round(float(fpr[i]), 4), "tpr": round(float(tpr[i]), 4)} for i in idx]


def pr_curve_points(y_true: np.ndarray, scores: np.ndarray, positive_label: Any,
                    max_points: int = 200) -> List[Dict[str, float]]:
    y_bin = (np.asarray(y_true) == positive_label).astype(int)
    precision, recall, _ = skm.precision_recall_curve(y_bin, scores)
    idx = np.linspace(0, len(precision) - 1, min(len(precision), max_points)).astype(int)
    return [{"recall": round(float(recall[i]), 4), "precision": round(float(precision[i]), 4)}
            for i in idx]


def best_threshold(y_true: np.ndarray, scores: np.ndarray, positive_label: Any,
                   objective: str = "f1") -> Dict[str, float]:
    """Sweep the decision threshold — this is what 'I want better recall' adjusts."""
    y_bin = (np.asarray(y_true) == positive_label).astype(int)
    grid = np.linspace(0.05, 0.95, 91)
    best = {"threshold": 0.5, "score": -1.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    for t in grid:
        pred = (scores >= t).astype(int)
        precision = skm.precision_score(y_bin, pred, zero_division=0)
        recall = skm.recall_score(y_bin, pred, zero_division=0)
        f1 = skm.f1_score(y_bin, pred, zero_division=0)
        score = {"f1": f1, "recall": recall, "precision": precision,
                 "youden": recall + skm.recall_score(1 - y_bin, 1 - pred, zero_division=0) - 1}.get(objective, f1)
        if score > best["score"]:
            best = {"threshold": round(float(t), 3), "score": round(float(score), 4),
                    "precision": round(float(precision), 4), "recall": round(float(recall), 4),
                    "f1": round(float(f1), 4)}
    return best


def calibration_points(y_true: np.ndarray, scores: np.ndarray, positive_label: Any,
                       bins: int = 10) -> List[Dict[str, float]]:
    y_bin = (np.asarray(y_true) == positive_label).astype(int)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(scores, edges) - 1, 0, bins - 1)
    points = []
    for b in range(bins):
        mask = idx == b
        if not mask.any():
            continue
        points.append({
            "predicted": round(float(scores[mask].mean()), 4),
            "observed": round(float(y_bin[mask].mean()), 4),
            "count": int(mask.sum()),
        })
    return points


def fairness_slices(y_true: np.ndarray, y_pred: np.ndarray, groups: pd.Series,
                    task_type: str) -> Dict[str, Any]:
    """Per-group performance plus the worst pairwise gap."""
    groups = groups.astype(str).reset_index(drop=True)
    rows: List[Dict[str, Any]] = []
    for value in groups.value_counts().head(12).index:
        mask = (groups == value).to_numpy()
        if mask.sum() < 10:
            continue
        entry: Dict[str, Any] = {"group": str(value), "n": int(mask.sum())}
        if task_type == "classification":
            labels = sorted(set(np.unique(y_true)))
            positive = labels[-1]
            entry["selection_rate"] = round(float((y_pred[mask] == positive).mean()), 4)
            entry["accuracy"] = round(float((y_pred[mask] == y_true[mask]).mean()), 4)
            actual_pos = y_true[mask] == positive
            entry["tpr"] = round(float((y_pred[mask][actual_pos] == positive).mean()), 4) \
                if actual_pos.any() else None
        else:
            entry["mae"] = round(float(np.mean(np.abs(y_true[mask] - y_pred[mask]))), 4)
            entry["r2"] = round(float(skm.r2_score(y_true[mask], y_pred[mask])), 4) \
                if mask.sum() > 2 else None
        rows.append(entry)

    key = "accuracy" if task_type == "classification" else "mae"
    values = [r[key] for r in rows if r.get(key) is not None]
    gap = round(float(max(values) - min(values)), 4) if len(values) > 1 else 0.0
    return {
        "slices": rows,
        "metric": key,
        "max_gap": gap,
        "verdict": "fail" if gap > 0.1 else ("review" if gap > 0.05 else "pass"),
    }
