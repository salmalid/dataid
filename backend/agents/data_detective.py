"""Data Detective — profiles the dataset and hunts for everything that will hurt later."""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ..core import config
from ..core.context import ProjectContext, TaskType, requires_target
from ..core.utils import (
    iqr_outlier_mask,
    infer_task_type,
    looks_like_datetime,
    looks_like_identifier,
    split_columns,
    top_correlations,
)
from .base import Agent


class DataDetectiveAgent(Agent):
    name = "data_detective"
    label = "Data Detective"
    description = "Profiles the dataset and flags missing values, outliers, leakage, bias and collinearity."

    def run(self, ctx: ProjectContext) -> None:
        from ..core.validation import reserve_holdout
        reserve_holdout(ctx)
        df = ctx.df
        self.progress(ctx, "Profiling columns", 0.1)
        ctx.profile = self._profile(df, ctx.target_column)

        if ctx.task_type is None:
            ctx.task_type = TaskType(infer_task_type(df[ctx.target_column]))
        ctx.log(self.name, f"task type resolved as {ctx.task_type.value}")
        has_target = requires_target(ctx.task_type) and ctx.target_column in df.columns

        self.progress(ctx, "Scanning for missing values", 0.25)
        self._missing(ctx)

        self.progress(ctx, "Scanning for duplicates and constants", 0.4)
        self._duplicates_and_constants(ctx)

        self.progress(ctx, "Detecting outliers", 0.55)
        self._outliers(ctx)

        # Every leakage probe is defined relative to a target; without one there is nothing
        # for a feature to leak. Same for class balance and target health.
        if has_target:
            self.progress(ctx, "Hunting target leakage", 0.7)
            # Feature exclusion decisions must not inspect held-out target values.
            ctx.df = df.iloc[ctx.train_indices]
            try:
                self._leakage(ctx)
            finally:
                ctx.df = df
        else:
            ctx.log(self.name, "no target column — leakage and target-health probes skipped")

        self.progress(ctx, "Measuring collinearity and class balance", 0.85)
        self._correlations(ctx)
        if has_target:
            self._target_health(ctx)

        ctx.eda = self._eda(ctx)

    # ------------------------------------------------------------------ profile
    def _profile(self, df: pd.DataFrame, target: str) -> Dict[str, Any]:
        groups = split_columns(df, target)
        columns: List[Dict[str, Any]] = []
        for col in df.columns:
            s = df[col]
            entry: Dict[str, Any] = {
                "name": col,
                "dtype": str(s.dtype),
                "role": "target" if col == target else _role_of(col, groups),
                "missing": int(s.isna().sum()),
                "missing_pct": float(s.isna().mean() * 100),
                "unique": int(s.nunique(dropna=True)),
                "is_target": col == target,
            }
            if pd.api.types.is_numeric_dtype(s) and s.notna().any():
                desc = s.describe()
                entry.update({
                    "min": float(desc.get("min", np.nan)),
                    "max": float(desc.get("max", np.nan)),
                    "mean": float(desc.get("mean", np.nan)),
                    "std": float(desc.get("std", np.nan)) if not pd.isna(desc.get("std", np.nan)) else 0.0,
                    "median": float(s.median()),
                    "skew": float(s.skew()) if s.nunique() > 2 else 0.0,
                    "histogram": _histogram(s),
                })
            else:
                counts = s.astype(str).value_counts().head(8)
                entry["top_values"] = [{"value": str(k), "count": int(v)} for k, v in counts.items()]
            columns.append(entry)

        return {
            "rows": int(df.shape[0]),
            "n_columns": int(df.shape[1]),
            "memory_bytes": int(df.memory_usage(deep=True).sum()),
            "column_groups": groups,
            "columns": columns,
            "duplicate_rows": int(df.duplicated().sum()),
            "total_missing_cells": int(df.isna().sum().sum()),
        }

    # ------------------------------------------------------------------ checks
    def _missing(self, ctx: ProjectContext) -> None:
        missing = ctx.df.isna().mean().sort_values(ascending=False)
        for col, frac in missing.items():
            if frac == 0:
                continue
            pct = frac * 100
            if frac >= 0.6:
                sev = "critical"
                msg = f"'{col}' is {pct:.1f}% empty — imputation would invent most of the column."
            elif frac >= 0.2:
                sev = "warning"
                msg = f"'{col}' has {pct:.1f}% missing values; a missingness indicator will be added."
            else:
                sev = "info"
                msg = f"'{col}' has {pct:.1f}% missing values, imputed downstream."
            ctx.add_issue(sev, "missing_values", str(col), msg, stat=float(pct))

    def _duplicates_and_constants(self, ctx: ProjectContext) -> None:
        dupes = int(ctx.df.duplicated().sum())
        if dupes:
            ctx.add_issue("warning", "duplicates", None,
                          f"{dupes:,} exactly duplicated rows ({dupes / len(ctx.df) * 100:.2f}%) will be dropped.",
                          stat=float(dupes))
        for col in ctx.df.columns:
            if col == ctx.target_column:
                continue
            if ctx.df[col].nunique(dropna=False) <= 1:
                ctx.add_issue("info", "constant", str(col),
                              f"'{col}' holds a single value and carries no signal.")
            elif looks_like_identifier(ctx.df[col], str(col)):
                ctx.add_issue("info", "identifier", str(col),
                              f"'{col}' looks like a row identifier and will be excluded from modelling.")

    def _outliers(self, ctx: ProjectContext) -> None:
        numeric = ctx.df.select_dtypes(include=[np.number]).drop(
            columns=[ctx.target_column], errors="ignore")
        if numeric.empty:
            return
        per_column: Dict[str, float] = {}
        for col in numeric.columns:
            mask = iqr_outlier_mask(numeric[col].dropna())
            share = float(mask.mean() * 100) if len(mask) else 0.0
            per_column[str(col)] = share
            if share > 5:
                ctx.add_issue("warning", "outliers", str(col),
                              f"'{col}' has {share:.1f}% IQR outliers; winsorising at the 1st/99th percentile.",
                              stat=share)

        multivariate = 0.0
        subset = numeric.dropna()
        if len(subset) >= 50 and subset.shape[1] >= 2:
            forest = IsolationForest(contamination=config.OUTLIER_CONTAMINATION,
                                     random_state=config.RANDOM_STATE, n_estimators=100)
            flags = forest.fit_predict(subset.sample(min(len(subset), 20_000),
                                                     random_state=config.RANDOM_STATE))
            multivariate = float((flags == -1).mean() * 100)
        ctx.eda["outliers"] = {"per_column_pct": per_column, "multivariate_pct": multivariate}

    def _leakage(self, ctx: ProjectContext) -> None:
        """Three signals: suspicious naming, near-perfect correlation, single-feature separability."""
        target = ctx.df[ctx.target_column]
        from ..core.utils import LEAKY_HINTS

        suspects: List[Dict[str, Any]] = []
        for col in ctx.df.columns:
            if col == ctx.target_column:
                continue
            name = str(col).lower()
            reasons: List[str] = []

            if any(h in name for h in LEAKY_HINTS):
                reasons.append("name suggests it is recorded at or after the outcome")

            s = ctx.df[col]
            if pd.api.types.is_numeric_dtype(s) and pd.api.types.is_numeric_dtype(target):
                pair = pd.concat([s, target], axis=1).dropna()
                if len(pair) > 10:
                    corr = abs(float(pair.corr().iloc[0, 1]))
                    if corr >= config.LEAKAGE_CORRELATION_THRESHOLD:
                        reasons.append(f"|corr| with target is {corr:.3f}")

            if ctx.task_type == TaskType.CLASSIFICATION:
                score = _single_feature_separability(s, target)
                if score is not None and score >= config.LEAKAGE_AUC_THRESHOLD:
                    reasons.append(f"alone it separates the target at AUC {score:.3f}")

            if not pd.api.types.is_numeric_dtype(s) and s.nunique(dropna=True) > 1:
                grouped = pd.concat([s.astype(str), target.astype(str)], axis=1).dropna()
                if len(grouped) > 10:
                    purity = grouped.groupby(grouped.columns[0])[grouped.columns[1]].nunique()
                    if (purity == 1).mean() > 0.98 and s.nunique() < len(s) * 0.5:
                        reasons.append("each category maps to exactly one target value")

            if reasons:
                suspects.append({"column": str(col), "reasons": reasons})
                ctx.add_issue("critical", "leakage", str(col),
                              f"Possible target leakage in '{col}': " + "; ".join(reasons))

        ctx.eda["leakage_suspects"] = suspects

    def _correlations(self, ctx: ProjectContext) -> None:
        pairs = top_correlations(ctx.df.drop(columns=[ctx.target_column], errors="ignore"))
        ctx.eda["collinear_pairs"] = [{"a": a, "b": b, "corr": round(c, 4)} for a, b, c in pairs]
        for a, b, c in pairs[:5]:
            ctx.add_issue("info", "collinearity", f"{a}|{b}",
                          f"'{a}' and '{b}' are {c:.2f} correlated — redundant information.", stat=abs(c))

        if not ctx.target_column or ctx.target_column not in ctx.df.columns:
            return
        target = ctx.df[ctx.target_column]
        if pd.api.types.is_numeric_dtype(target):
            corr_to_target = (ctx.df.select_dtypes(include=[np.number])
                              .corrwith(target).drop(labels=[ctx.target_column], errors="ignore")
                              .dropna().sort_values(key=abs, ascending=False))
            ctx.eda["target_correlation"] = [
                {"feature": str(k), "corr": round(float(v), 4)} for k, v in corr_to_target.head(20).items()
            ]

    def _target_health(self, ctx: ProjectContext) -> None:
        target = ctx.df[ctx.target_column]
        missing_target = int(target.isna().sum())
        if missing_target:
            ctx.add_issue("critical", "target", ctx.target_column,
                          f"{missing_target:,} rows have no target value and will be dropped.",
                          stat=float(missing_target))

        if ctx.task_type == TaskType.CLASSIFICATION:
            counts = target.dropna().astype(str).value_counts()
            dist = (counts / counts.sum()).to_dict()
            ctx.eda["class_balance"] = [
                {"label": str(k), "count": int(v), "pct": round(float(v) / counts.sum() * 100, 2)}
                for k, v in counts.items()
            ]
            if len(counts) > 1:
                ratio = counts.min() / counts.max()
                if ratio < 0.1:
                    ctx.add_issue("critical", "imbalance", ctx.target_column,
                                  f"Severe class imbalance ({ratio:.3f} minority:majority). "
                                  "Accuracy is meaningless here — optimise PR-AUC/recall.", stat=float(ratio))
                elif ratio < 0.35:
                    ctx.add_issue("warning", "imbalance", ctx.target_column,
                                  f"Moderate class imbalance ({ratio:.2f}); class weighting will be enabled.",
                                  stat=float(ratio))
            ctx.eda["class_distribution"] = {str(k): float(v) for k, v in dist.items()}
        else:
            desc = target.dropna().describe()
            ctx.eda["target_summary"] = {k: float(v) for k, v in desc.items()}
            skew = float(target.dropna().skew())
            ctx.eda["target_skew"] = skew
            if abs(skew) > 2:
                ctx.add_issue("warning", "skew", ctx.target_column,
                              f"Target is heavily skewed (skew={skew:.2f}); a log transform may stabilise errors.",
                              stat=skew)

    # ------------------------------------------------------------------ eda payload
    def _eda(self, ctx: ProjectContext) -> Dict[str, Any]:
        df = ctx.df
        eda = dict(ctx.eda)
        numeric = df.select_dtypes(include=[np.number])
        corr = numeric.corr(numeric_only=True) if numeric.shape[1] >= 2 else pd.DataFrame()
        eda["correlation_matrix"] = {
            "columns": [str(c) for c in corr.columns],
            "values": [[round(float(v), 4) for v in row] for row in corr.to_numpy()],
        } if not corr.empty else {"columns": [], "values": []}
        eda["missing_by_column"] = [
            {"column": str(c), "pct": round(float(df[c].isna().mean() * 100), 3)}
            for c in df.columns if df[c].isna().any()
        ]
        eda["sample_rows"] = df.head(20).astype(object).where(pd.notna(df.head(20)), None).to_dict(orient="records")
        eda["numeric_distributions"] = [
            {"column": str(c), **_histogram(df[c])} for c in numeric.columns[:12]
        ]
        return eda


def _role_of(col: str, groups: Dict[str, List[str]]) -> str:
    for role, cols in groups.items():
        if col in cols:
            return role
    return "unknown"


def _histogram(series: pd.Series, bins: int = 20) -> Dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {"bins": [], "counts": []}
    counts, edges = np.histogram(clean, bins=min(bins, max(clean.nunique(), 1)))
    centers = (edges[:-1] + edges[1:]) / 2
    return {"bins": [round(float(c), 4) for c in centers], "counts": [int(c) for c in counts]}


def _single_feature_separability(feature: pd.Series, target: pd.Series) -> float | None:
    """AUC of the raw feature against a binarised target — a cheap leakage probe."""
    from sklearn.metrics import roc_auc_score

    pair = pd.concat([feature, target], axis=1).dropna()
    if len(pair) < 30:
        return None
    y = pair.iloc[:, 1]
    if y.nunique() != 2:
        return None
    x = pair.iloc[:, 0]
    if not pd.api.types.is_numeric_dtype(x):
        codes = x.astype(str).astype("category").cat.codes
        if codes.nunique() > 50:
            return None
        x = codes
    y_bin = (y == y.unique()[0]).astype(int)
    try:
        return float(max(roc_auc_score(y_bin, x), 1 - roc_auc_score(y_bin, x)))
    except Exception:
        return None
