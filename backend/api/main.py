"""dataid control plane.

    uvicorn backend.api.main:app --reload --port 8000
"""
from __future__ import annotations

import json
import time
import uuid
import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse, JSONResponse

from ..core import commands, config, store
from ..core.events import BUS
from ..core.llm import get_llm
from ..core.context import TaskType, requires_target
from ..core.orchestrator import (
    AGENT_CATALOG,
    ARTIFACT_CATALOG,
    TASK_CATALOG,
    load_dataset,
    understand_dataset,
)
from ..core.utils import coerce_json, psi, psi_observed
from . import runner
from .schemas import (
    ApiKeyCreate,
    BatchPredictRequest,
    ChatRequest,
    DriftCheckRequest,
    PredictRequest,
    ProjectCreate,
    ProjectUpdate,
    PromoteRequest,
    RunCreate,
    SessionCreate,
)

ALLOWED_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".parquet", ".json", ".jsonl"}
MAX_UPLOAD_BYTES = 512 * 1024 * 1024

@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init_db()
    store.recover_interrupted_runs()
    yield


app = FastAPI(
    title="dataid API",
    version="1.0.0",
    description="The AI operating system for data scientists — multi-agent AutoML control plane.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- meta
def _authenticate(token: str):
    if config.ADMIN_TOKEN and hmac.compare_digest(token, config.ADMIN_TOKEN):
        return {"id": "admin", "scopes": ["read", "write"]}
    return store.authenticate_api_key(token) if token else None


@app.middleware("http")
async def api_auth(request: Request, call_next):
    if (not request.url.path.startswith("/api/") or request.method == "OPTIONS"
            or request.url.path in {"/api/health", "/api/session"}):
        return await call_next(request)
    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ") if authorization else request.cookies.get("dataid_session", "")
    if not token and not config.REQUIRE_API_KEY:
        return await call_next(request)
    key = _authenticate(token)
    if not key:
        return JSONResponse({"detail": "A valid API key is required. Connect in Settings."}, status_code=401)
    scope = "read" if request.method in {"GET", "HEAD"} else "write"
    if scope not in key["scopes"]:
        return JSONResponse({"detail": f"This key requires the {scope} scope."}, status_code=403)
    return await call_next(request)


@app.post("/api/session")
def create_session(body: SessionCreate, request: Request):
    key = _authenticate(body.token)
    if not key:
        raise HTTPException(401, "Invalid or revoked API key")
    response = JSONResponse({"connected": True, "scopes": key["scopes"]})
    response.set_cookie("dataid_session", body.token, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https", max_age=28800)
    return response


@app.delete("/api/session")
def delete_session():
    response = JSONResponse({"connected": False})
    response.delete_cookie("dataid_session")
    return response


@app.get("/api/health")
def health() -> Dict[str, Any]:
    from ..agents import model_zoo

    return {
        "status": "ok",
        "llm_provider": get_llm().name,
        "boosting_libraries": model_zoo.availability(),
        "active_runs": len(runner.active_runs()),
    }


@app.get("/api/agents")
def agents() -> Dict[str, Any]:
    return {"agents": AGENT_CATALOG, "commands": commands.catalog(),
            "artifacts": ARTIFACT_CATALOG, "tasks": TASK_CATALOG}


@app.get("/api/stats")
def stats() -> Dict[str, Any]:
    return {**store.workspace_stats(), "active_runs": runner.active_runs()}


@app.get("/api/showcase")
def showcase() -> Dict[str, Any]:
    """A real completed run, for the landing page to display instead of invented numbers.

    Prefers the most recent run that has both a leaderboard and attribution, so the page
    shows a full picture. Returns available=False when nothing has been run yet, which the
    page renders as an empty state rather than substituting example figures.
    """
    runs = store.recent_successful_runs(10)

    def scored(run: Dict[str, Any]) -> tuple:
        result = run.get("result") or {}
        return (bool(result.get("leaderboard")),
                bool((result.get("explainability") or {}).get("global_importance")))

    chosen = next((r for r in runs if all(scored(r))), None) or next(
        (r for r in runs if scored(r)[0]), None)
    if not chosen:
        return {"available": False}

    result = chosen.get("result") or {}
    metric = chosen.get("primary_metric") or "accuracy"
    board = [
        {"label": row.get("model"), "value": row.get(metric)}
        for row in (result.get("leaderboard") or [])
        if row.get("model") is not None and isinstance(row.get(metric), (int, float))
    ]
    drivers = [
        {"label": item.get("feature"), "value": item.get("importance")}
        for item in ((result.get("explainability") or {}).get("global_importance") or [])
        if item.get("feature") is not None
    ]

    files: List[Dict[str, Any]] = []
    for key, raw in (result.get("artifacts") or {}).items():
        path = Path(str(raw))
        if path.is_file():
            files.append({"key": key, "name": path.name, "bytes": path.stat().st_size})

    return {
        "available": True,
        "run_id": chosen.get("id"),
        "target": chosen.get("target_column"),
        "best_model": chosen.get("best_model"),
        "metric": metric,
        "metric_value": chosen.get("primary_value"),
        "duration_seconds": chosen.get("duration_seconds"),
        "leaderboard": board[:8],
        "drivers": drivers[:6],
        "artifacts": sorted(files, key=lambda f: f["name"]),
    }


# ---------------------------------------------------------------- projects
@app.get("/api/projects")
def list_projects() -> Dict[str, Any]:
    return {"projects": store.list_projects()}


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectCreate) -> Dict[str, Any]:
    return store.create_project(body.name, body.description, tags=body.tags)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> Dict[str, Any]:
    project = _require_project(project_id)
    runs = store.list_runs(project_id)
    latest = store.latest_successful_run(project_id)
    return {
        "project": project,
        "runs": runs,
        "latest_result": latest.get("result") if latest else None,
        "registry": store.list_registry(project_id),
    }


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, body: ProjectUpdate) -> Dict[str, Any]:
    _require_project(project_id)
    updated = store.update_project(project_id, **body.model_dump(exclude_none=True))
    store.log_audit("you@dataid.local", "project.update", "project", project_id,
                    body.model_dump(exclude_none=True))
    return updated  # type: ignore[return-value]


@app.delete("/api/projects/{project_id}", status_code=204, response_class=Response)
def delete_project(project_id: str) -> Response:
    _require_project(project_id)
    if any(r["project_id"] == project_id for r in runner.active_runs()):
        raise HTTPException(409, "Wait for the active run to finish before deleting this project")
    store.delete_project(project_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- dataset
@app.post("/api/projects/{project_id}/dataset")
async def upload_dataset(project_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
    project = _require_project(project_id)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. "
                                 f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}")

    # store under a generated name so a hostile filename can never escape the upload dir
    destination = config.UPLOADS_DIR / f"{project_id}_{uuid.uuid4().hex}{suffix}"
    size = 0
    with destination.open("wb") as sink:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                sink.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(413, "File exceeds the 512 MB limit.")
            sink.write(chunk)

    try:
        understanding = understand_dataset(destination)
    except Exception as exc:  # noqa: BLE001
        destination.unlink(missing_ok=True)
        raise HTTPException(400, f"Could not parse the dataset: {exc}") from exc

    store.update_project(
        project_id,
        dataset_path=str(destination),
        dataset_name=file.filename,
        rows=understanding["rows"],
        columns=understanding["columns"],
        target_column=understanding["suggested_target"],
        task_type=understanding["inferred_task"],
        status="ready_to_run",
    )
    store.log_audit("you@dataid.local", "dataset.upload", "project", project_id,
                    {"filename": file.filename, "rows": understanding["rows"]})

    return {"project": store.get_project(project_id), "understanding": coerce_json(understanding),
            "size_bytes": size}


@app.get("/api/projects/{project_id}/dataset/preview")
def preview_dataset(project_id: str, limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    project = _require_project(project_id)
    if not project.get("dataset_path"):
        raise HTTPException(404, "No dataset uploaded for this project.")
    df = load_dataset(project["dataset_path"])
    head = df.head(limit)
    return coerce_json({
        "columns": [{"name": str(c), "dtype": str(df[c].dtype),
                     "missing_pct": round(float(df[c].isna().mean() * 100), 2),
                     "unique": int(df[c].nunique(dropna=True))} for c in df.columns],
        "rows": head.astype(object).where(head.notna(), None).to_dict(orient="records"),
        "total_rows": int(len(df)),
    })


@app.get("/api/projects/{project_id}/understanding")
def dataset_understanding(project_id: str) -> Dict[str, Any]:
    project = _require_project(project_id)
    if not project.get("dataset_path"):
        raise HTTPException(404, "No dataset uploaded for this project.")
    return coerce_json(understand_dataset(project["dataset_path"]))


# ---------------------------------------------------------------- runs
@app.post("/api/projects/{project_id}/runs", status_code=202)
def start_run(project_id: str, body: RunCreate) -> Dict[str, Any]:
    project = _require_project(project_id)
    if not project.get("dataset_path"):
        raise HTTPException(400, "Upload a dataset before starting a run.")

    target = body.target_column or project.get("target_column")
    # Clustering and anomaly detection have nothing to predict, so a target is optional there.
    if not target and requires_target(TaskType(body.task_type) if body.task_type else None):
        raise HTTPException(400, "No target column selected.")

    sensitive = body.sensitive_column or project.get("sensitive_column")
    run = store.create_run(project_id, target, sensitive, body.tune)
    store.update_project(project_id, target_column=target, sensitive_column=sensitive,
                         status="running")
    runner.submit(project, run, target, sensitive, body.tune, body.artifacts,
                  task_type=body.task_type, time_column=body.time_column,
                  group_column=body.group_column)
    return {"run": run, "stream_url": f"/api/runs/{run['id']}/stream"}


@app.get("/api/projects/{project_id}/runs")
def list_runs(project_id: str) -> Dict[str, Any]:
    _require_project(project_id)
    return {"runs": store.list_runs(project_id)}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found.")
    return {"run": run, "timeline": BUS.history(run_id), "active": runner.is_active(run_id)}


@app.get("/api/runs/{run_id}/timeline")
def run_timeline(run_id: str) -> Dict[str, Any]:
    return {"events": BUS.history(run_id)}


@app.get("/api/runs/{run_id}/stream")
def stream_run(run_id: str) -> StreamingResponse:
    """Server-sent events feeding the live timeline."""

    def generate():
        for event in BUS.stream(run_id):
            yield f"data: {json.dumps(coerce_json(event))}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/runs/{run_id}/artifacts")
def run_artifacts(run_id: str) -> Dict[str, Any]:
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found.")
    artifacts = (run.get("result") or {}).get("artifacts", {})
    return {"artifacts": [
        {"key": key, "name": Path(path).name, "size_bytes": _size(path),
         "download_url": f"/api/runs/{run_id}/artifacts/{key}"}
        for key, path in artifacts.items()
    ]}


@app.get("/api/runs/{run_id}/artifacts/{key}")
def download_artifact(run_id: str, key: str, inline: bool = Query(False)):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found.")
    artifacts = (run.get("result") or {}).get("artifacts", {})
    raw = artifacts.get(key)
    if not raw:
        raise HTTPException(404, f"No artifact '{key}' for this run.")

    # the key indexes a path we wrote ourselves; confirm it still sits inside the run directory
    path = Path(raw).resolve()
    root = (config.RUNS_DIR / run_id).resolve()
    if not path.is_file() or root not in path.parents and path.parent != root:
        raise HTTPException(404, "Artifact file is missing.")

    # A dashboard you have to download and find on disk is not much of a dashboard. HTML can be
    # viewed in place; everything else still downloads.
    if inline and path.suffix.lower() in {".html", ".md", ".json"}:
        media = {".html": "text/html", ".md": "text/plain", ".json": "application/json"}
        return FileResponse(path, media_type=media[path.suffix.lower()],
                            filename=path.name, content_disposition_type="inline")
    return FileResponse(path, filename=path.name)


def _size(path: str) -> int:
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


@app.get("/api/runs/{run_id}/compare/{other_run_id}")
def compare_runs(run_id: str, other_run_id: str) -> Dict[str, Any]:
    left, right = store.get_run(run_id), store.get_run(other_run_id)
    if not left or not right:
        raise HTTPException(404, "One or both runs were not found.")

    left_metrics = (left.get("result") or {}).get("metrics", {})
    right_metrics = (right.get("result") or {}).get("metrics", {})
    keys = [k for k in set(left_metrics) | set(right_metrics)
            if isinstance(left_metrics.get(k), (int, float))
            and isinstance(right_metrics.get(k), (int, float))]

    deltas = []
    for key in sorted(keys):
        a, b = float(left_metrics[key]), float(right_metrics[key])
        deltas.append({"metric": key, "left": round(a, 5), "right": round(b, 5),
                       "delta": round(b - a, 5),
                       "pct_change": round((b - a) / a * 100, 2) if a else None})

    return {
        "left": {"run_id": run_id, "version": left.get("version"), "model": left.get("best_model")},
        "right": {"run_id": other_run_id, "version": right.get("version"),
                  "model": right.get("best_model")},
        "deltas": deltas,
    }


# ---------------------------------------------------------------- chat
@app.get("/api/projects/{project_id}/chat")
def get_chat(project_id: str) -> Dict[str, Any]:
    _require_project(project_id)
    return {"messages": store.list_chat(project_id)}


@app.post("/api/projects/{project_id}/chat")
def post_chat(project_id: str, body: ChatRequest) -> Dict[str, Any]:
    project = _require_project(project_id)
    store.add_chat_message(project_id, "user", body.message)

    latest = store.latest_successful_run(project_id)
    summary = {
        "has_dataset": bool(project.get("dataset_path")),
        "target": project.get("target_column"),
        "task_type": project.get("task_type"),
        "best_model": (latest or {}).get("best_model"),
    }
    response = commands.respond(body.message, summary)

    executed: Optional[Dict[str, Any]] = None
    if body.auto_execute and response["action"] == "start_run" and project.get("dataset_path"):
        target = project.get("target_column")
        if target:
            run = store.create_run(project_id, target, project.get("sensitive_column"), False)
            runner.submit(project, run, target, project.get("sensitive_column"), False,
                          ["notebook", "report", "deck", "dashboard"])
            store.update_project(project_id, status="running")
            executed = {"type": "run_started", "run_id": run["id"],
                        "stream_url": f"/api/runs/{run['id']}/stream"}
    elif response["action"] == "inspect" and latest:
        section = response["params"].get("section")
        payload = (latest.get("result") or {})
        executed = {"type": "section", "section": section,
                    "data": coerce_json(payload.get(_section_key(section), {}))}
    elif response["action"] == "adjust_threshold" and latest:
        metrics = (latest.get("result") or {}).get("metrics", {})
        executed = {"type": "threshold",
                    "current": metrics.get("threshold_f1"),
                    "recall_optimised": metrics.get("threshold_recall")}

    message = store.add_chat_message(project_id, "assistant", response["reply"],
                                     {**response, "executed": executed})
    return {"message": message, "response": response, "executed": executed}


def _section_key(section: Optional[str]) -> str:
    return {
        "leakage": "eda", "outliers": "eda", "explainability": "explainability",
        "deployment": "deployment", "monitoring": "monitoring", "fairness": "fairness",
        "latency": "deployment",
    }.get(section or "", "metrics")


# ---------------------------------------------------------------- inference
@app.post("/api/projects/{project_id}/predict")
def predict(project_id: str, body: PredictRequest) -> Dict[str, Any]:
    bundle, run_id = _load_bundle(project_id)
    started = time.perf_counter()
    result = _score(bundle, [body.record])[0]
    latency = (time.perf_counter() - started) * 1000
    store.record_prediction(project_id, run_id, body.record, result["prediction"],
                            result.get("confidence"), latency)
    return {**result, "latency_ms": round(latency, 3)}


@app.post("/api/projects/{project_id}/predict/batch")
def predict_batch(project_id: str, body: BatchPredictRequest) -> Dict[str, Any]:
    if not body.records:
        raise HTTPException(400, "records must not be empty.")
    bundle, _ = _load_bundle(project_id)
    started = time.perf_counter()
    results = _score(bundle, body.records)
    latency = (time.perf_counter() - started) * 1000
    return {"count": len(results), "results": results, "latency_ms": round(latency, 3)}


@app.get("/api/projects/{project_id}/predictions")
def prediction_history(project_id: str) -> Dict[str, Any]:
    _require_project(project_id)
    return {"predictions": store.list_predictions(project_id)}


def _load_bundle(project_id: str):
    import joblib

    _require_project(project_id)
    latest = _serving_run(project_id)
    if not latest:
        raise HTTPException(400, "This project has no successful run to serve.")
    path = (latest.get("result") or {}).get("artifacts", {}).get("model_bundle")
    if not path or not Path(path).is_file():
        raise HTTPException(404, "The model bundle for this project is missing.")
    return joblib.load(path), latest["id"]


def _serving_run(project_id: str):
    production = next((m for m in store.list_registry(project_id) if m["stage"] == "production"), None)
    return store.get_run(production["run_id"]) if production else store.latest_successful_run(project_id)


@app.get("/api/projects/{project_id}/schema")
def prediction_schema(project_id: str):
    bundle, run_id = _load_bundle(project_id)
    run = store.get_run(run_id)
    path = (run.get("result") or {}).get("artifacts", {}).get("schema")
    if path and Path(path).is_file():
        return {**json.loads(Path(path).read_text(encoding="utf-8")), "run_id": run_id}
    return {"run_id": run_id, "input_columns": bundle["input_columns"], "task_type": bundle["task_type"]}


def _score(bundle: Dict[str, Any], records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from ..core.inference import score_records

    try:
        return coerce_json(score_records(bundle, records))
    except Exception as exc:
        raise HTTPException(400, f"Scoring failed: {exc}") from exc

# ---------------------------------------------------------------- monitoring
@app.get("/api/projects/{project_id}/monitoring")
def monitoring(project_id: str) -> Dict[str, Any]:
    _require_project(project_id)
    latest = _serving_run(project_id)
    if not latest:
        raise HTTPException(400, "No successful run to monitor.")
    result = latest.get("result") or {}
    predictions = store.list_predictions(project_id, limit=500)
    return {
        "monitoring": result.get("monitoring", {}),
        "baseline": result.get("monitoring", {}).get("baseline", {}),
        "prediction_count": len(predictions),
        "recent_predictions": predictions[:50],
        "latency": result.get("deployment", {}).get("latency", {}),
    }


@app.post("/api/projects/{project_id}/monitoring/drift")
def check_drift(project_id: str, body: DriftCheckRequest) -> Dict[str, Any]:
    """Score a live batch against the run's captured reference distribution."""
    import numpy as np
    import pandas as pd

    _require_project(project_id)
    latest = _serving_run(project_id)
    if not latest:
        raise HTTPException(400, "No successful run to compare against.")

    reference = (latest.get("result") or {}).get("monitoring", {}).get("reference", {})
    bundle, _ = _load_bundle(project_id)
    if bundle.get("feature_recipe"):
        from ..core.inference import prepare_frame
        try:
            frame = prepare_frame(bundle, body.records)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    else:
        frame = pd.DataFrame(body.records)
    rows: List[Dict[str, Any]] = []

    unscoreable: List[str] = []

    for entry in reference.get("numeric", []):
        column = entry["column"]
        if column not in frame.columns:
            continue
        actual = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        bins = entry.get("bins")
        # runs captured before the reference stored its real binned distribution cannot be
        # scored honestly — reconstructing one from mean/std would assume normality and make
        # the PSI meaningless for skewed, bimodal or discrete features
        value = psi_observed(bins, actual) if bins else None
        if value is None:
            unscoreable.append(column)
            continue
        rows.append({
            "feature": column, "psi": round(value, 5),
            "status": "critical" if value >= config.DRIFT_PSI_ALERT
            else "warning" if value >= config.DRIFT_PSI_WARN else "stable",
            "reference_mean": entry["mean"],
            "observed_mean": round(float(np.nanmean(actual)), 5) if actual.size else None,
            "reference_rows": (bins or {}).get("sample_size"),
        })

    rows.sort(key=lambda r: r["psi"], reverse=True)
    max_psi = rows[0]["psi"] if rows else 0.0
    payload: Dict[str, Any] = {
        "features": rows, "max_psi": max_psi,
        "status": "critical" if max_psi >= config.DRIFT_PSI_ALERT
        else "warning" if max_psi >= config.DRIFT_PSI_WARN else "stable",
        "rows_checked": len(frame),
    }
    if unscoreable:
        payload["unscoreable_features"] = unscoreable
        payload["note"] = ("These features have no stored reference distribution — the run "
                           "predates real reference capture. Re-run the pipeline to score them.")
    if not rows:
        payload["status"] = "unknown"
    return payload


# ---------------------------------------------------------------- registry, keys, audit
@app.get("/api/registry")
def registry(project_id: Optional[str] = None) -> Dict[str, Any]:
    return {"models": store.list_registry(project_id)}


@app.post("/api/registry/{model_id}/promote")
def promote(model_id: str, body: PromoteRequest) -> Dict[str, Any]:
    updated = store.promote_model(model_id, body.stage)
    if not updated:
        raise HTTPException(404, "Model not found in the registry.")
    return updated


@app.get("/api/keys")
def list_keys() -> Dict[str, Any]:
    return {"keys": store.list_api_keys()}


@app.post("/api/keys", status_code=201)
def create_key(body: ApiKeyCreate) -> Dict[str, Any]:
    """The plaintext token is returned exactly once — only its hash is stored."""
    return store.create_api_key(body.name, body.scopes)


@app.delete("/api/keys/{key_id}", status_code=204, response_class=Response)
def revoke_key(key_id: str) -> Response:
    if not store.revoke_api_key(key_id):
        raise HTTPException(404, "Key not found.")
    return Response(status_code=204)


@app.get("/api/audit")
def audit(limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    return {"entries": store.list_audit(limit)}


# ---------------------------------------------------------------- helpers
def _require_project(project_id: str) -> Dict[str, Any]:
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    return project
