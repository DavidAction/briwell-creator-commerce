from abc import ABC, abstractmethod

from app.ai.contracts import AnalysisRequest, AnalysisResult
from app.core.policy import source_risk_decision


class AIAdapter(ABC):
    @abstractmethod
    def run(self, request: AnalysisRequest) -> AnalysisResult:
        raise NotImplementedError


def rejected_for_source_risk(request: AnalysisRequest) -> AnalysisResult | None:
    decision = source_risk_decision(request.source_risk_level)
    if decision.allowed:
        return None
    return AnalysisResult(
        status="rejected",
        model_alias=request.model_alias,
        prompt_version=request.prompt_version,
        output={
            "status": "rejected",
            "reason": decision.reason or "source_risk_not_allowed",
        },
        confidence=1.0,
        review_required=True,
        review_required_reason=decision.reason or "source_risk_not_allowed",
        error_code=decision.reason or "source_risk_not_allowed",
    )


class MockAIAdapter(AIAdapter):
    """Deterministic adapter for tests and local contract validation."""

    def run(self, request: AnalysisRequest) -> AnalysisResult:
        rejected = rejected_for_source_risk(request)
        if rejected is not None:
            return rejected

        return AnalysisResult(
            status="ok",
            model_alias=request.model_alias,
            prompt_version=request.prompt_version,
            output={
                "status": "ok",
                "task_type": request.task_type,
                "summary": "Mock analysis result. Replace with provider adapter.",
            },
            evidence=["Mock evidence from provided payload."],
            missing_data=[],
            confidence=0.8,
            review_required=False,
        )
