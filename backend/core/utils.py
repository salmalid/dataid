"""Shared helpers: type inference, JSON coercion, statistical primitives."""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import config

DATE_HINTS = ("date", "time", "day", "month", "year", "timestamp", "dt", "created", "updated")
ID_HINTS = ("id", "uuid", "guid", "index", "key", "code", "number", "no")
# Substrings that imply a column is recorded at or after the outcome. Deliberately
# excludes generic words like "score" — those fire on legitimate features and the
# correlation/AUC probes catch the genuinely leaky ones anyway.
LEAKY_HINTS = ("exit_date", "churn_date", "_target", "label_", "outcome", "prediction",
               "resolved", "settled", "chargeback", "post_", "after_", "_final",
               "closed_date", "refund")


def coerce_json(obj: Any) -> Any:
    """Make numpy / pandas structures serialisable."""
    if isinstance(obj, dict):
        return {str(k): coerce_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [coerce_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        return None if (math.isnan(val) or math.isinf(val)) else val
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return coerce_json(obj.tolist())
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, pd.Series):
        return coerce_json(obj.to_dict())
    if isinstance(obj, pd.DataFrame):
        return coerce_json(obj.to_dict(orient="records"))
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    return obj


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).strip().lower()).strip("_") or "col"


def looks_like_datetime(series: pd.Series, name: str = "") -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)) and any(h in name.lower() for h in DATE_HINTS):
        sample = series.dropna().astype(str).head(50)
        if sample.empty:
            return False
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        return parsed.notna().mean() > 0.8
    return False


def looks_like_identifier(series: pd.Series, name: str) -> bool:
    n = len(series)
    if n == 0:
        return False
    # A timestamp is a coordinate, not a key. Dates are all-distinct by nature, and treating
    # one as an identifier deletes the column a forecast is ordered by.
    if looks_like_datetime(series, name):
        return False

    unique_ratio = series.nunique(dropna=True) / n
    if unique_ratio <= 0.95:
        return False
    name_hit = any(name.lower() == h or name.lower().endswith("_" + h) for h in ID_HINTS)
    if name_hit or pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        return True
    # Every value distinct. That is what a key looks like — and also what any continuous
    # measurement looks like, so floats are measurements unless the name says otherwise.
    return unique_ratio == 1.0 and not pd.api.types.is_float_dtype(series)


def infer_task_type(y: pd.Series) -> str:
    """classification vs regression from the target's shape."""
    y = y.dropna()
    if pd.api.types.is_string_dtype(y) or y.dtype == object or isinstance(y.dtype, pd.CategoricalDtype) or pd.api.types.is_bool_dtype(y):
        return "classification"
    nunique = y.nunique()
    if nunique <= 2:
        return "classification"
    if pd.api.types.is_integer_dtype(y) and nunique <= 20 and nunique / max(len(y), 1) < 0.05:
        return "classification"
    return "regression"


def split_columns(df: pd.DataFrame, target: Optional[str] = None) -> Dict[str, List[str]]:
    numeric, categorical, datetime_cols, text, identifiers = [], [], [], [], []
    for col in df.columns:
        if col == target:
            continue
        s = df[col]
        if looks_like_datetime(s, col):
            datetime_cols.append(col)
        elif looks_like_identifier(s, col):
            identifiers.append(col)
        elif pd.api.types.is_numeric_dtype(s):
            numeric.append(col)
        elif s.dtype == object and s.dropna().astype(str).str.len().mean() > 40:
            text.append(col)
        else:
            categorical.append(col)
    return {"numeric": numeric, "categorical": categorical, "datetime": datetime_cols,
            "text": text, "identifier": identifiers}


def psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """Population Stability Index between a reference and a current sample."""
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]
    if expected.size == 0 or actual.size == 0:
        return 0.0
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, buckets + 1)))
    if edges.size < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    e_pct = np.histogram(expected, bins=edges)[0] / expected.size
    a_pct = np.histogram(actual, bins=edges)[0] / actual.size
    eps = 1e-6
    e_pct = np.clip(e_pct, eps, None)
    a_pct = np.clip(a_pct, eps, None)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def psi_reference(expected: np.ndarray, buckets: int = 10) -> Optional[Dict[str, Any]]:
    """Freeze a feature's real training distribution so PSI can be recomputed against it later.

    Stores the quantile bin edges and the reference proportions actually observed. Summary
    statistics are not enough: reconstructing a distribution from a mean and a standard
    deviation assumes normality, and PSI against a fabricated bell curve is noise for anything
    skewed, bimodal or discrete.

    The outer edges are ±inf, which is not representable in strict JSON, so only the finite
    interior edges are stored and the infinities are restored by psi_observed().
    """
    expected = np.asarray(expected, dtype=float)
    expected = expected[np.isfinite(expected)]
    if expected.size == 0:
        return None
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, buckets + 1)))
    if edges.size < 3:
        return None
    edges[0], edges[-1] = -np.inf, np.inf
    ref_pct = np.histogram(expected, bins=edges)[0] / expected.size
    return {
        "edges": [round(float(e), 6) for e in edges[1:-1]],
        "ref_pct": [round(float(p), 6) for p in ref_pct],
        "sample_size": int(expected.size),
        # The reference is captured after cleaning, where missing values were median-imputed —
        # which leaves a spike at the median. A live batch whose nulls are simply dropped has no
        # such spike and reports drift that is not there, so it is imputed the same way.
        "impute": round(float(np.median(expected)), 6),
    }


def psi_observed(reference: Dict[str, Any], actual: np.ndarray) -> Optional[float]:
    """PSI of a live batch against bins frozen by psi_reference(). None if unscoreable."""
    actual = np.asarray(actual, dtype=float)
    fill = reference.get("impute")
    if fill is None:
        actual = actual[np.isfinite(actual)]
    else:
        actual = np.where(np.isfinite(actual), actual, float(fill))
    ref_pct = np.asarray(reference.get("ref_pct") or [], dtype=float)
    if actual.size == 0 or ref_pct.size == 0:
        return None
    edges = np.concatenate(([-np.inf], np.asarray(reference.get("edges") or [], dtype=float),
                            [np.inf]))
    if edges.size - 1 != ref_pct.size:
        return None
    a_pct = np.histogram(actual, bins=edges)[0] / actual.size
    eps = 1e-6
    ref_pct = np.clip(ref_pct, eps, None)
    a_pct = np.clip(a_pct, eps, None)
    return float(np.sum((a_pct - ref_pct) * np.log(a_pct / ref_pct)))


def iqr_outlier_mask(series: pd.Series, factor: float = 1.5) -> pd.Series:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    span = q3 - q1
    if span == 0 or pd.isna(span):
        return pd.Series(False, index=series.index)
    return (series < q1 - factor * span) | (series > q3 + factor * span)


def safe_corr(df: pd.DataFrame) -> pd.DataFrame:
    numeric = df.select_dtypes(include=[np.number])
    if numeric.shape[1] < 2:
        return pd.DataFrame()
    return numeric.corr(numeric_only=True).fillna(0.0)


def top_correlations(df: pd.DataFrame, threshold: float = 0.85, limit: int = 15) -> List[Tuple[str, str, float]]:
    corr = safe_corr(df)
    if corr.empty:
        return []
    pairs: List[Tuple[str, str, float]] = []
    cols = list(corr.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            value = float(corr.loc[a, b])
            if abs(value) >= threshold:
                pairs.append((a, b, value))
    pairs.sort(key=lambda p: abs(p[2]), reverse=True)
    return pairs[:limit]


def downsample(df: pd.DataFrame, max_rows: int = config.MAX_TRAIN_ROWS,
               random_state: int = config.RANDOM_STATE) -> pd.DataFrame:
    if len(df) <= max_rows:
        return df
    return df.sample(max_rows, random_state=random_state).reset_index(drop=True)


def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def format_metric(name: str, value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    if name in {"accuracy", "roc_auc", "pr_auc", "f1", "precision", "recall", "r2"}:
        return f"{value:.4f}"
    return f"{value:,.4f}"
