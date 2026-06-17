from fastapi.testclient import TestClient

from app.main import app
from app.providers.kbeauty_keywords import build_kbeauty_keyword_playbook
from app.providers.tiktok import TikTokDiscoveryRunRequest
from app.providers.tiktok import run_discovery


client = TestClient(app)


def test_kbeauty_keyword_playbook_balances_twenty_thirty_intents() -> None:
    items = build_kbeauty_keyword_playbook(
        countries=["MX"],
        product_categories=["sunscreen"],
        max_keywords_per_country_category=8,
    )

    intents = {item.intent_type for item in items}
    queries = " ".join(item.query for item in items).lower()

    assert {"trend", "discovery", "concern", "format", "commerce"}.issubset(intents)
    assert "viral" in queries
    assert "grwm" in queries
    assert "protector solar coreano" in queries
    assert any(item.audience in {"gen_z", "young_millennial"} for item in items)


def test_tiktok_provider_dry_run_returns_recent_20_payloads() -> None:
    result = run_discovery(
        TikTokDiscoveryRunRequest(
            provider="apify",
            countries=["MX"],
            product_categories=["sunscreen"],
            max_keywords_per_country_category=2,
            max_results_per_query=1,
            recent_posts_per_creator=20,
            dry_run=True,
        )
    )

    assert result.status == "dry_run_completed"
    assert result.provider == "apify"
    assert result.creator_count == 2
    assert result.video_count == 40
    assert result.creator_import_payload["source_type"] == "approved_provider"
    assert result.quality_gates["recent_20_coverage"]["ready_creators"] == 2
    assert result.provider_request_preview is not None
    assert "searchQueries" in result.provider_request_preview["input"]
    assert result.provider_request_preview["input"]["searchSection"] == "/video"


def test_tiktok_provider_live_blocks_without_allow_flag() -> None:
    result = run_discovery(
        TikTokDiscoveryRunRequest(
            provider="apify",
            countries=["MX"],
            product_categories=["sunscreen"],
            max_keywords_per_country_category=1,
            max_results_per_query=1,
            dry_run=False,
            allow_live_provider_calls=False,
        )
    )

    assert result.status == "blocked"
    assert any("ALLOW_LIVE_TIKTOK_PROVIDER_CALLS" in error for error in result.errors)


def test_tiktok_provider_status_endpoint() -> None:
    response = client.get("/providers/tiktok/status", headers={"X-User-Role": "operator"})

    assert response.status_code == 200
    body = response.json()
    assert body["default_provider"] == "apify"
    assert any(item["provider"] == "apify" for item in body["capabilities"])


def test_tiktok_keyword_playbook_endpoint() -> None:
    response = client.get(
        "/providers/tiktok/keyword-playbook",
        headers={"X-User-Role": "campaign_manager"},
        params={
            "countries": "MX,PE",
            "product_categories": "sunscreen",
            "max_keywords_per_country_category": 3,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "latam_kbeauty_20s_30s"
    assert body["keyword_count"] == 6
    assert {item["country"] for item in body["items"]} == {"MX", "PE"}


def test_tiktok_discovery_run_endpoint_dry_run() -> None:
    response = client.post(
        "/providers/tiktok/discovery-runs",
        headers={"X-User-Role": "operator"},
        json={
            "provider": "apify",
            "countries": ["MX"],
            "product_categories": ["sunscreen"],
            "max_keywords_per_country_category": 2,
            "max_results_per_query": 1,
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dry_run_completed"
    assert body["creator_count"] == 2
    assert body["quality_gates"]["minimum_viable_for_screening"] is True
