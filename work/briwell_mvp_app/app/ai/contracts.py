from typing import Any, Literal

from pydantic import BaseModel, Field


AnalysisStatus = Literal["ok", "rejected", "error"]


class AnalysisRequest(BaseModel):
    task_type: str = Field(min_length=1)
    model_alias: str = Field(min_length=1)
    source_risk_level: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    status: AnalysisStatus
    model_alias: str
    prompt_version: str
    output: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    review_required: bool = False
    review_required_reason: str | None = None
    error_code: str | None = None
