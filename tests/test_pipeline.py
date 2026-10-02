import os
os.environ["DATAID_LLM_PROVIDER"] = "none"

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, IsolationForest
from sklearn.cluster import KMeans

from backend.agents.model_zoo import Candidate
from backend.core.orchestrator import Pipeline


class PipelineTests(unittest.TestCase):
    def test_all_six_task_families_complete_offline(self):
        rng = np.random.default_rng(7)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for task in ("classification", "regression", "forecasting", "ranking", "clustering", "anomaly"):
                with self.subTest(task=task):
                    n = 150
                    df = pd.DataFrame({"balance": rng.normal(100, 10, n), "amount": rng.exponential(4, n),
                                       "region": ["north", "south", "east"] * 50})
                    kwargs = {"target_column": "target"}
                    df["target"] = df.balance * 0.2 + rng.normal(0, 4, n)
                    builder = lambda: RandomForestRegressor(n_estimators=5, random_state=7)
                    if task == "classification":
                        df["target"] = (df.target > df.target.median()).astype(int)
                        builder = lambda: RandomForestClassifier(n_estimators=5, random_state=7)
                    elif task == "forecasting":
                        df["date"] = pd.date_range("2024-01-01", periods=n)
                        kwargs["time_column"] = "date"
                    elif task == "ranking":
                        df["query"] = [f"q{i//5}" for i in range(n)]
                        df["target"] = rng.integers(0, 5, n)
                        kwargs["group_column"] = "query"
                    elif task in {"clustering", "anomaly"}:
                        kwargs = {}
                        df = df.drop(columns="target")
                        builder = (lambda: KMeans(n_clusters=3, random_state=7, n_init=2)) if task == "clustering" else (lambda: IsolationForest(n_estimators=10, random_state=7))
                    path = root / f"{task}.csv"
                    df.to_csv(path, index=False)
                    candidate = Candidate("test", "Test model", "test", builder)
                    with patch("backend.agents.model_zoo.candidates_for", return_value=[candidate]):
                        result = Pipeline(path, task_type=task, output_root=root, artifacts=["report", "dashboard", "notebook", "deck"], **kwargs).run()
                    self.assertEqual(result["status"], "success", result.get("error"))
                    self.assertIn("deployment_archive", result["artifacts"])
                    self.assertIn("dashboard", result["artifacts"])
                    self.assertIn("notebook", result["artifacts"])
                    self.assertIn("deck", result["artifacts"])
                    self.assertLess(result["monitoring"]["reference"]["captured_rows"], n)
                    for artifact in result["artifacts"].values():
                        self.assertTrue(Path(artifact).is_file())


if __name__ == "__main__":
    unittest.main()
