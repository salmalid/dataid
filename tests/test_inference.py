import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

os.environ["DATAID_LLM_PROVIDER"] = "none"

import joblib
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from backend.agents.data_cleaner import DataCleanerAgent
from backend.agents.feature_engineer import FeatureEngineerAgent
from backend.agents.deployment import DeploymentAgent
from backend.core.context import ProjectContext, TaskType
from backend.core.inference import prepare_frame, score_records


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        rng = np.random.default_rng(42)
        n = 180
        self.raw = pd.DataFrame({
            "amount": rng.exponential(10, n),
            "balance": rng.normal(100, 20, n),
            "segment": [" North ", "north", "South"] * (n // 3),
            "merchant": [f"shop-{i % 50}" for i in range(n)],
            "signup_date": pd.date_range("2023-01-01", periods=n).astype(str),
            "label": rng.integers(0, 2, n),
        })
        self.raw.loc[::8, "balance"] = np.nan

    def build(self, task=TaskType.CLASSIFICATION):
        raw = self.raw.copy()
        kwargs = {}
        if task == TaskType.RANKING:
            raw["query"] = [f"q-{i // 6}" for i in range(len(raw))]
            kwargs["group_column"] = "query"
        if task == TaskType.FORECASTING:
            raw["signup_date"] = pd.to_datetime(raw["signup_date"])
            kwargs["time_column"] = "signup_date"
        ctx = ProjectContext(raw, "label", task_type=task,
                             output_root=Path(self.temp.name), **kwargs)
        DataCleanerAgent().run(ctx)
        FeatureEngineerAgent().run(ctx)
        cls = RandomForestClassifier if task == TaskType.CLASSIFICATION else RandomForestRegressor
        ctx.best_model = cls(n_estimators=5, random_state=42).fit(ctx.X_train, ctx.y_train)
        ctx.best_model_name = "test forest"
        DeploymentAgent().run(ctx)
        bundle = joblib.load(ctx.artifacts_dir / "deploy/model.joblib")
        return ctx, bundle

    def test_raw_features_match_training_and_serialized_bundle(self):
        ctx, bundle = self.build()
        records = self.raw.drop(columns="label").to_dict("records")
        actual = ctx.preprocessor.transform(prepare_frame(bundle, records))
        expected = ctx.preprocessor.transform(ctx.df)
        np.testing.assert_allclose(actual, expected, atol=1e-12)
        self.assertEqual(score_records(bundle, records[:1]), score_records(bundle, records[:8])[:1])
        self.assertTrue(any(op["kind"] == "indicator" for op in bundle["feature_recipe"]["operations"]))

    def test_missing_key_in_individual_batch_record_is_rejected(self):
        _, bundle = self.build()
        records = self.raw.iloc[:2].to_dict("records")
        del records[1][bundle["input_columns"][0]]
        with self.assertRaisesRegex(ValueError, "record 1: missing"):
            score_records(bundle, records)

    def test_explicit_null_category_remains_missing_for_imputer(self):
        _, bundle = self.build()
        record = self.raw.iloc[0].to_dict()
        record["segment"] = None
        frame = prepare_frame(bundle, [record])
        self.assertTrue(pd.isna(frame.iloc[0]["segment"]))
        self.assertEqual(len(score_records(bundle, [record])), 1)

    def test_deployment_archive_is_self_contained(self):
        import zipfile
        ctx, _ = self.build()
        with zipfile.ZipFile(ctx.artifacts["deployment_archive"]) as archive:
            self.assertTrue({"model.joblib", "app.py", "inference.py", "requirements.txt", "schema.json", "Dockerfile", "CLIENTS.md"}.issubset(archive.namelist()))

    def test_generated_service_and_control_plane_agree(self):
        ctx, bundle = self.build()
        deploy = ctx.artifacts_dir / "deploy"
        sys.path.insert(0, str(deploy))
        self.addCleanup(sys.path.remove, str(deploy))
        spec = importlib.util.spec_from_file_location("generated_app", deploy / "app.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(module)
        client = TestClient(module.app)
        record = self.raw.iloc[0].where(self.raw.iloc[0].notna(), None).to_dict()
        from backend.api.main import _score
        expected = _score(bundle, [record])[0]
        response = client.post("/predict", json={"record": record})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["prediction"], expected["prediction"])
        self.assertEqual(client.get("/schema").json()["input_columns"], bundle["input_columns"])
        self.assertEqual(client.post("/predict", json={"record": {}}).status_code, 400)
        self.assertEqual(client.post("/predict/batch", json={"records": [record, {}]}).status_code, 400)
        self.assertEqual(client.post("/predict/batch", json={"records": []}).status_code, 400)

    def test_ranking_excludes_query_id(self):
        ctx, bundle = self.build(TaskType.RANKING)
        self.assertNotIn("query", bundle["input_columns"])
        actual = ctx.preprocessor.transform(prepare_frame(bundle, self.raw.to_dict("records")))
        np.testing.assert_allclose(actual, ctx.preprocessor.transform(ctx.df))

    def test_forecasting_history_is_explicit_and_reproducible(self):
        ctx, bundle = self.build(TaskType.FORECASTING)
        raw = self.raw.copy()
        for col in bundle["feature_recipe"]["history_columns"]:
            raw[col] = ctx.df[col]
        actual = ctx.preprocessor.transform(prepare_frame(bundle, raw.to_dict("records")))
        np.testing.assert_allclose(actual, ctx.preprocessor.transform(ctx.df))
        with self.assertRaisesRegex(ValueError, "missing required"):
            score_records(bundle, self.raw.iloc[:1].to_dict("records"))


if __name__ == "__main__":
    unittest.main()
