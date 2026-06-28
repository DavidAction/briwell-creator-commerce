from fastapi.testclient import TestClient

from app.ai.dm import build_ai_dm_drafts
from app.main import app
from app.routers import outreach as outreach_module


client = TestClient(app)


def _creator() -> dict:
    return {
        "creator_id": "creator-1",
        "username": "luzskincare",
        "display_name": "Luz Skincare",
        "country": "MX",
        "profile_url": "https://www.tiktok.com/@luzskincare",
        "source_risk_level": "low",
        "bio": "K-beauty skincare reviews",
        "follower_count": 42000,
    }


def test_ai_dm_drafts_dry_run_returns_three_spanish_variants() -> None:
    result = build_ai_dm_drafts(
        _creator(),
        product_category="sunscreen",
        country="MX",
        dry_run=True,
        allow_live_provider_calls=False,
    )
    assert result["status"] == "generated"
    assert result["source"] == "ai_dry_run"
    assert len(result["drafts"]) == 3
    variants = {d["variant"] for d in result["drafts"]}
    assert "soft_intro" in variants and "commerce_collaboration" in variants
    assert all("Hola" in d["message"] for d in result["drafts"])
    assert all(d["claims_check_status"] == "needs_review" for d in result["drafts"])


def test_ai_dm_drafts_fall_back_to_templates_on_failure(monkeypatch) -> None:
    # Force the AI run to fail; the function must still return usable template drafts.
    class _Failed:
        status = "failed"

        class result:
            status = "error"
            error_code = "provider_call_failed"

    monkeypatch.setattr("app.workers.analysis_runner.run_analysis", lambda *_a, **_k: _Failed())
    result = build_ai_dm_drafts(_creator(), product_category="sunscreen", dry_run=True)
    assert result["source"] == "template_fallback"
    assert len(result["drafts"]) >= 2


def test_generate_dm_endpoint_with_ai(monkeypatch) -> None:
    def _stub(creator, product_category, product_name=None, country=None, dry_run=True,
              allow_live_provider_calls=False, source_risk_level="low"):
        return {
            "status": "generated",
            "source": "ai_dry_run",
            "drafts": [
                {"variant": "soft_intro", "message": "Hola", "personalization_evidence": [],
                 "product_angle": "", "claims_check_status": "needs_review"},
                {"variant": "product_review", "message": "Hola", "personalization_evidence": [],
                 "product_angle": "", "claims_check_status": "needs_review"},
                {"variant": "commerce_collaboration", "message": "Hola", "personalization_evidence": [],
                 "product_angle": "", "claims_check_status": "needs_review"},
            ],
        }

    monkeypatch.setattr(outreach_module, "build_ai_dm_drafts", _stub)
    response = client.post(
        "/outreach/creator-1/generate-dm",
        headers={"X-User-Role": "operator"},
        json={
            "product_category": "sunscreen",
            "use_ai": True,
            "country": "MX",
            "creator_snapshot": {
                "country": "MX",
                "username": "creator_mx",
                "profile_url": "https://www.tiktok.com/@creator_mx",
                "source_risk_level": "low",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dm_source"]["source"] == "ai_dry_run"
    assert len(body["drafts"]) >= 2
    assert body["review_required"] is True
