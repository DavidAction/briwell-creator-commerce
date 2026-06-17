from app.ai.adapters import MockAIAdapter
from app.ai.contracts import AnalysisRequest
from app.ai.gemini import GeminiTextAdapter


def test_mock_ai_adapter_accepts_low_medium_source() -> None:
    adapter = MockAIAdapter()
    result = adapter.run(
        AnalysisRequest(
            task_type="profile_analysis",
            model_alias="low_cost_text",
            source_risk_level="low_medium",
            prompt_version="profile_v0",
            payload={"username": "creator"},
        )
    )
    assert result.status == "ok"
    assert result.confidence == 0.8
    assert result.evidence


def test_mock_ai_adapter_rejects_high_risk_source() -> None:
    adapter = MockAIAdapter()
    result = adapter.run(
        AnalysisRequest(
            task_type="profile_analysis",
            model_alias="low_cost_text",
            source_risk_level="high",
            prompt_version="profile_v0",
            payload={"username": "creator"},
        )
    )
    assert result.status == "rejected"
    assert result.error_code == "source_risk_not_allowed"
    assert result.review_required is True


def test_gemini_text_adapter_dry_run_profile_analysis() -> None:
    adapter = GeminiTextAdapter(dry_run=True)
    result = adapter.run(
        AnalysisRequest(
            task_type="profile_analysis",
            model_alias="low_cost_text",
            source_risk_level="low",
            prompt_version="profile_v0",
            payload={
                "creator": {
                    "country": "MX",
                    "username": "creator_mx",
                    "profile_url": "https://example.com/@creator_mx",
                    "bio": "skincare and kbeauty reviews",
                    "language": "es",
                }
            },
        )
    )
    assert result.status == "ok"
    assert result.output["status"] == "ok"
    assert result.output["primary_country"] == "MX"
    assert result.evidence


def test_gemini_text_adapter_rejects_high_risk_before_provider_call() -> None:
    adapter = GeminiTextAdapter(dry_run=False, allow_live_provider_calls=True, api_key="fake")
    result = adapter.run(
        AnalysisRequest(
            task_type="profile_analysis",
            model_alias="low_cost_text",
            source_risk_level="high",
            prompt_version="profile_v0",
            payload={"creator": {"username": "creator"}},
        )
    )
    assert result.status == "rejected"
    assert result.error_code == "source_risk_not_allowed"


def test_gemini_text_adapter_requires_key_for_live_call() -> None:
    adapter = GeminiTextAdapter(dry_run=False, allow_live_provider_calls=True, api_key="")
    result = adapter.run(
        AnalysisRequest(
            task_type="profile_analysis",
            model_alias="low_cost_text",
            source_risk_level="low",
            prompt_version="profile_v0",
            payload={"creator": {"username": "creator"}},
        )
    )
    assert result.status == "error"
    assert result.error_code == "provider_api_key_missing"
