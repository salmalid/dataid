"""The multi-agent pipeline. Runs agents in order against one shared context."""
from __future__ import annotations

import re
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from . import config
from .context import (
    ProjectContext,
    TaskFamily,
    TaskType,
    family_of,
    requires_group_column,
    requires_target,
    requires_time_column,
)
from .events import emit
from .utils import coerce_json, downsample, infer_task_type
from ..agents import (
    DataCleanerAgent,
    DataDetectiveAgent,
    DeploymentAgent,
    ExperimentManagerAgent,
    ExplainabilityAgent,
    FeatureEngineerAgent,
    MLResearcherAgent,
    MonitoringAgent,
)
from ..generators import (
    generate_dashboard,
    generate_notebook,
    generate_powerpoint,
    generate_report_html,
    generate_report_markdown,
)

PIPELINE = [
    DataDetectiveAgent,
    DataCleanerAgent,
    FeatureEngineerAgent,
    MLResearcherAgent,
    ExperimentManagerAgent,
    ExplainabilityAgent,
    DeploymentAgent,
    MonitoringAgent,
]

AGENT_CATALOG = [
    {"name": a.name, "label": a.label, "description": a.description, "critical": a.critical}
    for a in PIPELINE
]

# The output formats a caller can request. Order is the order they are generated in.
ARTIFACT_CATALOG = [
    {"key": "report", "label": "Report",
     "description": "Executive summary, findings and leaderboard as HTML + Markdown.",
     "formats": [".html", ".md"]},
    {"key": "dashboard", "label": "Interactive dashboard",
     "description": "Filterable multi-panel dashboard in a single self-contained file.",
     "formats": [".html"]},
    {"key": "deck", "label": "Slide deck",
     "description": "Eight-slide executive presentation.",
     "formats": [".pptx"]},
    {"key": "notebook", "label": "Notebook",
     "description": "Runnable Jupyter notebook reproducing the whole pipeline.",
     "formats": [".ipynb"]},
]

ARTIFACT_KEYS = [a["key"] for a in ARTIFACT_CATALOG]
DEFAULT_ARTIFACTS = list(ARTIFACT_KEYS)


TASK_CATALOG = [
    {"key": "classification", "label": "Classification",
     "description": "Predict which category a row belongs to.",
     "needs_target": True, "needs_time": False, "needs_group": False,
     "example": "Will this customer churn?"},
    {"key": "regression", "label": "Regression",
     "description": "Predict a number.",
     "needs_target": True, "needs_time": False, "needs_group": False,
     "example": "What will this house sell for?"},
    {"key": "forecasting", "label": "Forecasting",
     "description": "Predict a number forward in time. Needs a date column; the holdout is the "
                    "most recent slice and is never shuffled.",
     "needs_target": True, "needs_time": True, "needs_group": False,
     "example": "What will demand be next month?"},
    {"key": "clustering", "label": "Clustering",
     "description": "Find natural segments. No target — the leaderboard sweeps the cluster count "
                    "and ranks by holdout silhouette.",
     "needs_target": False, "needs_time": False, "needs_group": False,
     "example": "What customer segments exist?"},
    {"key": "anomaly", "label": "Anomaly detection",
     "description": "Flag rows that do not look like the rest. No target required; if you supply "
                    "one, precision and recall are reported against it.",
     "needs_target": False, "needs_time": False, "needs_group": False,
     "example": "Which transactions look wrong?"},
    {"key": "ranking", "label": "Ranking",
     "description": "Order items within each query by relevance. Needs a group column; whole "
                    "groups are held out together.",
     "needs_target": True, "needs_time": False, "needs_group": True,
     "example": "Which results should appear first?"},
]

TASK_KEYS = [t["key"] for t in TASK_CATALOG]


class Pipeline:
    def __init__(self, dataset_path: str | Path, target_column: Optional[str] = None,
                 sensitive_column: Optional[str] = None, tune: bool = False,
                 run_id: Optional[str] = None, output_root: Optional[Path] = None,
                 artifacts: Optional[List[str]] = None,
                 task_type: Optional[str] = None,
                 time_column: Optional[str] = None,
                 group_column: Optional[str] = None) -> None:
        self.dataset_path = Path(dataset_path)
        self.target_column = target_column
        self.sensitive_column = sensitive_column
        self.tune = tune
        self.run_id = run_id
        self.task_type = TaskType(task_type) if task_type else None
        self.time_column = time_column
        self.group_column = group_column
        self.output_root = output_root or config.RUNS_DIR
        # `or` would be wrong here: an explicitly empty list means "train only, generate
        # nothing", and falsiness would silently turn that into "generate everything".
        self.artifacts = DEFAULT_ARTIFACTS if artifacts is None else list(artifacts)

    # ------------------------------------------------------------------
    def run(self, on_complete: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        started = time.perf_counter()
        ctx: Optional[ProjectContext] = None
        run_id = self.run_id or "pending"

        try:
            df = load_dataset(self.dataset_path)
            self._validate(df)
            if self.time_column and self.time_column in df.columns:
                # sort order has to be chronological, not lexicographic — "10 Jan" precedes
                # "2 Feb" as a string and would silently scramble the split
                df[self.time_column] = pd.to_datetime(df[self.time_column], errors="coerce")

            kwargs: Dict[str, Any] = {
                "raw_df": downsample(df),
                "target_column": self.target_column,
                "sensitive_column": self.sensitive_column,
                "tune": self.tune,
                "output_root": self.output_root,
                "task_type": self.task_type,
                "time_column": self.time_column,
                "group_column": self.group_column,
            }
            if self.run_id:
                kwargs["run_id"] = self.run_id
            ctx = ProjectContext(**kwargs)
            run_id = ctx.run_id

            emit(run_id, "pipeline", "pipeline", "running",
                 f"Pipeline started on {len(df):,} rows", 0.0,
                 agents=[a["name"] for a in AGENT_CATALOG])

            for agent_class in PIPELINE:
                agent_class().execute(ctx)

            self._generate_artifacts(ctx)

            elapsed = time.perf_counter() - started
            emit(run_id, "pipeline", "pipeline", "success",
                 f"Completed in {elapsed:.1f}s — winner {ctx.best_model_name}", 1.0,
                 duration=round(elapsed, 2), best_model=ctx.best_model_name)

            result = coerce_json({**ctx.to_summary_dict(), "status": "success",
                                  "duration_seconds": round(elapsed, 2)})
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - started
            emit(run_id, "pipeline", "pipeline", "failed", str(exc), 1.0,
                 traceback=traceback.format_exc(limit=6))
            result = coerce_json({
                "run_id": run_id, "status": "failed", "error": str(exc),
                "duration_seconds": round(elapsed, 2),
                "logs": [l.__dict__ for l in ctx.logs] if ctx else [],
                "issues": [i.__dict__ for i in ctx.issues] if ctx else [],
            })

        if on_complete:
            on_complete(result)
        return result

    # ------------------------------------------------------------------
    def _validate(self, df: pd.DataFrame) -> None:
        """Fail fast and specifically, before an agent fails obscurely twenty seconds in."""
        task = self.task_type

        if requires_target(task):
            if not self.target_column:
                raise ValueError(
                    f"'{task.value if task else 'This task'}' needs a target column. "
                    "Clustering and anomaly detection are the two that do not.")
            if self.target_column not in df.columns:
                raise ValueError(f"Target '{self.target_column}' is not a column in the dataset.")
        elif self.target_column and self.target_column not in df.columns:
            # optional here, but a typo should still be caught rather than silently ignored
            raise ValueError(f"Column '{self.target_column}' is not in the dataset.")

        if requires_time_column(task):
            if not self.time_column:
                raise ValueError("Forecasting needs a time column to order rows by.")
            if self.time_column not in df.columns:
                raise ValueError(f"Time column '{self.time_column}' is not in the dataset.")
            if pd.to_datetime(df[self.time_column], errors="coerce").notna().sum() < 2:
                raise ValueError(f"Column '{self.time_column}' does not parse as dates.")

        if requires_group_column(task):
            if not self.group_column:
                raise ValueError("Ranking needs a group column identifying which query each row "
                                 "belongs to.")
            if self.group_column not in df.columns:
                raise ValueError(f"Group column '{self.group_column}' is not in the dataset.")
            if df[self.group_column].nunique() < 2:
                raise ValueError(f"Column '{self.group_column}' has only one group — ranking "
                                 "needs several queries to average over.")

    def _generate_artifacts(self, ctx: ProjectContext) -> None:
        jobs: List[tuple[str, str, Callable[[], Path]]] = []
        if "notebook" in self.artifacts:
            jobs.append(("notebook", "Notebook",
                         lambda: generate_notebook(ctx, str(self.dataset_path))))
        if "report" in self.artifacts:
            jobs.append(("report_markdown", "Markdown report", lambda: generate_report_markdown(ctx)))
            jobs.append(("report_html", "HTML report", lambda: generate_report_html(ctx)))
        if "deck" in self.artifacts:
            jobs.append(("deck", "Executive deck", lambda: generate_powerpoint(ctx)))
        if "dashboard" in self.artifacts:
            jobs.append(("dashboard", "Interactive dashboard", lambda: generate_dashboard(ctx)))

        total = len(jobs) or 1
        emit(ctx.run_id, "generators", "generators", "running", "Generating artifacts", 0.0)
        for i, (key, label, job) in enumerate(jobs, start=1):
            try:
                path = job()
                ctx.register_artifact(key, path)
                emit(ctx.run_id, "generators", "generators", "running",
                     f"{label} ready", i / total, artifact=key, path=str(path))
            except Exception as exc:  # noqa: BLE001
                ctx.log("generators", f"{label} failed: {exc}")
                emit(ctx.run_id, "generators", "generators", "running",
                     f"{label} failed: {exc}", i / total, artifact=key)
        emit(ctx.run_id, "generators", "generators", "success",
             f"{len(ctx.artifacts)} artifacts written", 1.0)


# ---------------------------------------------------------------------- helpers
def load_dataset(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path, low_memory=False)
    if suffix in {".tsv"}:
        return pd.read_csv(path, sep="\t", low_memory=False)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix in {".json", ".jsonl"}:
        return pd.read_json(path, lines=suffix == ".jsonl")
    raise ValueError(f"Unsupported file type '{suffix}'. Use CSV, TSV, Excel, Parquet or JSON.")


def understand_dataset(path: str | Path) -> Dict[str, Any]:
    """The 'AI reads your CSV' response shown immediately after upload."""
    from .utils import looks_like_datetime, looks_like_identifier, split_columns

    df = load_dataset(path)
    groups = split_columns(df)
    target, confidence, reason = suggest_target(df)
    task_type = infer_task_type(df[target]) if target else None

    leakage: List[str] = []
    if target:
        from ..core.utils import LEAKY_HINTS

        for col in df.columns:
            if col != target and any(h in str(col).lower() for h in LEAKY_HINTS):
                leakage.append(str(col))

    sensitive_pattern = re.compile(
        r"(?:^|_)(gender|sex|race|ethnicity|age|region|country|nationality|marital|"
        r"religion|disability|disabled)(?:$|_)")
    sensitive_candidates = [str(c) for c in df.columns
                            if sensitive_pattern.search(str(c).lower())]

    rows = len(df)
    estimated_seconds = max(25, min(600, int(rows * df.shape[1] / 9000) + 30))

    return {
        "rows": int(rows),
        "columns": int(df.shape[1]),
        "memory_bytes": int(df.memory_usage(deep=True).sum()),
        "column_names": [str(c) for c in df.columns],
        "column_groups": groups,
        "suggested_target": target,
        "target_confidence": confidence,
        "target_reason": reason,
        "inferred_task": task_type,
        "problem_statement": _problem_statement(target, task_type),
        "leakage_candidates": leakage,
        "sensitive_candidates": sensitive_candidates,
        "recommended_models": _recommended_models(task_type, rows),
        "missing_cells": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "estimated_seconds": estimated_seconds,
        "preview": coerce_json(df.head(8).astype(object).where(pd.notna(df.head(8)), None)
                               .to_dict(orient="records")),
    }


def suggest_target(df: pd.DataFrame) -> tuple[Optional[str], float, str]:
    """Score every column on how much it looks like a supervised target."""
    priority = ("target", "label", "class", "outcome", "y", "churn", "attrition", "fraud",
                "survived", "default", "price", "sales", "revenue", "score", "rating",
                "diagnosis", "disease", "result", "status", "converted", "clicked", "response")

    best: tuple[Optional[str], float, str] = (None, 0.0, "")
    for col in df.columns:
        name = str(col).lower()
        s = df[col]
        score, reasons = 0.0, []

        for i, hint in enumerate(priority):
            if name == hint:
                score += 0.6 - i * 0.005
                reasons.append(f"column is named '{col}'")
                break
            # match on whole word parts only — a bare substring lets "y" hit "chest_pain_type"
            if hint in re.split(r"[^a-z0-9]+", name):
                score += 0.35 - i * 0.004
                reasons.append(f"name contains '{hint}'")
                break

        nunique = s.nunique(dropna=True)
        if nunique == 2:
            score += 0.28
            reasons.append("binary values")
        elif 2 < nunique <= 10 and s.dtype == object:
            score += 0.15
            reasons.append("small set of categories")

        if s.isna().mean() > 0.3:
            score -= 0.3
        if list(df.columns).index(col) == len(df.columns) - 1:
            score += 0.12
            reasons.append("last column")
        if nunique == len(s):
            score -= 0.5

        if score > best[1]:
            best = (str(col), round(min(score, 0.99), 3), "; ".join(reasons[:3]))

    if best[0] is None and len(df.columns):
        last = str(df.columns[-1])
        return last, 0.2, "defaulted to the last column"
    return best


def _problem_statement(target: Optional[str], task_type: Optional[str]) -> str:
    if not target:
        return "Unable to infer a target column — pick one to continue."
    pretty = str(target).replace("_", " ").strip().title()
    if task_type == "classification":
        return f"{pretty} Prediction (classification)"
    return f"{pretty} Forecasting (regression)"


def _recommended_models(task_type: Optional[str], rows: int) -> List[str]:
    from ..agents import model_zoo

    available = model_zoo.availability()
    boosted = [name for name, present in
               (("CatBoost", available["catboost"]), ("LightGBM", available["lightgbm"]),
                ("XGBoost", available["xgboost"])) if present]
    base = boosted + ["HistGradientBoosting", "Random Forest"]
    if task_type == "classification":
        base.append("Logistic Regression")
    else:
        base.append("Ridge")
    if rows < 2000:
        base = [m for m in base if m not in {"LightGBM"}]
    return base[:5]
