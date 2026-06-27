from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.ai.contracts import AnalysisRequest
from app.workers.analysis_runner import AnalysisRunRequest
from app.workers.analysis_runner import AnalysisRunResult
from app.workers.analysis_runner import run_analysis


SourceRisk = Literal["low", "low_medium", "medium", "high", "not_allowed"]


class FrameSample(BaseModel):
    timestamp_seconds: float = Field(ge=0)
    description: str = Field(min_length=1, max_length=1000)
    asset_url: str | None = Field(default=None, max_length=2000)
    # Optional raw base64 image (no data: prefix) so live Gemini analyzes the actual
    # frame, not just its text description. Only used on live multimodal calls.
    image_base64: str | None = Field(default=None, repr=False)
    image_mime_type: str = "image/jpeg"


class MultimodalVideoSnapshot(BaseModel):
    video_id: str | None = None
    creator_id: str | None = None
    url: str | None = Field(default=None, max_length=2000)
    caption: str | None = Field(default=None, max_length=3000)
    transcript: str | None = Field(default=None, max_length=10000)
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)


class MultimodalAnalysisRequest(BaseModel):
    source_risk_level: SourceRisk
    video: MultimodalVideoSnapshot
    frame_samples: list[FrameSample] = Field(default_factory=list, max_length=12)
    product_context: dict[str, Any] = Field(default_factory=dict)
    model_alias: str = "multimodal_default"
    prompt_version: str = "multimodal_v0"
    dry_run: bool | None = None
    allow_live_provider_calls: bool | None = None


def run_multimodal_analysis(payload: MultimodalAnalysisRequest) -> AnalysisRunResult:
    return run_analysis(
        AnalysisRunRequest(
            target_entity_type="video",
            target_entity_id=payload.video.video_id,
            dry_run=payload.dry_run,
            allow_live_provider_calls=payload.allow_live_provider_calls,
            request=AnalysisRequest(
                task_type="multimodal_analysis",
                model_alias=payload.model_alias,
                source_risk_level=payload.source_risk_level,
                prompt_version=payload.prompt_version,
                payload={
                    "video": payload.video.model_dump(),
                    "frame_samples": [item.model_dump() for item in payload.frame_samples],
                    "product_context": payload.product_context,
                },
            ),
        )
    )
