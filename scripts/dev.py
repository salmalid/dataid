"""Start the dataid backend and frontend together.

    python scripts/dev.py

Ctrl-C stops both. Pass --backend-only or --frontend-only to run one side.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def start_backend(port: int, reload: bool) -> subprocess.Popen:
    print(f"[dataid] backend  → http://127.0.0.1:{port}")
    command = [sys.executable, "-m", "uvicorn", "backend.api.main:app",
               "--host", "127.0.0.1", "--port", str(port)]
    if reload:
        # The Deployment agent writes a generated app.py into storage/runs/<id>/deploy/.
        # uvicorn's watcher picks that up as a source change and restarts the server *during
        # the run* — killing the executor thread and dropping the SSE stream the timeline is
        # reading. --reload-dir does not reliably contain this, so reload is opt-in.
        command += ["--reload", "--reload-dir", "backend"]
        print("[dataid] WARNING: --reload can restart the server mid-run when a run reaches "
              "the deployment stage. Leave it off while running pipelines.")
    return subprocess.Popen(command, cwd=ROOT)


def start_frontend(api_port: int) -> subprocess.Popen | None:
    if not (FRONTEND / "node_modules").exists():
        print("[dataid] frontend dependencies are missing — run `cd frontend && npm install`")
        return None
    print("[dataid] frontend → http://localhost:3000")
    env = {**os.environ, "DATAID_API_ORIGIN": f"http://127.0.0.1:{api_port}"}
    return subprocess.Popen(
        ["npm.cmd" if os.name == "nt" else "npm", "run", "dev"],
        cwd=FRONTEND,
        env=env,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="dataid development launcher")
    parser.add_argument("--port", type=int, default=8000, help="backend port")
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--frontend-only", action="store_true")
    parser.add_argument("--reload", action="store_true",
                        help="auto-restart the backend on code changes; unsafe during a run")
    args = parser.parse_args()

    if not (ROOT / "sample_data").exists():
        print("[dataid] generating sample datasets…")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_sample_data.py")], cwd=ROOT)

    processes: list[subprocess.Popen] = []
    try:
        if not args.frontend_only:
            processes.append(start_backend(args.port, args.reload))
            time.sleep(2)
        if not args.backend_only:
            frontend = start_frontend(args.port)
            if frontend:
                processes.append(frontend)

        if not processes:
            return 1

        print("[dataid] ready — Ctrl-C to stop")
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        print("[dataid] a process exited; shutting down")
    except KeyboardInterrupt:
        print("\n[dataid] stopping…")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
