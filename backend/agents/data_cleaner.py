"""Data Cleaner — acts on every issue the Detective raised."""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ..core.context import ProjectContext, TaskType
from ..core.utils import looks_like_datetime, looks_like_identifier
from .base import Agent


class DataCleanerAgent(Agent):
    name = "data_cleaner"
    label = "Data Cleaner"
    description = "Drops junk columns, repairs types, imputes missing values and tames outliers."

    def run(self, ctx: ProjectContext) -> None:
        from ..core.validation import reserve_holdout
        from ..core.inference import apply_operations
        reserve_holdout(ctx)
        whole = ctx.df.copy()
        df = whole.iloc[ctx.train_indices].copy()
        # Query IDs are structural, and must not be clipped, imputed or normalised.
        if ctx.group_column:
            df = df.drop(columns=[ctx.group_column])
        self.operations = ctx.feature_recipe["operations"]
        actions: List[Dict[str, Any]] = []
        before_shape = ctx.raw_df.shape
        removed = len(ctx.raw_df) - len(whole)
        if removed:
            actions.append({"action": "drop_rows", "detail": f"{removed} duplicate or invalid-target rows removed before splitting"})

        self.progress(ctx, "Dropping rows without a target", 0.1)
        # Unsupervised runs have no target column to be missing from.
        if ctx.target_column and ctx.target_column in df.columns:
            missing_target = int(df[ctx.target_column].isna().sum())
            if missing_target:
                df = df[df[ctx.target_column].notna()].copy()
                actions.append({"action": "drop_rows",
                                "detail": f"{missing_target} rows missing the target"})

        self.progress(ctx, "Removing duplicates", 0.2)
        dupes = int(df.duplicated().sum())
        if dupes:
            df = df.drop_duplicates().reset_index(drop=True)
            actions.append({"action": "drop_duplicates", "detail": f"{dupes} exact duplicate rows"})

        self.progress(ctx, "Dropping unusable columns", 0.3)
        dropped = self._drop_columns(ctx, df)
        if dropped:
            df = df.drop(columns=dropped)
            actions.append({"action": "drop_columns", "detail": ", ".join(dropped)})

        ctx.feature_recipe["input_columns"] = [c for c in df.columns
                                               if c not in {ctx.target_column, ctx.group_column}]
        for col in df.columns:
            if col == ctx.target_column:
                continue
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                self.operations.append({"kind": "datetime", "column": col})
            elif pd.api.types.is_numeric_dtype(df[col]):
                self.operations.append({"kind": "numeric", "column": col})

        self.progress(ctx, "Repairing column types", 0.45)
        converted = self._fix_types(df, ctx.target_column)
        if converted:
            actions.append({"action": "convert_types", "detail": ", ".join(converted)})

        self.progress(ctx, "Flagging and imputing missing values", 0.6)
        indicators, imputed = self._impute(df, ctx.target_column)
        if indicators:
            actions.append({"action": "missing_indicator", "detail": ", ".join(indicators)})
        if imputed:
            actions.append({"action": "impute", "detail": ", ".join(imputed)})

        self.progress(ctx, "Winsorising extreme values", 0.75)
        winsorised = self._winsorise(df, ctx.target_column)
        if winsorised:
            actions.append({"action": "winsorise", "detail": ", ".join(winsorised)})

        self.progress(ctx, "Normalising text categories", 0.9)
        normalised = self._normalise_categories(df, ctx.target_column)
        if normalised:
            actions.append({"action": "normalise_text", "detail": ", ".join(normalised)})

        ctx.df = apply_operations(whole.drop(columns=dropped), self.operations)
        ctx.cleaning_summary = {
            "shape_before": list(before_shape),
            "shape_after": list(ctx.df.shape),
            "rows_removed": int(before_shape[0] - ctx.df.shape[0]),
            # The cleaner both drops columns and adds missingness indicators, so the net
            # difference goes negative and reads as "removed -2". Report what was actually
            # dropped and let the added columns show up as their own count.
            "columns_removed": len(dropped),
            "columns_added": int(max(ctx.df.shape[1] - before_shape[1] + len(dropped), 0)),
            "dropped_columns": dropped,
            "actions": actions,
            "remaining_missing": int(ctx.df.isna().sum().sum()),
        }

    # ------------------------------------------------------------------
    def _drop_columns(self, ctx: ProjectContext, df: pd.DataFrame) -> List[str]:
        drop: List[str] = []
        leakage_cols = {i.column for i in ctx.issues if i.category == "leakage" and i.column}
        # The user declared these as structural: the column a forecast is ordered by and the
        # one that defines a ranking query. Dropping either silently breaks the split.
        protected = {ctx.target_column, ctx.time_column, ctx.group_column} - {None}
        for col in df.columns:
            if col in protected:
                continue
            s = df[col]
            if s.isna().mean() >= 0.6:
                drop.append(str(col))
            elif s.nunique(dropna=False) <= 1:
                drop.append(str(col))
            elif looks_like_identifier(s, str(col)):
                drop.append(str(col))
            elif col in leakage_cols:
                drop.append(str(col))
        return sorted(set(drop))

    def _fix_types(self, df: pd.DataFrame, target: str) -> List[str]:
        converted: List[str] = []
        for col in list(df.columns):
            if col == target:
                continue
            s = df[col]
            if not (pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s)):
                continue
            if looks_like_datetime(s, str(col)):
                parsed = pd.to_datetime(s, errors="coerce", format="mixed")
                if parsed.notna().mean() > 0.7:
                    df[col] = parsed
                    self.operations.append({"kind": "datetime", "column": col})
                    converted.append(f"{col}->datetime")
                    continue
            stripped = s.astype(str).str.replace(r"[,$%\s]", "", regex=True)
            numeric = pd.to_numeric(stripped, errors="coerce")
            if numeric.notna().mean() > 0.9 and s.notna().mean() > 0:
                df[col] = numeric
                self.operations.append({"kind": "numeric", "column": col})
                converted.append(f"{col}->numeric")
        return converted

    def _impute(self, df: pd.DataFrame, target: str) -> tuple[List[str], List[str]]:
        indicators: List[str] = []
        imputed: List[str] = []
        for col in list(df.columns):
            if col == target:
                continue
            s = df[col]
            frac = s.isna().mean()
            if frac == 0:
                continue
            if frac >= 0.05:
                df[f"{col}__was_missing"] = s.isna().astype(int)
                self.operations.append({"kind": "indicator", "column": col, "output": f"{col}__was_missing"})
                indicators.append(str(col))
            if pd.api.types.is_numeric_dtype(s):
                fill = float(s.median())
                df[col] = s.fillna(fill)
                self.operations.append({"kind": "fill", "column": col, "value": fill})
                imputed.append(f"{col}=median({fill:.4g})")
            elif pd.api.types.is_datetime64_any_dtype(s):
                df[col] = s.fillna(s.median())
                self.operations.append({"kind": "fill", "column": col, "value": s.median()})
                imputed.append(f"{col}=median date")
            else:
                mode = s.mode(dropna=True)
                fill = mode.iloc[0] if not mode.empty else "unknown"
                df[col] = s.fillna(fill)
                self.operations.append({"kind": "fill", "column": col, "value": fill})
                imputed.append(f"{col}=mode({fill})")
        return indicators, imputed

    def _winsorise(self, df: pd.DataFrame, target: str) -> List[str]:
        touched: List[str] = []
        numeric = df.select_dtypes(include=[np.number]).columns.drop(target, errors="ignore")
        for col in numeric:
            if col.endswith("__was_missing"):
                continue
            s = df[col]
            if s.nunique() < 10:
                continue
            lo, hi = s.quantile(0.01), s.quantile(0.99)
            if lo == hi:
                continue
            clipped = s.clip(lo, hi)
            if not clipped.equals(s):
                df[col] = clipped
                self.operations.append({"kind": "clip", "column": col, "low": lo, "high": hi})
                touched.append(str(col))
        return touched

    def _normalise_categories(self, df: pd.DataFrame, target: str) -> List[str]:
        touched: List[str] = []
        for col in df.select_dtypes(include=["object"]).columns:
            if col == target:
                continue
            s = df[col].astype(str).str.strip()
            lowered = s.str.lower()
            self.operations.append({"kind": "text", "column": col, "lower": lowered.nunique() < s.nunique()})
            # only collapse case when it actually merges variants
            if lowered.nunique() < s.nunique():
                df[col] = lowered
                touched.append(str(col))
            else:
                df[col] = s
        return touched
