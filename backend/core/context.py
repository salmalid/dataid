"""Shared state object passed between every agent in the pipeline."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    ANOMALY = "anomaly"
    FORECASTING = "forecasting"
    RANKING = "ranking"


class TaskFamily(str, Enum):
    """How a task is *shaped*, which is what the pipeline actually branches on.

    Two tasks in the same family split their data the same way, score with the same kind of
    metric, and need the same columns present. Agents ask for the family, never the task.
    """

    SUPERVISED = "supervised"      # a target exists and rows are exchangeable
    UNSUPERVISED = "unsupervised"  # no target at all
    TEMPORAL = "temporal"          # a target exists but row order is meaningful
    RANKING = "ranking"            # a target exists and rows are grouped into queries


FAMILY_OF: Dict[TaskType, TaskFamily] = {
    TaskType.CLASSIFICATION: TaskFamily.SUPERVISED,
    TaskType.REGRESSION: TaskFamily.SUPERVISED,
    TaskType.CLUSTERING: TaskFamily.UNSUPERVISED,
    TaskType.ANOMALY: TaskFamily.UNSUPERVISED,
    TaskType.FORECASTING: TaskFamily.TEMPORAL,
    TaskType.RANKING: TaskFamily.RANKING,
}


def family_of(task_type: Optional[TaskType]) -> Optional[TaskFamily]:
    return FAMILY_OF.get(task_type) if task_type else None


def requires_target(task_type: Optional[TaskType]) -> bool:
    """Clustering and anomaly detection have nothing to predict — that is the whole point."""
    return family_of(task_type) is not TaskFamily.UNSUPERVISED


def requires_time_column(task_type: Optional[TaskType]) -> bool:
    return family_of(task_type) is TaskFamily.TEMPORAL


def requires_group_column(task_type: Optional[TaskType]) -> bool:
    return family_of(task_type) is TaskFamily.RANKING


# What each task optimises for, and whether bigger is better.
PRIMARY_METRIC: Dict[TaskType, str] = {
    TaskType.CLASSIFICATION: "roc_auc",
    TaskType.REGRESSION: "r2",
    TaskType.CLUSTERING: "silhouette",
    TaskType.ANOMALY: "anomaly_separation",
    TaskType.FORECASTING: "mae",
    TaskType.RANKING: "ndcg",
}

LOWER_IS_BETTER = {"mae", "rmse", "mse", "mape", "log_loss", "davies_bouldin", "smape"}


@dataclass
class LogEntry:
    agent: str
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Issue:
    severity: str  # "info" | "warning" | "critical"
    category: str  # e.g. "missing_values", "leakage", "outliers", "duplicates"
    column: Optional[str]
    message: str
    stat: Optional[float] = None


@dataclass
class ProjectContext:
    """Mutable state threaded through DataCleaningAgent -> ... -> DeploymentAgent."""

    raw_df: pd.DataFrame
    # Optional since clustering and anomaly detection have no target. Everything downstream
    # must go through `requires_target(ctx.task_type)` rather than assuming a column exists.
    target_column: Optional[str] = None
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    output_root: Path = field(default_factory=lambda: Path("runs"))
    sensitive_column: Optional[str] = None
    task_type: Optional[TaskType] = None
    tune: bool = False
    # forecasting orders rows by this; ranking groups rows by that
    time_column: Optional[str] = None
    group_column: Optional[str] = None

    # working copy, mutated in place by DataCleaningAgent / FeatureEngineeringAgent
    df: pd.DataFrame = field(init=False)

    logs: List[LogEntry] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)

    profile: Dict[str, Any] = field(default_factory=dict)
    eda: Dict[str, Any] = field(default_factory=dict)
    research: Dict[str, Any] = field(default_factory=dict)
    fairness: Dict[str, Any] = field(default_factory=dict)
    monitoring: Dict[str, Any] = field(default_factory=dict)
    cleaning_summary: Dict[str, Any] = field(default_factory=dict)
    feature_summary: Dict[str, Any] = field(default_factory=dict)

    preprocessor: Any = None
    feature_recipe: Dict[str, Any] = field(default_factory=lambda: {"operations": []})
    feature_names: List[str] = field(default_factory=list)
    train_indices: Optional[np.ndarray] = None
    test_indices: Optional[np.ndarray] = None

    X_train: Optional[np.ndarray] = None
    X_test: Optional[np.ndarray] = None
    # None for clustering, and for anomaly detection on unlabelled data
    y_train: Optional[np.ndarray] = None
    y_test: Optional[np.ndarray] = None
    raw_X_test: Optional[pd.DataFrame] = None
    # query ids, ranking only — metrics are averaged within a group, never across
    group_values: Optional[pd.Series] = None
    groups_train: Optional[np.ndarray] = None
    groups_test: Optional[np.ndarray] = None

    leaderboard: Optional[pd.DataFrame] = None
    best_model_name: Optional[str] = None
    best_model: Any = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    # unsupervised output: the assignment or score the winning model produced on the holdout
    labels_test: Optional[np.ndarray] = None
    scores_test: Optional[np.ndarray] = None
    segments: Dict[str, Any] = field(default_factory=dict)

    explainability: Dict[str, Any] = field(default_factory=dict)
    deployment: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.df = self.raw_df.copy()
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    @property
    def artifacts_dir(self) -> Path:
        return self.output_root / self.run_id

    def log(self, agent: str, message: str) -> None:
        self.logs.append(LogEntry(agent=agent, message=message))

    def add_issue(self, severity: str, category: str, column: Optional[str], message: str,
                  stat: Optional[float] = None) -> None:
        self.issues.append(Issue(severity=severity, category=category, column=column,
                                  message=message, stat=stat))

    def register_artifact(self, name: str, path: Path) -> None:
        self.artifacts[name] = str(path)

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_type": self.task_type.value if self.task_type else None,
            "task_family": family_of(self.task_type).value if self.task_type else None,
            "target_column": self.target_column,
            "time_column": self.time_column,
            "group_column": self.group_column,
            "segments": self.segments,
            "rows": int(self.raw_df.shape[0]),
            "columns": int(self.raw_df.shape[1]),
            "issues": [i.__dict__ for i in self.issues],
            "profile": self.profile,
            "eda": self.eda,
            "research": self.research,
            "fairness": self.fairness,
            "monitoring": self.monitoring,
            "cleaning_summary": self.cleaning_summary,
            "feature_summary": self.feature_summary,
            "best_model": self.best_model_name,
            "metrics": self.metrics,
            "leaderboard": self.leaderboard.to_dict(orient="records") if self.leaderboard is not None else [],
            "explainability": {k: v for k, v in self.explainability.items() if k != "shap_values"},
            "deployment": self.deployment,
            "artifacts": self.artifacts,
            "logs": [l.__dict__ for l in self.logs],
        }
