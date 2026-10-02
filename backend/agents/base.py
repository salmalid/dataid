"""Agent contract: each agent mutates the shared ProjectContext and narrates itself."""
from __future__ import annotations

import time
import traceback
from typing import Any, Dict

from ..core.context import ProjectContext
from ..core.events import emit


class Agent:
    name: str = "agent"
    label: str = "Agent"
    description: str = ""
    # a hard failure here aborts the pipeline; soft agents degrade gracefully
    critical: bool = True

    def run(self, ctx: ProjectContext) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    # ------------------------------------------------------------------
    def execute(self, ctx: ProjectContext) -> Dict[str, Any]:
        emit(ctx.run_id, self.name, self.name, "running", f"{self.label} started")
        started = time.perf_counter()
        try:
            self.run(ctx)
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - started
            detail = traceback.format_exc(limit=4)
            ctx.log(self.name, f"failed: {exc}")
            emit(ctx.run_id, self.name, self.name, "failed", str(exc), 1.0,
                 duration=round(elapsed, 3), traceback=detail)
            if self.critical:
                raise
            return {"agent": self.name, "status": "failed", "error": str(exc), "duration": elapsed}

        elapsed = time.perf_counter() - started
        emit(ctx.run_id, self.name, self.name, "success", f"{self.label} complete", 1.0,
             duration=round(elapsed, 3))
        ctx.log(self.name, f"completed in {elapsed:.2f}s")
        return {"agent": self.name, "status": "success", "duration": elapsed}

    # convenience for subclasses
    def progress(self, ctx: ProjectContext, message: str, pct: float, **detail: Any) -> None:
        emit(ctx.run_id, self.name, self.name, "running", message, pct, **detail)
        ctx.log(self.name, message)
