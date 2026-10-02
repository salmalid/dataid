"""Scoring for the task families that have no ground truth to compare against.

A supervised leaderboard ranks by "how close to the right answer". Clustering, anomaly detection
and ranking each need a different notion of better, so each gets its own scorer here rather than
bending `classification_metrics` into a shape it was never meant to hold.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn import metrics as skm

# Below this many rows the internal cluster indices are too noisy to rank models by.
MIN_ROWS_FOR_INDEX = 10
# Silhouette is O(n²) in memory; sample above this.
SILHOUETTE_SAMPLE = 5000


def clustering_metrics(X: np.ndarray, labels: np.ndarray) -> Dict[str, Any]:
    """Internal validation only — there is no ground truth by definition.

    `silhouette` (higher better, -1..1) is the headline; `davies_bouldin` (lower better) and
    `calinski_harabasz` (higher better) are reported because they disagree in useful ways —
    silhouette favours compact round clusters, Calinski-Harabasz favours well-separated ones.
    """
    labels = np.asarray(labels)
    # noise points from DBSCAN are labelled -1 and are not a cluster
    real = labels[labels >= 0]
    unique = np.unique(real)
    out: Dict[str, Any] = {
        "n_clusters": int(len(unique)),
        "n_noise": int(np.sum(labels < 0)),
        "noise_pct": round(float(np.mean(labels < 0) * 100), 3),
        "cluster_sizes": [{"cluster": int(c), "count": int(np.sum(labels == c))}
                          for c in unique],
    }

    scoreable = labels >= 0
    if len(unique) < 2 or scoreable.sum() < MIN_ROWS_FOR_INDEX:
        # a single cluster is a degenerate solution: report it, rank it last
        out.update({"silhouette": -1.0, "davies_bouldin": None, "calinski_harabasz": None,
                    "valid": False})
        return out

    Xs, ls = X[scoreable], labels[scoreable]
    sample = None
    if len(Xs) > SILHOUETTE_SAMPLE:
        rng = np.random.default_rng(42)
        sample = rng.choice(len(Xs), SILHOUETTE_SAMPLE, replace=False)

    try:
        out["silhouette"] = round(float(skm.silhouette_score(
            Xs if sample is None else Xs[sample],
            ls if sample is None else ls[sample])), 5)
    except Exception:  # noqa: BLE001
        out["silhouette"] = -1.0
    for name, fn, invert in (("davies_bouldin", skm.davies_bouldin_score, False),
                             ("calinski_harabasz", skm.calinski_harabasz_score, False)):
        try:
            out[name] = round(float(fn(Xs, ls)), 5)
        except Exception:  # noqa: BLE001
            out[name] = None
    out["valid"] = True
    return out


def cluster_profiles(frame: pd.DataFrame, labels: np.ndarray,
                     max_features: int = 12) -> List[Dict[str, Any]]:
    """What actually distinguishes each cluster — the deliverable of a clustering run.

    For every cluster, the features whose mean deviates most from the population mean, in
    standard deviations. That is the sentence a user needs: "cluster 2 is the high-tenure,
    low-spend segment", not "cluster 2 exists".
    """
    labels = np.asarray(labels)
    numeric = frame.select_dtypes(include=[np.number])
    if numeric.empty:
        return []

    overall_mean = numeric.mean()
    overall_std = numeric.std().replace(0, np.nan)
    profiles: List[Dict[str, Any]] = []

    for cluster in sorted({int(c) for c in labels if c >= 0}):
        mask = labels == cluster
        if mask.sum() == 0:
            continue
        subset = numeric[mask]
        deviation = ((subset.mean() - overall_mean) / overall_std).dropna()
        ranked = deviation.reindex(deviation.abs().sort_values(ascending=False).index)
        profiles.append({
            "cluster": cluster,
            "size": int(mask.sum()),
            "share_pct": round(float(mask.mean() * 100), 2),
            "distinguishing_features": [
                {"feature": str(name),
                 "z_score": round(float(value), 3),
                 "mean": round(float(subset[name].mean()), 4),
                 "population_mean": round(float(overall_mean[name]), 4),
                 "direction": "above average" if value > 0 else "below average"}
                for name, value in ranked.head(max_features).items()
            ],
        })
    return profiles


def anomaly_metrics(scores: np.ndarray, predicted: np.ndarray,
                    y_true: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """Score an outlier detector.

    Without labels there is no accuracy to report, so the headline `anomaly_separation` is how
    far the flagged population's scores sit from the normal population's, in pooled standard
    deviations. A detector that flags points barely distinguishable from the rest scores near
    zero. When labels *are* available they are used and reported alongside.
    """
    scores = np.asarray(scores, dtype=float)
    predicted = np.asarray(predicted)
    flagged = predicted == -1

    out: Dict[str, Any] = {
        "n_flagged": int(flagged.sum()),
        "flagged_pct": round(float(flagged.mean() * 100), 3),
        "score_mean": round(float(np.mean(scores)), 5),
        "score_std": round(float(np.std(scores)), 5),
    }

    if flagged.any() and (~flagged).any():
        a, b = scores[flagged], scores[~flagged]
        pooled = np.sqrt((np.var(a) + np.var(b)) / 2)
        out["anomaly_separation"] = round(
            float(abs(np.mean(b) - np.mean(a)) / pooled) if pooled > 0 else 0.0, 5)
    else:
        # flagged everything or nothing — a useless detector, ranked last
        out["anomaly_separation"] = 0.0

    counts, edges = np.histogram(scores, bins=30)
    out["score_histogram"] = {
        "bins": [round(float(v), 5) for v in (edges[:-1] + edges[1:]) / 2],
        "counts": [int(c) for c in counts],
    }

    if y_true is not None:
        truth = _binary_outlier_truth(y_true)
        if truth is not None:
            predicted_positive = flagged.astype(int)
            out["labelled_evaluation"] = {
                "precision": round(float(skm.precision_score(truth, predicted_positive,
                                                             zero_division=0)), 5),
                "recall": round(float(skm.recall_score(truth, predicted_positive,
                                                       zero_division=0)), 5),
                "f1": round(float(skm.f1_score(truth, predicted_positive, zero_division=0)), 5),
                "true_outlier_rate": round(float(np.mean(truth) * 100), 3),
            }
            try:
                out["labelled_evaluation"]["roc_auc"] = round(
                    float(skm.roc_auc_score(truth, -scores)), 5)
            except Exception:  # noqa: BLE001
                pass
    return out


def _binary_outlier_truth(y_true: np.ndarray) -> Optional[np.ndarray]:
    """Map a two-class label column onto 1 = outlier, taking the minority class as the outlier."""
    values, counts = np.unique(np.asarray(y_true).astype(str), return_counts=True)
    if len(values) != 2:
        return None
    minority = values[int(np.argmin(counts))]
    return (np.asarray(y_true).astype(str) == minority).astype(int)


# ------------------------------------------------------------------------- ranking
def ndcg_at_k(relevance: Sequence[float], k: int = 10) -> float:
    """Normalised discounted cumulative gain for one query's predicted ordering."""
    rel = np.asarray(relevance, dtype=float)[:k]
    if rel.size == 0:
        return 0.0
    discounts = 1.0 / np.log2(np.arange(2, rel.size + 2))
    dcg = float(np.sum(rel * discounts))
    ideal = np.sort(np.asarray(relevance, dtype=float))[::-1][:k]
    idcg = float(np.sum(ideal * 1.0 / np.log2(np.arange(2, ideal.size + 2))))
    return dcg / idcg if idcg > 0 else 0.0


def ranking_metrics(y_true: np.ndarray, y_score: np.ndarray, groups: Sequence[Any],
                    k: int = 10) -> Dict[str, Any]:
    """Rank quality averaged over queries.

    Ranking is only meaningful *within* a group — a global correlation would reward getting
    easy queries right while mangling hard ones. Every metric here is computed per group and
    then averaged, which is what a search or recommendation team actually reports.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_score = np.asarray(y_score, dtype=float)
    groups = pd.Series(list(groups)).astype(str).to_numpy()

    ndcgs, maps, mrrs, sizes = [], [], [], []
    for group in pd.unique(groups):
        mask = groups == group
        if mask.sum() < 2:
            continue
        truth, score = y_true[mask], y_score[mask]
        order = np.argsort(-score)
        ranked = truth[order]
        ndcgs.append(ndcg_at_k(ranked, k))
        sizes.append(int(mask.sum()))

        relevant = ranked > 0
        if relevant.any():
            hits = np.cumsum(relevant)
            precision_at = hits / np.arange(1, len(ranked) + 1)
            maps.append(float(np.sum(precision_at * relevant) / relevant.sum()))
            mrrs.append(float(1.0 / (np.argmax(relevant) + 1)))
        else:
            maps.append(0.0)
            mrrs.append(0.0)

    if not ndcgs:
        return {"ndcg": 0.0, "map": 0.0, "mrr": 0.0, "n_queries": 0, "valid": False}

    return {
        "ndcg": round(float(np.mean(ndcgs)), 5),
        f"ndcg_at_{k}": round(float(np.mean(ndcgs)), 5),
        "map": round(float(np.mean(maps)), 5),
        "mrr": round(float(np.mean(mrrs)), 5),
        "n_queries": len(ndcgs),
        "mean_query_size": round(float(np.mean(sizes)), 2),
        "valid": True,
    }


def forecast_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    """Regression metrics plus the two a forecaster is actually judged on.

    `smape` is bounded and survives near-zero actuals, where MAPE explodes. `mase_naive`
    compares against the naive "tomorrow equals today" forecast — below 1.0 means the model
    beats doing nothing, which is the only bar that matters.
    """
    from .metrics import regression_metrics

    out = dict(regression_metrics(y_true, y_pred))
    truth = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)

    denominator = (np.abs(truth) + np.abs(pred)) / 2
    with np.errstate(divide="ignore", invalid="ignore"):
        smape = np.where(denominator == 0, 0.0, np.abs(truth - pred) / denominator)
    out["smape"] = round(float(np.mean(smape) * 100), 5)

    if len(truth) > 1:
        naive_error = np.mean(np.abs(np.diff(truth)))
        model_error = np.mean(np.abs(truth - pred))
        out["mase_naive"] = round(float(model_error / naive_error), 5) if naive_error > 0 else None
        out["beats_naive"] = bool(out["mase_naive"] is not None and out["mase_naive"] < 1.0)
    return out
