"""Feature Engineer — datetime expansion, interactions, aggregates, then the sklearn preprocessor."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from ..core import config
from ..core.context import ProjectContext, TaskFamily, TaskType, family_of
from ..core.utils import split_columns
from .base import Agent


class FeatureEngineerAgent(Agent):
    name = "feature_engineer"
    label = "Feature Engineer"
    description = "Derives datetime parts, ratios, interactions and target-aware encodings."

    def run(self, ctx: ProjectContext) -> None:
        df = ctx.df
        self.operations = ctx.feature_recipe["operations"]
        first_feature_op = len(self.operations)
        created: List[str] = []

        # Forecasting is the one family where row order carries information, so it has to be
        # imposed before anything else touches the frame — the split below relies on it.
        if family_of(ctx.task_type) is TaskFamily.TEMPORAL:
            # Silently skipping the sort would leave _split_temporal slicing an unordered frame
            # and reporting a "chronological" holdout that is nothing of the kind.
            if ctx.time_column not in df.columns:
                raise ValueError(
                    f"Forecasting needs '{ctx.time_column}' to order rows by, but it is no longer "
                    "in the frame — an earlier agent dropped it. Check the cleaning log.")
            df = df.sort_values(ctx.time_column, kind="stable").reset_index(drop=True)
            ctx.df = df
            ctx.log(self.name, f"ordered rows by '{ctx.time_column}' for a chronological split")
            lagged = self._lag_features(df, ctx.target_column)
            # History-derived values are an explicit input contract for rolling forecasts.
            # A stateless endpoint must never guess an observation's preceding target values.
            ctx.feature_recipe["input_columns"].extend(lagged)
            ctx.feature_recipe["history_columns"] = lagged
            created += lagged
            ctx.log(self.name, f"added {len(lagged)} lag and rolling features")

        # The query id groups rows; it is not evidence about them. Pulled out before the
        # preprocessor is built, so the ColumnTransformer never expects it downstream.
        if family_of(ctx.task_type) is TaskFamily.RANKING and ctx.group_column in df.columns:
            self.operations[:] = [op for op in self.operations if op["column"] != ctx.group_column]
            ctx.group_values = df[ctx.group_column].astype(str).reset_index(drop=True)
            df = df.drop(columns=[ctx.group_column])
            ctx.df = df
            ctx.log(self.name, f"held '{ctx.group_column}' out of the features — it identifies "
                               "the query rather than describing the item")

        self.progress(ctx, "Expanding datetime columns", 0.15)
        full_frame = df.copy()
        df = df.iloc[ctx.train_indices].copy()
        created += self._expand_datetimes(df, ctx.target_column)

        self.progress(ctx, "Building interaction and ratio features", 0.35)
        created += self._interactions(df, ctx.target_column)

        self.progress(ctx, "Encoding high-cardinality categories", 0.5)
        created += self._frequency_encode(df, ctx.target_column)

        # Choose features and frequency mappings on training rows, then replay them unchanged.
        from ..core.inference import apply_operations
        transformed = apply_operations(full_frame, self.operations[first_feature_op:])
        ctx.df = transformed.loc[:, df.columns]
        self.progress(ctx, "Assembling the preprocessing pipeline", 0.7)
        preprocessor, groups = self._build_preprocessor(ctx)

        self.progress(ctx, "Splitting train and holdout", 0.85)
        self._split_and_fit(ctx, preprocessor)

        ctx.feature_summary = {
            "created_features": created,
            "n_created": len(created),
            "column_groups": groups,
            "n_features_out": len(ctx.feature_names),
            "feature_names": ctx.feature_names[:400],
            "train_rows": int(ctx.X_train.shape[0]),
            "test_rows": int(ctx.X_test.shape[0]),
        }

    # ------------------------------------------------------------------
    LAGS = (1, 2, 3, 7, 14)
    WINDOWS = (3, 7, 30)

    def _lag_features(self, df: pd.DataFrame, target: str) -> List[str]:
        """Past values of the target, which is what a forecast is actually built from.

        Every one is `shift(≥1)`, so a row only ever sees strictly earlier observations —
        without the shift these would be the purest form of leakage. The differences matter
        most: a tree cannot extrapolate a rising trend from the level alone, but it can learn
        a change that stays in the range it was trained on.
        """
        if not target or target not in df.columns:
            return []
        series = pd.to_numeric(df[target], errors="coerce")
        created: List[str] = []

        for lag in self.LAGS:
            if lag >= len(df):
                continue
            name = f"{target}__lag_{lag}"
            df[name] = series.shift(lag)
            created.append(name)

        for window in self.WINDOWS:
            if window >= len(df):
                continue
            shifted = series.shift(1)
            for stat in ("mean", "std"):
                name = f"{target}__roll_{stat}_{window}"
                df[name] = getattr(shifted.rolling(window, min_periods=1), stat)()
                created.append(name)

        if len(df) > 2:
            df[f"{target}__diff_1"] = series.diff().shift(1)
            created.append(f"{target}__diff_1")
            # a monotonic index so linear models can carry a trend past the training range
            # Not "__t_index": anything ending in "_index" trips the identifier heuristic in
            # utils.looks_like_identifier and gets dropped before the model ever sees it.
            df["elapsed_periods"] = np.arange(len(df), dtype=float)
            created.append("elapsed_periods")

        return created

    def _expand_datetimes(self, df: pd.DataFrame, target: str) -> List[str]:
        created: List[str] = []
        for col in list(df.columns):
            if col == target or not pd.api.types.is_datetime64_any_dtype(df[col]):
                continue
            s = df[col]
            parts = {
                f"{col}__year": s.dt.year,
                f"{col}__month": s.dt.month,
                f"{col}__day": s.dt.day,
                f"{col}__dayofweek": s.dt.dayofweek,
                f"{col}__quarter": s.dt.quarter,
                f"{col}__is_weekend": (s.dt.dayofweek >= 5).astype(int),
                f"{col}__days_since_epoch": (s - pd.Timestamp("1970-01-01")).dt.days,
            }
            for name, values in parts.items():
                if values.nunique(dropna=True) > 1:
                    df[name] = values.astype(float)
                    self.operations.append({"kind": "datepart", "column": col, "output": name, "part": name[len(col) + 2:]})
                    created.append(name)
            # cyclical encoding keeps December adjacent to January
            df[f"{col}__month_sin"] = np.sin(2 * np.pi * s.dt.month / 12)
            df[f"{col}__month_cos"] = np.cos(2 * np.pi * s.dt.month / 12)
            created += [f"{col}__month_sin", f"{col}__month_cos"]
            for part in ("month_sin", "month_cos"):
                self.operations.append({"kind": "datepart", "column": col, "output": f"{col}__{part}", "part": part})
            df.drop(columns=[col], inplace=True)
        return created

    def _interactions(self, df: pd.DataFrame, target: str) -> List[str]:
        numeric = [c for c in df.select_dtypes(include=[np.number]).columns
                   if c != target and not str(c).endswith("__was_missing")]
        if len(numeric) < 2:
            return []
        variances = df[numeric].var(numeric_only=True).sort_values(ascending=False)
        top = [str(c) for c in variances.head(4).index]
        created: List[str] = []
        for i, a in enumerate(top):
            for b in top[i + 1:]:
                prod = f"{a}__x__{b}"
                df[prod] = df[a] * df[b]
                self.operations.append({"kind": "product", "column": a, "other": b, "output": prod})
                created.append(prod)
                denom = df[b].replace(0, np.nan)
                if denom.notna().mean() > 0.9:
                    ratio = f"{a}__over__{b}"
                    df[ratio] = (df[a] / denom).replace([np.inf, -np.inf], np.nan).fillna(0.0)
                    self.operations.append({"kind": "ratio", "column": a, "other": b, "output": ratio})
                    created.append(ratio)
        for col in top[:3]:
            if (df[col] >= 0).all() and df[col].skew() > 1.5:
                name = f"{col}__log1p"
                df[name] = np.log1p(df[col])
                self.operations.append({"kind": "log", "column": col, "output": name})
                created.append(name)
        return created

    def _frequency_encode(self, df: pd.DataFrame, target: str) -> List[str]:
        created: List[str] = []
        for col in df.select_dtypes(include=["object", "category"]).columns:
            if col == target:
                continue
            card = df[col].nunique(dropna=True)
            if card > config.HIGH_CARDINALITY_THRESHOLD:
                freq = df[col].map(df[col].value_counts(normalize=True))
                name = f"{col}__freq"
                df[name] = freq.astype(float).fillna(0.0)
                self.operations.append({"kind": "frequency", "column": col, "output": name, "values": df[col].value_counts(normalize=True).to_dict()})
                created.append(name)
        return created

    # ------------------------------------------------------------------
    def _build_preprocessor(self, ctx: ProjectContext) -> Tuple[ColumnTransformer, Dict[str, List[str]]]:
        df = ctx.df.iloc[ctx.train_indices]
        groups = split_columns(df, ctx.target_column)
        numeric = [c for c in groups["numeric"]]
        low_card, high_card = [], []
        for col in groups["categorical"]:
            (high_card if df[col].nunique() > config.HIGH_CARDINALITY_THRESHOLD else low_card).append(col)

        transformers = []
        if numeric:
            transformers.append(("numeric", Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]), numeric))
        if low_card:
            transformers.append(("categorical", Pipeline([
                ("impute", SimpleImputer(strategy="most_frequent")),
                # drop="if_binary" collapses yes/no pairs to a single column. Without it a
                # binary category yields two perfectly collinear columns, which halves and
                # duplicates the coefficient on every linear model and fills the "top drivers"
                # list with mirrored pairs. Multi-level categories keep all their columns.
                ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=0.01,
                                         sparse_output=False, drop="if_binary")),
            ]), low_card))
        if high_card:
            transformers.append(("high_cardinality", Pipeline([
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("ordinal", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
            ]), high_card))

        if not transformers:
            raise ValueError("No usable feature columns remain after cleaning.")

        preprocessor = ColumnTransformer(transformers, remainder="drop", verbose_feature_names_out=False)
        return preprocessor, {"numeric": numeric, "low_cardinality": low_card,
                              "high_cardinality": high_card, "dropped": groups["identifier"] + groups["text"]}

    def _split_and_fit(self, ctx: ProjectContext, preprocessor: ColumnTransformer) -> None:
        if ctx.train_indices is not None:
            df = ctx.df
            X = df.drop(columns=[ctx.target_column], errors="ignore")
            y = df[ctx.target_column] if ctx.target_column else None
            if y is not None and ctx.task_type in {TaskType.CLASSIFICATION, TaskType.ANOMALY, TaskType.CLUSTERING}:
                y = y.astype(str)
            train, test = ctx.train_indices, ctx.test_indices
            if ctx.group_values is not None:
                ctx.groups_train = ctx.group_values.iloc[train].to_numpy()
                ctx.groups_test = ctx.group_values.iloc[test].to_numpy()
            self._assign(ctx, preprocessor, X.iloc[train], X.iloc[test],
                         y.iloc[train].to_numpy() if y is not None else None,
                         y.iloc[test].to_numpy() if y is not None else None)
            self._finalise(ctx, preprocessor)
            return
        raise ValueError("Reserve the holdout before feature engineering")

    def _assign(self, ctx: ProjectContext, preprocessor: ColumnTransformer,
                X_train: pd.DataFrame, X_test: pd.DataFrame,
                y_train, y_test) -> None:
        ctx.X_train = preprocessor.fit_transform(X_train)
        ctx.X_test = preprocessor.transform(X_test)
        ctx.y_train = y_train
        ctx.y_test = y_test
        ctx.raw_X_test = X_test.reset_index(drop=True)
        ctx.preprocessor = preprocessor

    def _finalise(self, ctx: ProjectContext, preprocessor: ColumnTransformer) -> None:
        try:
            ctx.feature_names = [str(n) for n in preprocessor.get_feature_names_out()]
        except Exception:
            ctx.feature_names = [f"f{i}" for i in range(ctx.X_train.shape[1])]
