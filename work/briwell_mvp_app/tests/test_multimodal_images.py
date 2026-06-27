import json

import httpx

from app.ai.contracts import AnalysisRequest
from app.ai.gemini import GeminiTextAdapter


def _fake_response():
    output = {
        "status": "ok",
        "product_visibility_score": 70,
        "skincare_context_score": 70,
        "content_quality_score": 70,
        "brand_safety_score": 85,
        "commerce_signal_score": 60,
        "audio_transcript_available": True,
        "visible_product_types": ["sunscreen"],
        "frame_observations": ["sunscreen applied on camera"],
        "detected_risks": [],
        "scene_summary": "Creator applies sunscreen on camera.",
        "suggested_campaign_angle": "Daily SPF routine demo.",
        "evidence": ["frame image and caption provided"],
        "missing_data": [],
        "confidence": 0.7,
        "review_required": False,
    }

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(output)}]}}]}

    return _Resp()


def _run_multimodal(monkeypatch, frame_samples):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _fake_response()

    monkeypatch.setattr(httpx, "post", fake_post)
    adapter = GeminiTextAdapter(dry_run=False, allow_live_provider_calls=True, api_key="test-key")
    result = adapter.run(
        AnalysisRequest(
            task_type="multimodal_analysis",
            model_alias="multimodal_default",
            source_risk_level="low",
            prompt_version="multimodal_v0",
            payload={"frame_samples": frame_samples},
        )
    )
    return result, captured["json"]["contents"][0]["parts"]


def test_multimodal_live_sends_inline_image(monkeypatch) -> None:
    result, parts = _run_multimodal(
        monkeypatch,
        [{"description": "creator applying sunscreen", "image_base64": "QUJD", "image_mime_type": "image/png"}],
    )
    assert result.status == "ok"
    inline = [part for part in parts if "inlineData" in part]
    assert len(inline) == 1
    assert inline[0]["inlineData"]["mimeType"] == "image/png"
    assert inline[0]["inlineData"]["data"] == "QUJD"
    assert any("text" in part for part in parts)  # text prompt still present


def test_multimodal_without_image_sends_text_only(monkeypatch) -> None:
    _result, parts = _run_multimodal(monkeypatch, [{"description": "no image provided"}])
    assert not any("inlineData" in part for part in parts)
    assert any("text" in part for part in parts)
