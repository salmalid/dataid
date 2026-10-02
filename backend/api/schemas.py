"""Request and response models for the dataid control plane."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from ..core.orchestrator import ARTIFACT_KEYS, DEFAULT_ARTIFACTS, TASK_KEYS


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = ""
    tags: List[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_column: Optional[str] = None
    sensitive_column: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


class RunCreate(BaseModel):
    target_column: Optional[str] = None
    sensitive_column: Optional[str] = None
    tune: bool = False
    # None keeps the historical behaviour: infer classification vs regression from the target.
    task_type: Optional[str] = None
    time_column: Optional[str] = None      # forecasting
    group_column: Optional[str] = None     # ranking
    # An explicit [] is legal and means "train the model, generate no documents".
    artifacts: List[str] = Field(default_factory=lambda: list(DEFAULT_ARTIFACTS))

    @field_validator("task_type")
    @classmethod
    def _known_task(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in TASK_KEYS:
            raise ValueError(f"Unknown task '{value}'. Valid: {', '.join(TASK_KEYS)}")
        return value

    @field_validator("artifacts")
    @classmethod
    def _known_artifacts(cls, value: List[str]) -> List[str]:
        unknown = [v for v in value if v not in ARTIFACT_KEYS]
        if unknown:
            raise ValueError(f"Unknown artifact(s) {unknown}. Valid: {', '.join(ARTIFACT_KEYS)}")
        return list(dict.fromkeys(value))  # de-duplicate, preserve order


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    auto_execute: bool = True


class PredictRequest(BaseModel):
    record: Dict[str, Any]


class BatchPredictRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(..., max_length=5000)


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    scopes: List[str] = Field(default_factory=lambda: ["read", "write"])

    @field_validator("scopes")
    @classmethod
    def _known_scopes(cls, value: List[str]) -> List[str]:
        if set(value) - {"read", "write"}:
            raise ValueError("Scopes must be read or write")
        return list(dict.fromkeys(value))


class SessionCreate(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class PromoteRequest(BaseModel):
    stage: str = Field(..., pattern="^(staging|production|archived)$")


class DriftCheckRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(..., max_length=20000)
