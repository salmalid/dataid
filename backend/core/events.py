"""In-process event bus powering the GitHub-Actions style timeline."""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class TimelineEvent:
    run_id: str
    agent: str
    step: str
    status: str  # queued | running | success | failed | skipped
    message: str = ""
    progress: float = 0.0
    detail: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: Dict[str, List[TimelineEvent]] = defaultdict(list)
        self._subscribers: Dict[str, List[Queue]] = defaultdict(list)

    def emit(self, event: TimelineEvent) -> None:
        with self._lock:
            self._history[event.run_id].append(event)
            subs = list(self._subscribers[event.run_id])
        for q in subs:
            q.put(event)

    def history(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.as_dict() for e in self._history[run_id]]

    def subscribe(self, run_id: str) -> Queue:
        q: Queue = Queue()
        with self._lock:
            for existing in self._history[run_id]:
                q.put(existing)
            self._subscribers[run_id].append(q)
        return q

    def unsubscribe(self, run_id: str, q: Queue) -> None:
        with self._lock:
            if q in self._subscribers[run_id]:
                self._subscribers[run_id].remove(q)

    def stream(self, run_id: str, timeout: float = 30.0) -> Iterator[Dict[str, Any]]:
        q = self.subscribe(run_id)
        try:
            while True:
                try:
                    event = q.get(timeout=timeout)
                except Empty:
                    yield {"type": "heartbeat", "run_id": run_id}
                    continue
                yield event.as_dict()
                if event.step == "pipeline" and event.status in {"success", "failed"}:
                    break
        finally:
            self.unsubscribe(run_id, q)


BUS = EventBus()


def emit(run_id: str, agent: str, step: str, status: str, message: str = "",
         progress: float = 0.0, **detail: Any) -> None:
    BUS.emit(TimelineEvent(run_id=run_id, agent=agent, step=step, status=status,
                           message=message, progress=progress, detail=detail))
