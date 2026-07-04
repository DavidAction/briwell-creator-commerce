import pytest

from app.core.policy import ALLOWED_COLLECTION_SOURCE_TYPES
from app.providers.base import ProviderRunRequest
from app.providers.creator_provided import CreatorProvidedProvider
from app.providers.registry import get_provider


def test_creator_provided_registered_with_correct_source_type_and_risk() -> None:
    provider = get_provider("creator_provided")
    assert isinstance(provider, CreatorProvidedProvider)
    assert provider.name == "creator_provided"
    assert provider.source_type == "creator_provided"
    assert provider.source_risk_level == "low"
    assert provider.source_type in ALLOWED_COLLECTION_SOURCE_TYPES


def test_status_reports_low_risk_and_dry_run_default() -> None:
    provider = CreatorProvidedProvider()
    status = provider.status()
    assert status.name == "creator_provided"
    assert status.source_type == "creator_provided"
    assert status.source_risk_level == "low"
    assert status.configured is True
    assert status.dry_run_default is True
    assert status.limits


def test_dry_run_with_no_payload_returns_deterministic_sample() -> None:
    provider = CreatorProvidedProvider()
    result = provider.run(ProviderRunRequest())

    assert result.status == "dry_run_completed"
    assert result.mode == "dry_run"
    assert result.provider == "creator_provided"
    assert result.source_type == "creator_provided"
    assert result.creator_count == 1
    assert result.video_count == 1
    assert not result.errors

    creator = result.creators[0]
    assert creator.source_type == "creator_provided"
    assert creator.source_risk_level == "low"
    assert creator.country == "MX"

    videos = result.videos_by_creator[creator.provider_creator_id]
    assert len(videos) == 1
    assert videos[0].source_type == "creator_provided"
    assert videos[0].source_risk_level == "low"


def test_dry_run_sample_is_deterministic_across_calls() -> None:
    provider = CreatorProvidedProvider()
    first = provider.run(ProviderRunRequest())
    second = provider.run(ProviderRunRequest())
    assert first.creators[0].username == second.creators[0].username
    assert first.creator_import_payload == second.creator_import_payload


def test_real_rows_supplied_produces_live_completed() -> None:
    provider = CreatorProvidedProvider()
    payload = {
        "creators": [
            {
                "provider_creator_id": "real-1",
                "country": "PE",
                "username": "real.creator",
                "display_name": "Real Creator",
                "profile_url": "https://www.tiktok.com/@real.creator",
                "bio": "My own skincare content.",
                "follower_count": 15000,
                "avg_views": 4000,
                "engagement_rate": 3.1,
                "product_category": "cleanser",
                "signals": ["own_upload"],
                "consent_ref": "consent-abc-123",
                "provided_at": "2026-07-02T10:00:00Z",
            }
        ],
        "videos_by_creator": {
            "real-1": [
                {
                    "url": "https://www.tiktok.com/@real.creator/video/123",
                    "platform_video_id": "123",
                    "caption": "My real post",
                    "hashtags": ["kbeauty"],
                    "posted_at": "2026-06-15T08:00:00Z",
                    "view_count": 5000,
                    "like_count": 300,
                    "consent_ref": "consent-abc-123",
                    "provided_at": "2026-07-02T10:00:00Z",
                }
            ]
        },
    }

    result = provider.run(ProviderRunRequest(payload=payload))

    assert result.status == "live_completed"
    assert result.mode == "live"
    assert result.creator_count == 1
    assert result.video_count == 1
    assert not result.errors

    creator = result.creators[0]
    assert creator.provider_creator_id == "real-1"
    assert creator.username == "real.creator"
    assert creator.country == "PE"
    assert creator.source_type == "creator_provided"
    assert creator.source_risk_level == "low"
    assert creator.raw_metadata["consent_ref"] == "consent-abc-123"
    assert creator.raw_metadata["provided_at"] == "2026-07-02T10:00:00Z"
    assert creator.raw_metadata["creator_supplied"] is True

    video = result.videos_by_creator["real-1"][0]
    assert video.url == "https://www.tiktok.com/@real.creator/video/123"
    assert video.source_type == "creator_provided"
    assert video.source_risk_level == "low"
    assert video.raw_metadata["consent_ref"] == "consent-abc-123"


def test_flat_rows_payload_normalizes_creators_only() -> None:
    provider = CreatorProvidedProvider()
    payload = {
        "rows": [
            {
                "country": "EC",
                "username": "flat.creator",
                "profile_url": "https://www.tiktok.com/@flat.creator",
                "follower_count": 9000,
            }
        ]
    }

    result = provider.run(ProviderRunRequest(payload=payload))

    assert result.status == "live_completed"
    assert result.creator_count == 1
    assert result.video_count == 0
    assert result.creators[0].username == "flat.creator"
    assert result.creators[0].country == "EC"


def test_explicit_dry_run_true_with_real_rows_still_marked_dry_run() -> None:
    provider = CreatorProvidedProvider()
    payload = {
        "creators": [
            {
                "country": "MX",
                "username": "forced.dry",
                "profile_url": "https://www.tiktok.com/@forced.dry",
            }
        ]
    }
    result = provider.run(ProviderRunRequest(payload=payload, dry_run=True))
    assert result.status == "dry_run_completed"
    assert result.mode == "dry_run"
    assert result.creators[0].username == "forced.dry"


def test_no_rows_and_dry_run_false_returns_error_not_crash() -> None:
    provider = CreatorProvidedProvider()
    result = provider.run(ProviderRunRequest(dry_run=False))
    assert result.creator_count == 0
    assert result.video_count == 0
    assert result.errors


def test_import_payload_shapes_match_repository_expectations() -> None:
    provider = CreatorProvidedProvider()
    payload = {
        "creators": [
            {
                "provider_creator_id": "shape-1",
                "country": "MX",
                "username": "shape.creator",
                "profile_url": "https://www.tiktok.com/@shape.creator",
            }
        ],
        "videos_by_creator": {
            "shape-1": [
                {"url": "https://www.tiktok.com/@shape.creator/video/9"},
            ]
        },
    }
    result = provider.run(ProviderRunRequest(payload=payload))

    assert result.creator_import_payload["source_type"] == "creator_provided"
    assert result.creator_import_payload["source_risk_level"] == "low"
    creator_items = result.creator_import_payload["items"]
    assert len(creator_items) == 1
    for item in creator_items:
        assert {"country", "username", "profile_url"}.issubset(item)

    assert len(result.video_import_payloads) == 1
    video_payload = result.video_import_payloads[0]
    assert video_payload["source_type"] == "creator_provided"
    assert video_payload["source_risk_level"] == "low"
    assert video_payload["provider_creator_id"] == "shape-1"
    for video_item in video_payload["items"]:
        assert "url" in video_item


@pytest.mark.parametrize(
    "country",
    ["MX", "PE", "EC"],
)
def test_all_supported_countries_pass_policy_and_normalization(country: str) -> None:
    provider = CreatorProvidedProvider()
    payload = {
        "creators": [
            {
                "country": country,
                "username": f"creator.{country.lower()}",
                "profile_url": f"https://www.tiktok.com/@creator.{country.lower()}",
            }
        ]
    }
    result = provider.run(ProviderRunRequest(payload=payload))
    assert result.creators[0].country == country
    assert result.creators[0].source_type in ALLOWED_COLLECTION_SOURCE_TYPES
