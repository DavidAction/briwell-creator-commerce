from fastapi.testclient import TestClient

from app.main import app
from app.providers.registry import PROVIDERS


client = TestClient(app)


def test_providers_status_lists_all_registered_providers_with_source_type() -> None:
    response = client.get(
        "/providers/status",
        headers={"X-User-Role": "operator"},
    )
    assert response.status_code == 200
    body = response.json()
    items = body["items"]
    assert len(items) == len(PROVIDERS)

    by_name = {item["name"]: item for item in items}
    assert set(by_name) == set(PROVIDERS)

    assert by_name["apify"]["source_type"] == "provider_scrape"
    assert by_name["creator_provided"]["source_type"] == "creator_provided"
    assert by_name["tiktok_official"]["source_type"] == "official_api"
    assert by_name["licensed_vendor"]["source_type"] == "approved_provider"


def test_providers_status_rejects_viewer_role() -> None:
    response = client.get(
        "/providers/status",
        headers={"X-User-Role": "viewer"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_apify_discovery_run_dry_run_returns_200() -> None:
    response = client.post(
        "/providers/apify/discovery-runs",
        headers={"X-User-Role": "operator"},
        json={
            "countries": ["MX"],
            "product_categories": ["sunscreen"],
            "max_results": 1,
            "recent_posts_per_creator": 5,
            "dry_run": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dry_run_completed"
    assert body["mode"] == "dry_run"
    assert body["provider"] == "apify"
    assert body["source_type"] == "provider_scrape"


def test_discovery_run_rejects_viewer_role() -> None:
    response = client.post(
        "/providers/apify/discovery-runs",
        headers={"X-User-Role": "viewer"},
        json={"dry_run": True},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_unknown_provider_discovery_run_returns_404() -> None:
    response = client.post(
        "/providers/does-not-exist/discovery-runs",
        headers={"X-User-Role": "operator"},
        json={"dry_run": True},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["code"] == "PROVIDER_NOT_FOUND"
    assert "does-not-exist" in body["detail"]["message"]


def test_creator_provided_import_returns_200_with_normalized_payload() -> None:
    response = client.post(
        "/providers/creator-provided/import",
        headers={"X-User-Role": "operator"},
        json={
            "max_results": 5,
            "recent_posts_per_creator": 5,
            "payload": {
                "rows": [
                    {
                        "country": "MX",
                        "username": "creator_router_test",
                        "profile_url": "https://www.tiktok.com/@creator_router_test",
                        "follower_count": 5000,
                        "consent_ref": "router-test-consent",
                    }
                ]
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "creator_provided"
    assert body["source_type"] == "creator_provided"
    assert body["creator_count"] == 1
    assert body["creator_import_payload"]["source_type"] == "creator_provided"
    assert body["creator_import_payload"]["items"][0]["username"] == "creator_router_test"


def test_creator_provided_import_rejects_campaign_manager_write_but_allows_read_role() -> None:
    # campaign_manager is explicitly allowed for the import endpoint (uploads are
    # often coordinated by campaign managers), viewer is not.
    response = client.post(
        "/providers/creator-provided/import",
        headers={"X-User-Role": "viewer"},
        json={"payload": {}},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"
