"""Source templates emitted by the Deployment agent."""
from __future__ import annotations

import json
from typing import Any, Dict


def render_inference_service(ctx, schema: Dict[str, Any]) -> str:
    example = repr(schema["example_payload"])
    return f'''"""dataid inference service for run {ctx.run_id}.

Generated automatically. Serves the exact preprocessor + model bundle that produced
the reported holdout metrics.

    uvicorn app:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import time
from collections import Counter, deque
from pathlib import Path
from typing import Any, Dict, List

from inference import score_records
import json
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BUNDLE_PATH = Path(__file__).parent / "model.joblib"
BUNDLE = joblib.load(BUNDLE_PATH)

PREPROCESSOR = BUNDLE["preprocessor"]
MODEL = BUNDLE["model"]
INPUT_COLUMNS: List[str] = BUNDLE["input_columns"]
TARGET = BUNDLE["target"]
TASK_TYPE = BUNDLE["task_type"]
MODEL_NAME = BUNDLE["model_name"]

COUNTERS = Counter()
LATENCIES = deque(maxlen=1000)

app = FastAPI(
    title={f"dataid — {ctx.best_model_name} serving {ctx.target_column}"!r},
    version="1.0.0",
    description="Auto-generated inference API. Run {ctx.run_id}.",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class PredictRequest(BaseModel):
    record: Dict[str, Any] = Field(..., description="One row keyed by input column name")

    model_config = {{
        "json_schema_extra": {{
            "example": {{"record": {example}}}
        }}
    }}


class BatchRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(..., max_length=10_000)


def _score(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return score_records(BUNDLE, records)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {{"status": "ok", "model": MODEL_NAME, "task_type": TASK_TYPE, "target": TARGET}}


@app.get("/schema")
def get_schema() -> Dict[str, Any]:
    return json.loads((BUNDLE_PATH.parent / "schema.json").read_text(encoding="utf-8"))


@app.post("/predict")
def predict(request: PredictRequest) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        result = _score([request.record])[0]
    except Exception as exc:  # noqa: BLE001
        COUNTERS["errors"] += 1
        raise HTTPException(status_code=400, detail=f"scoring failed: {{exc}}") from exc
    elapsed = (time.perf_counter() - started) * 1000
    LATENCIES.append(elapsed)
    COUNTERS["predictions"] += 1
    return {{**result, "latency_ms": round(elapsed, 3)}}


@app.post("/predict/batch")
def predict_batch(request: BatchRequest) -> Dict[str, Any]:
    if not request.records:
        raise HTTPException(status_code=400, detail="records must not be empty")
    started = time.perf_counter()
    try:
        results = _score(request.records)
    except Exception as exc:  # noqa: BLE001
        COUNTERS["errors"] += 1
        raise HTTPException(status_code=400, detail=f"scoring failed: {{exc}}") from exc
    elapsed = (time.perf_counter() - started) * 1000
    LATENCIES.append(elapsed / max(len(request.records), 1))
    COUNTERS["predictions"] += len(request.records)
    return {{"count": len(results), "results": results, "latency_ms": round(elapsed, 3)}}


@app.get("/metrics")
def metrics() -> Dict[str, Any]:
    window = list(LATENCIES)
    average = sum(window) / len(window) if window else 0.0
    return {{
        "predictions_total": COUNTERS["predictions"],
        "errors_total": COUNTERS["errors"],
        "latency_ms_avg": round(average, 3),
        "latency_ms_max": round(max(window), 3) if window else 0.0,
    }}
'''


def render_dockerfile(ctx) -> str:
    return f"""# dataid deployment image — run {ctx.run_id}
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \\
 && apt-get install -y --no-install-recommends libgomp1 curl \\
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY model.joblib schema.json app.py inference.py ./

RUN useradd --create-home --uid 10001 dataid && chown -R dataid:dataid /app
USER dataid

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \\
  CMD curl -fsS http://localhost:8080/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
"""


def render_compose(ctx) -> str:
    return f"""version: "3.9"

services:
  inference:
    build: .
    image: dataid/{ctx.run_id}:latest
    container_name: dataid-{ctx.run_id}
    ports:
      - "8080:8080"
    environment:
      - MODEL_NAME={ctx.best_model_name}
      - TARGET={ctx.target_column}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G
"""


def render_kubernetes(ctx) -> str:
    slug = f"dataid-{ctx.run_id}"
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {slug}
  labels:
    app: {slug}
    dataid.run: "{ctx.run_id}"
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {slug}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: {slug}
    spec:
      containers:
        - name: inference
          image: dataid/{ctx.run_id}:latest
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: {slug}
spec:
  selector:
    app: {slug}
  ports:
    - port: 80
      targetPort: 8080
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {slug}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {slug}
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
"""


def render_platform_configs(ctx) -> Dict[str, str]:
    slug = f"dataid-{ctx.run_id}"
    return {
        "render.yaml": f"""services:
  - type: web
    name: {slug}
    runtime: docker
    dockerfilePath: ./Dockerfile
    plan: starter
    healthCheckPath: /health
    envVars:
      - key: MODEL_NAME
        value: {ctx.best_model_name}
""",
        "railway.json": json.dumps({
            "$schema": "https://railway.app/railway.schema.json",
            "build": {"builder": "DOCKERFILE", "dockerfilePath": "Dockerfile"},
            "deploy": {
                "startCommand": "uvicorn app:app --host 0.0.0.0 --port $PORT",
                "healthcheckPath": "/health",
                "healthcheckTimeout": 30,
                "restartPolicyType": "ON_FAILURE",
            },
        }, indent=2),
        "apprunner.yaml": f"""version: 1.0
runtime: docker
build:
  commands:
    build:
      - echo "built by dataid run {ctx.run_id}"
run:
  command: uvicorn app:app --host 0.0.0.0 --port 8080
  network:
    port: 8080
  env:
    - name: MODEL_NAME
      value: {ctx.best_model_name}
""",
        "azure-container-app.yaml": f"""properties:
  configuration:
    ingress:
      external: true
      targetPort: 8080
  template:
    containers:
      - name: {slug}
        image: dataid/{ctx.run_id}:latest
        resources:
          cpu: 0.5
          memory: 1Gi
        probes:
          - type: Liveness
            httpGet:
              path: /health
              port: 8080
    scale:
      minReplicas: 1
      maxReplicas: 10
""",
    }


def render_client_snippets(ctx, schema: Dict[str, Any]) -> str:
    payload = json.dumps({"record": schema["example_payload"]}, indent=2, default=str)
    js_payload = json.dumps(schema["example_payload"], indent=2, default=str)
    return f"""# Calling the {ctx.best_model_name} endpoint

Predicting `{ctx.target_column}` — dataid run `{ctx.run_id}`.

## curl

```bash
curl -X POST http://localhost:8080/predict \\
  -H 'Content-Type: application/json' \\
  -d '{json.dumps({"record": schema["example_payload"]}, default=str)}'
```

## Python

```python
import requests

response = requests.post(
    "http://localhost:8080/predict",
    json={payload},
    timeout=10,
)
response.raise_for_status()
print(response.json())
```

## TypeScript

```ts
const response = await fetch("http://localhost:8080/predict", {{
  method: "POST",
  headers: {{ "Content-Type": "application/json" }},
  body: JSON.stringify({{ record: {js_payload} }}),
}});

if (!response.ok) throw new Error(`inference failed: ${{response.status}}`);
const result = await response.json();
```

## Batch

`POST /predict/batch` accepts `{{"records": [...]}}` with up to 10,000 rows and returns
one result per row in the same order.
"""
