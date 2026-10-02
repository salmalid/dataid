import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from backend.agents.data_cleaner import DataCleanerAgent
from backend.agents.feature_engineer import FeatureEngineerAgent
from backend.core.context import ProjectContext, TaskType
from backend.core.validation import reserve_holdout


class ValidationTests(unittest.TestCase):
    def test_holdout_cannot_change_cleaning_or_feature_statistics(self):
        with tempfile.TemporaryDirectory() as temp:
            df = pd.DataFrame({"amount": np.arange(100, dtype=float),
                               "balance": np.arange(100, dtype=float) ** 2,
                               "merchant": [f"shop-{i % 45}" for i in range(100)],
                               "label": [0, 1] * 50})
            df.loc[::6, "balance"] = np.nan
            ctx = ProjectContext(df, "label", task_type=TaskType.CLASSIFICATION, output_root=Path(temp))
            reserve_holdout(ctx)
            train_median = ctx.df.iloc[ctx.train_indices].balance.median()
            train_high = ctx.df.iloc[ctx.train_indices].amount.quantile(0.99)
            ctx.df.loc[ctx.test_indices, "amount"] = 1e12
            ctx.df.loc[ctx.test_indices, "balance"] = 1e15
            ctx.df.loc[ctx.test_indices, "merchant"] = "holdout-only"
            DataCleanerAgent().run(ctx)
            FeatureEngineerAgent().run(ctx)
            operations = ctx.feature_recipe["operations"]
            fill = next(op for op in operations if op["kind"] == "fill" and op["column"] == "balance")
            clip = next(op for op in operations if op["kind"] == "clip" and op["column"] == "amount")
            self.assertEqual(fill["value"], train_median)
            self.assertEqual(clip["high"], train_high)
            for op in operations:
                if op["kind"] == "frequency":
                    self.assertNotIn("holdout-only", op["values"])
            self.assertEqual(len(ctx.X_test), 20)

    def test_invalid_forecast_dates_fail_before_training(self):
        with tempfile.TemporaryDirectory() as temp:
            df = pd.DataFrame({"date": ["bad"] + list(pd.date_range("2024-01-01", periods=9)), "label": range(10)})
            ctx = ProjectContext(df, "label", task_type=TaskType.FORECASTING,
                                 time_column="date", output_root=Path(temp))
            with self.assertRaisesRegex(ValueError, "invalid dates"):
                reserve_holdout(ctx)
