"""Deployment — freezes the winning pipeline and emits everything needed to serve it."""
from __future__ import annotations

import json
import importlib.metadata
import shutil
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd

from ..core.context import ProjectContext, TaskType
from ..core.utils import coerce_json
from ..generators import (
    render_dockerfile,
    render_compose,
    render_inference_service,
    render_client_snippets,
    render_kubernetes,
    render_platform_configs,
)
from .base import Agent


class DeploymentAgent(Agent):
    name = "deployment"
    label = "Deployment Agent"
    description = "Packages the pipeline as a joblib bundle, a FastAPI service, a container and cloud manifests."

    def run(self, ctx: ProjectContext) -> None:
        out = ctx.artifacts_dir / "deploy"
        out.mkdir(parents=True, exist_ok=True)

        self.progress(ctx, "Freezing the model bundle", 0.2)
        bundle = {
            "preprocessor": ctx.preprocessor,
            "model": ctx.best_model,
            "feature_names": ctx.feature_names,
            "target": ctx.target_column,
            "task_type": ctx.task_type.value,
            "model_name": ctx.best_model_name,
            "input_columns": ctx.feature_recipe.get("input_columns", [c for c in ctx.df.columns if c != ctx.target_column]),
            "feature_recipe": ctx.feature_recipe,
        }
        model_path = out / "model.joblib"
        joblib.dump(bundle, model_path)
        ctx.register_artifact("model_bundle", model_path)

        self.progress(ctx, "Writing the input schema", 0.35)
        schema = self._schema(ctx)
        schema_path = out / "schema.json"
        schema_path.write_text(json.dumps(coerce_json(schema), indent=2), encoding="utf-8")
        ctx.register_artifact("schema", schema_path)

        self.progress(ctx, "Generating the FastAPI inference service", 0.5)
        (out / "app.py").write_text(render_inference_service(ctx, schema), encoding="utf-8")
        (out / "requirements.txt").write_text(self._requirements(ctx), encoding="utf-8")
        shutil.copyfile(Path(__file__).parents[1] / "core" / "inference.py", out / "inference.py")
        ctx.register_artifact("inference_runtime", out / "inference.py")
        ctx.register_artifact("inference_service", out / "app.py")

        self.progress(ctx, "Generating container and orchestration files", 0.7)
        (out / "Dockerfile").write_text(render_dockerfile(ctx), encoding="utf-8")
        (out / "docker-compose.yml").write_text(render_compose(ctx), encoding="utf-8")
        (out / "k8s-deployment.yaml").write_text(render_kubernetes(ctx), encoding="utf-8")
        ctx.register_artifact("dockerfile", out / "Dockerfile")
        ctx.register_artifact("kubernetes", out / "k8s-deployment.yaml")

        self.progress(ctx, "Generating platform configs and client snippets", 0.85)
        for filename, content in render_platform_configs(ctx).items():
            (out / filename).write_text(content, encoding="utf-8")
        (out / "CLIENTS.md").write_text(render_client_snippets(ctx, schema), encoding="utf-8")
        archive = shutil.make_archive(str(ctx.artifacts_dir / "deployment"), "zip", root_dir=out)
        ctx.register_artifact("deployment_archive", Path(archive))

        latency = self._benchmark(ctx)
        ctx.deployment = {
            "model_path": str(model_path),
            "schema_path": str(schema_path),
            "artifacts_dir": str(out),
            "image_name": f"dataid/{ctx.run_id}:latest",
            "endpoints": [
                {"method": "GET", "path": "/health", "description": "Liveness probe"},
                {"method": "GET", "path": "/schema", "description": "Expected input columns and types"},
                {"method": "POST", "path": "/predict", "description": "Score a single record"},
                {"method": "POST", "path": "/predict/batch", "description": "Score up to 10,000 records"},
                {"method": "GET", "path": "/metrics", "description": "Prometheus-style counters"},
            ],
            "targets": ["Docker", "Kubernetes", "AWS App Runner", "Render", "Railway", "Azure Container Apps"],
            "latency": latency,
            "model_size_bytes": int(model_path.stat().st_size),
            "run_command": "uvicorn app:app --host 0.0.0.0 --port 8080",
            "docker_command": f"docker build -t dataid/{ctx.run_id} . && "
                              f"docker run -p 8080:8080 dataid/{ctx.run_id}",
        }

    # ------------------------------------------------------------------
    def _schema(self, ctx: ProjectContext) -> Dict[str, Any]:
        fields = []
        columns = ctx.feature_recipe.get("input_columns", [c for c in ctx.df.columns if c != ctx.target_column])
        for col in columns:
            s = ctx.raw_df[col] if col in ctx.raw_df else ctx.df[col]
            if pd.api.types.is_numeric_dtype(s):
                kind, example = "number", float(s.median())
            elif pd.api.types.is_datetime64_any_dtype(s):
                kind, example = "string", str(s.dropna().iloc[0]) if s.notna().any() else ""
            else:
                mode = s.mode(dropna=True)
                kind, example = "string", str(mode.iloc[0]) if not mode.empty else ""
            fields.append({"name": str(col), "type": kind, "required": True,
                           "example": example})
        return {
            "model": ctx.best_model_name,
            "task_type": ctx.task_type.value,
            "target": ctx.target_column,
            "fields": fields,
            "input_columns": columns,
            "history_columns": ctx.feature_recipe.get("history_columns", []),
            "online_inference": hasattr(ctx.best_model, "predict"),
            "example_payload": {f["name"]: f["example"] for f in fields},
        }

    def _requirements(self, ctx: ProjectContext) -> str:
        packages = ["scikit-learn", "pandas", "numpy", "scipy", "joblib"]
        model_package = type(ctx.best_model).__module__.split(".")[0]
        if model_package in {"xgboost", "lightgbm", "catboost"}:
            packages.append(model_package)
        return "\n".join([
            "fastapi>=0.110",
            "uvicorn[standard]>=0.27",
            *[f"{name}=={importlib.metadata.version(name)}" for name in packages],
            "pydantic>=2.6",
            "",
        ])

    def _benchmark(self, ctx: ProjectContext) -> Dict[str, Any]:
        import time

        sample = ctx.X_test[: min(len(ctx.X_test), 1000)]
        if len(sample) == 0:
            return {}
        # DBSCAN, Agglomerative, Spectral and Mean Shift expose only fit_predict: they cannot
        # assign an unseen point without refitting. That is a property of the algorithm, not a
        # failure, so it is reported rather than raised — but the bundle cannot serve online.
        if not hasattr(ctx.best_model, "predict"):
            ctx.log(self.name,
                    f"{ctx.best_model_name} has no predict(); it cannot score new rows without "
                    "refitting, so no inference latency is reported")
            return {"online_inference": False,
                    "reason": f"{ctx.best_model_name} must be refitted to label new data"}
        timings = []
        for _ in range(5):
            start = time.perf_counter()
            ctx.best_model.predict(sample)
            timings.append((time.perf_counter() - start) / len(sample) * 1000)
        arr = np.array(timings)
        return {
            "p50_ms_per_row": round(float(np.percentile(arr, 50)), 4),
            "p95_ms_per_row": round(float(np.percentile(arr, 95)), 4),
            "throughput_rows_per_sec": round(float(1000 / max(arr.mean(), 1e-6)), 1),
        }
