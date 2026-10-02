"""SQLite persistence: workspaces, projects, runs, registry, keys, audit, chat."""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from . import config

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, plan TEXT DEFAULT 'pro',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, name TEXT NOT NULL,
    email TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'editor', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, name TEXT NOT NULL,
    description TEXT DEFAULT '', dataset_path TEXT, dataset_name TEXT,
    target_column TEXT, sensitive_column TEXT, task_type TEXT,
    rows INTEGER DEFAULT 0, columns INTEGER DEFAULT 0,
    status TEXT DEFAULT 'draft', tags TEXT DEFAULT '[]',
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, version INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued', target_column TEXT,
    sensitive_column TEXT, tune INTEGER DEFAULT 0,
    best_model TEXT, primary_metric TEXT, primary_value REAL,
    duration_seconds REAL, result_json TEXT, error TEXT,
    created_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS registry (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, run_id TEXT NOT NULL,
    name TEXT NOT NULL, version INTEGER NOT NULL, stage TEXT DEFAULT 'staging',
    metric_name TEXT, metric_value REAL, model_path TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, name TEXT NOT NULL,
    prefix TEXT NOT NULL, token_hash TEXT NOT NULL, scopes TEXT DEFAULT '[]',
    last_used_at TEXT, revoked INTEGER DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY, workspace_id TEXT, actor TEXT NOT NULL, action TEXT NOT NULL,
    resource_type TEXT, resource_id TEXT, detail TEXT DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, role TEXT NOT NULL,
    content TEXT NOT NULL, meta TEXT DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, run_id TEXT,
    payload TEXT NOT NULL, prediction TEXT, confidence REAL,
    latency_ms REAL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project_id);
CREATE INDEX IF NOT EXISTS idx_chat_project ON chat_messages(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_ws ON audit_log(workspace_id);
CREATE INDEX IF NOT EXISTS idx_pred_project ON predictions(project_id);
"""

DEFAULT_WORKSPACE = "ws_default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _LOCK, connect() as conn:
        conn.executescript(SCHEMA)
        existing = conn.execute("SELECT id FROM workspaces WHERE id = ?",
                                (DEFAULT_WORKSPACE,)).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO workspaces (id, name, plan, created_at) VALUES (?, ?, ?, ?)",
                (DEFAULT_WORKSPACE, "Personal workspace", "pro", _now()))
            conn.execute(
                "INSERT INTO members (id, workspace_id, name, email, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_uid("mem"), DEFAULT_WORKSPACE, "You", "you@dataid.local", "owner", _now()))


def _row(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def _rows(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- projects
def create_project(name: str, description: str = "", workspace_id: str = DEFAULT_WORKSPACE,
                   tags: Optional[List[str]] = None) -> Dict[str, Any]:
    project = {
        "id": _uid("prj"), "workspace_id": workspace_id, "name": name,
        "description": description, "dataset_path": None, "dataset_name": None,
        "target_column": None, "sensitive_column": None, "task_type": None,
        "rows": 0, "columns": 0, "status": "draft",
        "tags": json.dumps(tags or []), "created_at": _now(), "updated_at": _now(),
    }
    with _LOCK, connect() as conn:
        conn.execute(
            "INSERT INTO projects (id, workspace_id, name, description, dataset_path, dataset_name,"
            " target_column, sensitive_column, task_type, rows, columns, status, tags,"
            " created_at, updated_at) VALUES (:id, :workspace_id, :name, :description, :dataset_path,"
            " :dataset_name, :target_column, :sensitive_column, :task_type, :rows, :columns,"
            " :status, :tags, :created_at, :updated_at)", project)
    log_audit("you@dataid.local", "project.create", "project", project["id"], {"name": name})
    return get_project(project["id"])  # type: ignore[return-value]


def list_projects(workspace_id: str = DEFAULT_WORKSPACE) -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT p.*, "
            " (SELECT COUNT(*) FROM runs r WHERE r.project_id = p.id) AS run_count, "
            " (SELECT best_model FROM runs r WHERE r.project_id = p.id AND r.status='success' "
            "   ORDER BY r.version DESC LIMIT 1) AS best_model, "
            " (SELECT primary_value FROM runs r WHERE r.project_id = p.id AND r.status='success' "
            "   ORDER BY r.version DESC LIMIT 1) AS best_metric, "
            " (SELECT primary_metric FROM runs r WHERE r.project_id = p.id AND r.status='success' "
            "   ORDER BY r.version DESC LIMIT 1) AS best_metric_name "
            "FROM projects p WHERE p.workspace_id = ? ORDER BY p.updated_at DESC",
            (workspace_id,)).fetchall()
    return [_hydrate_project(r) for r in _rows(rows)]


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    project = _row(row)
    return _hydrate_project(project) if project else None


def _hydrate_project(project: Dict[str, Any]) -> Dict[str, Any]:
    project["tags"] = json.loads(project.get("tags") or "[]")
    return project


def update_project(project_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    allowed = {"name", "description", "dataset_path", "dataset_name", "target_column",
               "sensitive_column", "task_type", "rows", "columns", "status", "tags"}
    updates = {k: (json.dumps(v) if k == "tags" else v)
               for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_project(project_id)
    updates["updated_at"] = _now()
    assignments = ", ".join(f"{k} = :{k}" for k in updates)
    with _LOCK, connect() as conn:
        conn.execute(f"UPDATE projects SET {assignments} WHERE id = :id",
                     {**updates, "id": project_id})
    return get_project(project_id)


def delete_project(project_id: str) -> bool:
    with _LOCK, connect() as conn:
        cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.execute("DELETE FROM runs WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM chat_messages WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM registry WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM predictions WHERE project_id = ?", (project_id,))
    log_audit("you@dataid.local", "project.delete", "project", project_id, {})
    return cursor.rowcount > 0


# ---------------------------------------------------------------- runs
def create_run(project_id: str, target_column: str, sensitive_column: Optional[str],
               tune: bool) -> Dict[str, Any]:
    with _LOCK, connect() as conn:
        version = conn.execute("SELECT COALESCE(MAX(version), 0) + 1 AS v FROM runs WHERE project_id = ?",
                               (project_id,)).fetchone()["v"]
        run_id = uuid.uuid4().hex[:10]
        conn.execute(
            "INSERT INTO runs (id, project_id, version, status, target_column, sensitive_column,"
            " tune, created_at) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)",
            (run_id, project_id, version, target_column, sensitive_column, int(tune), _now()))
    log_audit("you@dataid.local", "run.start", "run", run_id, {"project_id": project_id})
    return get_run(run_id)  # type: ignore[return-value]


def mark_run_running(run_id: str) -> None:
    with _LOCK, connect() as conn:
        conn.execute("UPDATE runs SET status = 'running' WHERE id = ?", (run_id,))


def recover_interrupted_runs() -> None:
    """The control plane runs in one process; an old active status means it was interrupted."""
    with _LOCK, connect() as conn:
        conn.execute("UPDATE runs SET status = 'failed', error = ?, finished_at = ? "
                     "WHERE status IN ('queued', 'running')",
                     ("Backend stopped before this run completed. Start a new run.", _now()))


def finish_run(run_id: str, result: Dict[str, Any]) -> None:
    status = result.get("status", "failed")
    metrics = result.get("metrics", {})
    primary = (result.get("research") or {}).get("primary_metric")
    value = metrics.get(primary) if primary else None
    if value is None:
        value = metrics.get("accuracy", metrics.get("r2"))

    with _LOCK, connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, best_model = ?, primary_metric = ?, primary_value = ?,"
            " duration_seconds = ?, result_json = ?, error = ?, finished_at = ? WHERE id = ?",
            (status, result.get("best_model"), primary,
             float(value) if isinstance(value, (int, float)) else None,
             result.get("duration_seconds"), json.dumps(result), result.get("error"),
             _now(), run_id))
        row = conn.execute("SELECT project_id, version FROM runs WHERE id = ?", (run_id,)).fetchone()

    if status == "success" and row:
        update_project(row["project_id"], status="ready",
                       task_type=result.get("task_type"))
        register_model(row["project_id"], run_id, result.get("best_model") or "model",
                       row["version"], primary or "score",
                       float(value) if isinstance(value, (int, float)) else 0.0,
                       (result.get("artifacts") or {}).get("model_bundle", ""))


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    run = _row(row)
    if run and run.get("result_json"):
        run["result"] = json.loads(run["result_json"])
    run.pop("result_json", None) if run else None
    return run


def list_runs(project_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, project_id, version, status, target_column, best_model, primary_metric,"
            " primary_value, duration_seconds, error, created_at, finished_at"
            " FROM runs WHERE project_id = ? ORDER BY version DESC LIMIT ?",
            (project_id, limit)).fetchall()
    return _rows(rows)


def recent_successful_runs(limit: int = 10) -> List[Dict[str, Any]]:
    """Most recent successful runs across every project, newest first."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM runs WHERE status = 'success'"
            " ORDER BY finished_at DESC LIMIT ?", (limit,)).fetchall()
    return [run for run in (get_run(r["id"]) for r in rows) if run]


def latest_successful_run(project_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM runs WHERE project_id = ? AND status = 'success'"
            " ORDER BY version DESC LIMIT 1", (project_id,)).fetchone()
    return get_run(row["id"]) if row else None


# ---------------------------------------------------------------- registry
def register_model(project_id: str, run_id: str, name: str, version: int,
                   metric_name: str, metric_value: float, model_path: str) -> None:
    with _LOCK, connect() as conn:
        conn.execute(
            "INSERT INTO registry (id, project_id, run_id, name, version, stage, metric_name,"
            " metric_value, model_path, created_at) VALUES (?, ?, ?, ?, ?, 'staging', ?, ?, ?, ?)",
            (_uid("mdl"), project_id, run_id, name, version, metric_name, metric_value,
             model_path, _now()))


def list_registry(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM registry"
    params: tuple = ()
    if project_id:
        query += " WHERE project_id = ?"
        params = (project_id,)
    query += " ORDER BY created_at DESC"
    with connect() as conn:
        return _rows(conn.execute(query, params).fetchall())


def promote_model(model_id: str, stage: str) -> Optional[Dict[str, Any]]:
    with _LOCK, connect() as conn:
        row = conn.execute("SELECT project_id FROM registry WHERE id = ?", (model_id,)).fetchone()
        if not row:
            return None
        if stage == "production":
            conn.execute("UPDATE registry SET stage = 'archived' WHERE project_id = ? "
                         "AND stage = 'production'", (row["project_id"],))
        conn.execute("UPDATE registry SET stage = ? WHERE id = ?", (stage, model_id))
        updated = conn.execute("SELECT * FROM registry WHERE id = ?", (model_id,)).fetchone()
    log_audit("you@dataid.local", "model.promote", "model", model_id, {"stage": stage})
    return _row(updated)


# ---------------------------------------------------------------- api keys
def create_api_key(name: str, scopes: Optional[List[str]] = None,
                   workspace_id: str = DEFAULT_WORKSPACE) -> Dict[str, Any]:
    import hashlib

    token = f"nds_{secrets.token_urlsafe(32)}"
    prefix = token[:11]
    record = {
        "id": _uid("key"), "workspace_id": workspace_id, "name": name, "prefix": prefix,
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "scopes": json.dumps(["read", "write"] if scopes is None else scopes), "last_used_at": None,
        "revoked": 0, "created_at": _now(),
    }
    with _LOCK, connect() as conn:
        conn.execute(
            "INSERT INTO api_keys (id, workspace_id, name, prefix, token_hash, scopes,"
            " last_used_at, revoked, created_at) VALUES (:id, :workspace_id, :name, :prefix,"
            " :token_hash, :scopes, :last_used_at, :revoked, :created_at)", record)
    log_audit("you@dataid.local", "apikey.create", "api_key", record["id"], {"name": name})
    return {**record, "token": token, "scopes": json.loads(record["scopes"]),
            "token_hash": None}


def list_api_keys(workspace_id: str = DEFAULT_WORKSPACE) -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, workspace_id, name, prefix, scopes, last_used_at, revoked, created_at"
            " FROM api_keys WHERE workspace_id = ? ORDER BY created_at DESC",
            (workspace_id,)).fetchall()
    out = _rows(rows)
    for key in out:
        key["scopes"] = json.loads(key["scopes"])
    return out


def authenticate_api_key(token: str) -> Optional[Dict[str, Any]]:
    import hashlib
    digest = hashlib.sha256(token.encode()).hexdigest()
    with _LOCK, connect() as conn:
        row = conn.execute("SELECT id, scopes FROM api_keys WHERE token_hash = ? AND revoked = 0",
                           (digest,)).fetchone()
        if row is None:
            return None
        conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?", (_now(), row["id"]))
    return {"id": row["id"], "scopes": json.loads(row["scopes"])}


def revoke_api_key(key_id: str) -> bool:
    with _LOCK, connect() as conn:
        cursor = conn.execute("UPDATE api_keys SET revoked = 1 WHERE id = ?", (key_id,))
    log_audit("you@dataid.local", "apikey.revoke", "api_key", key_id, {})
    return cursor.rowcount > 0


# ---------------------------------------------------------------- audit + chat
def log_audit(actor: str, action: str, resource_type: str, resource_id: str,
              detail: Dict[str, Any], workspace_id: str = DEFAULT_WORKSPACE) -> None:
    with _LOCK, connect() as conn:
        conn.execute(
            "INSERT INTO audit_log (id, workspace_id, actor, action, resource_type, resource_id,"
            " detail, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (_uid("aud"), workspace_id, actor, action, resource_type, resource_id,
             json.dumps(detail), _now()))


def list_audit(limit: int = 100, workspace_id: str = DEFAULT_WORKSPACE) -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ?",
            (workspace_id, limit)).fetchall()
    out = _rows(rows)
    for entry in out:
        entry["detail"] = json.loads(entry["detail"])
    return out


def add_chat_message(project_id: str, role: str, content: str,
                     meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    record = {"id": _uid("msg"), "project_id": project_id, "role": role, "content": content,
              "meta": json.dumps(meta or {}), "created_at": _now()}
    with _LOCK, connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, project_id, role, content, meta, created_at)"
            " VALUES (:id, :project_id, :role, :content, :meta, :created_at)", record)
    return {**record, "meta": meta or {}}


def list_chat(project_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE project_id = ? ORDER BY created_at ASC LIMIT ?",
            (project_id, limit)).fetchall()
    out = _rows(rows)
    for message in out:
        message["meta"] = json.loads(message["meta"])
    return out


def record_prediction(project_id: str, run_id: Optional[str], payload: Dict[str, Any],
                      prediction: Any, confidence: Optional[float], latency_ms: float) -> None:
    with _LOCK, connect() as conn:
        conn.execute(
            "INSERT INTO predictions (id, project_id, run_id, payload, prediction, confidence,"
            " latency_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (_uid("prd"), project_id, run_id, json.dumps(payload), str(prediction),
             confidence, latency_ms, _now()))


def list_predictions(project_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
            (project_id, limit)).fetchall()
    out = _rows(rows)
    for entry in out:
        entry["payload"] = json.loads(entry["payload"])
    return out


def workspace_stats(workspace_id: str = DEFAULT_WORKSPACE) -> Dict[str, Any]:
    with connect() as conn:
        projects = conn.execute("SELECT COUNT(*) c FROM projects WHERE workspace_id = ?",
                                (workspace_id,)).fetchone()["c"]
        runs = conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
        successful = conn.execute("SELECT COUNT(*) c FROM runs WHERE status='success'").fetchone()["c"]
        models = conn.execute("SELECT COUNT(*) c FROM registry").fetchone()["c"]
        production = conn.execute("SELECT COUNT(*) c FROM registry WHERE stage='production'").fetchone()["c"]
        predictions = conn.execute("SELECT COUNT(*) c FROM predictions").fetchone()["c"]
        duration = conn.execute(
            "SELECT AVG(duration_seconds) d FROM runs WHERE status='success'").fetchone()["d"]
    return {
        "projects": projects, "runs": runs, "successful_runs": successful,
        "models": models, "models_in_production": production, "predictions": predictions,
        "avg_run_seconds": round(duration, 1) if duration else 0.0,
        "success_rate": round(successful / runs * 100, 1) if runs else 0.0,
    }
