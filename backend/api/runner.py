"""Background run execution — a bounded thread pool plus the live run registry."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from ..core import store
from ..core.config import RUNS_DIR
from ..core.orchestrator import Pipeline
from ..core.events import emit

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dataid-run")
_ACTIVE: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


def submit(project: Dict[str, Any], run: Dict[str, Any], target_column: Optional[str],
           sensitive_column: Optional[str], tune: bool, artifacts: List[str],
           task_type: Optional[str] = None, time_column: Optional[str] = None,
           group_column: Optional[str] = None) -> None:
    with _LOCK:
        _ACTIVE[run["id"]] = {"run_id": run["id"], "project_id": project["id"],
                              "project_name": project["name"], "status": "queued"}

    def task() -> None:
        try:
            with _LOCK:
                _ACTIVE[run["id"]]["status"] = "running"
            store.mark_run_running(run["id"])
            pipeline = Pipeline(
                dataset_path=project["dataset_path"], target_column=target_column,
                sensitive_column=sensitive_column, tune=tune, run_id=run["id"],
                output_root=RUNS_DIR, artifacts=artifacts, task_type=task_type,
                time_column=time_column, group_column=group_column,
            )
            store.finish_run(run["id"], pipeline.run())
        except Exception as exc:
            store.finish_run(run["id"], {"status": "failed", "error": str(exc)})
            emit(run["id"], "pipeline", "pipeline", "failed", str(exc), 1.0)
        finally:
            with _LOCK:
                _ACTIVE.pop(run["id"], None)

    _EXECUTOR.submit(task)


def active_runs() -> List[Dict[str, Any]]:
    with _LOCK:
        return list(_ACTIVE.values())


def is_active(run_id: str) -> bool:
    with _LOCK:
        return run_id in _ACTIVE
