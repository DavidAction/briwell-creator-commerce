from fastapi.testclient import TestClient

from app.main import app
from app.operations.intake import validate_intake


client = TestClient(app)


def _creator(**overrides) -> dict:
    base = {
        "country": "MX",
        "username": "luz_kbeauty",
        "profile_url": "https://www.tiktok.com/@luz_kbeauty",
        "source_risk_level": "low",
        "display_name": "Luz",
        "bio": "K-beauty skincare",
        "follower_count": 42000,
        "avg_views": 18000,
        "language": "es",
    }
    base.update(overrides)
    return base


def _posts(count: int = 20) -> list[dict]:
    return [
        {
            "url": f"https://www.tiktok.com/@luz_kbeauty/video/{i}",
            "caption": "Rutina skincare coreana con protector solar SPF.",
            "view_count": 12000 + i,
            "like_count": 800,
            "comment_count": 40,
        }
        for i in range(count)
    ]


def test_valid_manual_intake_is_ready() -> None:
    report = validate_intake("manual", "low", [_creator()], {"luz_kbeauty": _posts(20)})
    assert report["ready_to_import"] is True
    assert report["status"] != "blocked"
    assert report["source_decision"]["allowed"] is True
    assert report["creator_rows"]["missing_required"] == []


def test_blocked_source_type_is_reported_not_thrown() -> None:
    report = validate_intake("scraper", "low", [_creator()])
    assert report["status"] == "blocked"
    assert report["ready_to_import"] is False
    assert report["source_decision"]["allowed"] is False
    assert any("source_type" in reason for reason in report["source_decision"]["reasons"])


def test_provider_scrape_is_allowed_but_flagged() -> None:
    report = validate_intake("provider_scrape", "low_medium", [_creator()])
    assert report["source_decision"]["allowed"] is True
    assert report["source_decision"]["is_scrape_lane"] is True
    assert any("provider_scrape" in note for note in report["notes"])


def test_missing_required_column_blocks_import() -> None:
    report = validate_intake("manual", "low", [_creator(profile_url="")])
    assert report["status"] == "blocked"
    assert report["ready_to_import"] is False
    assert report["creator_rows"]["missing_required"]
    assert "profile_url" in report["creator_rows"]["missing_required"][0]["missing"]


def test_intake_validate_endpoint() -> None:
    response = client.post(
        "/operations/intake-validate",
        headers={"X-User-Role": "operator"},
        json={
            "source_type": "approved_provider",
            "source_risk_level": "low_medium",
            "creators": [_creator()],
            "recent_posts_by_creator": {"luz_kbeauty": _posts(20)},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ready_to_import"] is True
    assert "recommended_coverage" in body["creator_rows"]
    assert body["recent_posts"]["total"] == 20
