import json as json_module

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


def test_gemini_live_recent_posts_uses_structured_output_schema(monkeypatch) -> None:
    captured: dict = {}
    provider_output = {
        "status": "ok",
        "post_count_analyzed": 20,
        "expected_post_count": 20,
        "suitability_decision": "pass_to_full_analysis",
        "suitability_score": 88,
        "beauty_content_ratio": 0.9,
        "kbeauty_signal_ratio": 0.7,
        "skincare_relevance_score": 90,
        "commerce_signal_score": 80,
        "consistency_score": 85,
        "brand_safety_precheck_score": 92,
        "matched_product_categories": ["sunscreen"],
        "recent_post_observations": ["Strong SPF and K-beauty routine fit."],
        "coverage_gaps": [],
        "risk_notes": [],
        "next_step": "run_full_profile_comment_multimodal_analysis",
        "evidence": ["20 approved recent posts were analyzed."],
        "missing_data": [],
        "confidence": 0.86,
        "review_required": False,
        "review_required_reason": None,
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json_module.dumps(provider_output)}],
                        }
                    }
                ]
            }

    def fake_post(url, params, json, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["payload"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.ai.gemini.httpx.post", fake_post)

    adapter = GeminiTextAdapter(
        dry_run=False,
        allow_live_provider_calls=True,
        api_key="fake-key",
        base_url="https://generativelanguage.googleapis.com/v1beta",
    )
    result = adapter.run(
        AnalysisRequest(
            task_type="recent_posts_screen",
            model_alias="recent_posts_screen",
            source_risk_level="low",
            prompt_version="recent_posts_screen_v0",
            payload={
                "creator_id": "creator-1",
                "recent_posts": [
                    {
                        "caption": "Rutina con protector solar coreano SPF.",
                        "transcript": "Textura ligera y link de compra.",
                        "hashtags": ["skincare", "kbeauty"],
                        "view_count": 12000,
                    }
                    for _ in range(20)
                ],
                "expected_post_count": 20,
            },
        )
    )

    assert result.status == "ok"
    assert result.output["suitability_decision"] == "pass_to_full_analysis"
    generation_config = captured["payload"]["generationConfig"]
    schema = generation_config["responseFormat"]["text"]["schema"]
    assert generation_config["responseFormat"]["text"]["mimeType"] == "application/json"
    assert "suitability_decision" in schema["properties"]
    assert "decision_policy" in captured["payload"]["contents"][0]["parts"][0]["text"]
