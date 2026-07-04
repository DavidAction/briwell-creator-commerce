import dataclasses

import pytest

from app.core.config import settings as global_settings
from app.core.policy import ALLOWED_COLLECTION_SOURCE_TYPES
from app.providers import tiktok_official
from app.providers.base import ProviderRunRequest
from app.providers.registry import get_provider
from app.providers.tiktok_official import TikTokOfficialProvider


def _patched_settings(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    patched = dataclasses.replace(global_settings, **overrides)
    monkeypatch.setattr(tiktok_official, "settings", patched)


def test_registered_with_correct_source_type_and_risk() -> None:
    provider = get_provider("tiktok_official")
    assert isinstance(provider, TikTokOfficialProvider)
    assert provider.name == "tiktok_official"
    assert provider.source_type == "official_api"
    assert provider.source_risk_level == "low"
    assert provider.source_type in ALLOWED_COLLECTION_SOURCE_TYPES


def test_status_reports_official_api_low_risk_and_dry_run_default() -> None:
    provider = TikTokOfficialProvider()
    status = provider.status()
    assert status.name == "tiktok_official"
    assert status.source_type == "official_api"
    assert status.source_risk_level == "low"
    assert status.dry_run_default is True
    assert status.live_supported is True
    assert status.limits


def test_status_configured_reflects_client_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_settings(monkeypatch, tiktok_client_key="", tiktok_client_secret="")
    provider = TikTokOfficialProvider()
    assert provider.status().configured is False

    _patched_settings(monkeypatch, tiktok_client_key="ck_test", tiktok_client_secret="cs_test")
    assert provider.status().configured is True


def test_dry_run_default_makes_no_network_calls_and_returns_deterministic_output() -> None:
    provider = TikTokOfficialProvider()
    result = provider.run(ProviderRunRequest())

    assert result.status == "dry_run_completed"
    assert result.mode == "dry_run"
    assert result.provider == "tiktok_official"
    assert result.source_type == "official_api"
    assert result.creator_count == len(result.creators)
    assert result.video_count == sum(len(v) for v in result.videos_by_creator.values())
    assert result.creator_count > 0
    assert not result.errors

    for creator in result.creators:
        assert creator.source_type == "official_api"
        assert creator.source_risk_level == "low"
        assert creator.provider == "tiktok_official"

    for videos in result.videos_by_creator.values():
        for video in videos:
            assert video.source_type == "official_api"
            assert video.source_risk_level == "low"
            assert video.provider == "tiktok_official"


def test_dry_run_output_is_deterministic_across_calls() -> None:
    provider = TikTokOfficialProvider()
    first = provider.run(ProviderRunRequest(dry_run=True, max_results=2))
    second = provider.run(ProviderRunRequest(dry_run=True, max_results=2))

    assert [c.username for c in first.creators] == [c.username for c in second.creators]
    assert first.creator_import_payload == second.creator_import_payload
    assert first.video_import_payloads == second.video_import_payloads


def test_dry_run_respects_max_results_and_recent_posts_per_creator() -> None:
    provider = TikTokOfficialProvider()
    result = provider.run(
        ProviderRunRequest(dry_run=True, max_results=2, recent_posts_per_creator=5)
    )
    assert result.creator_count == 2
    for videos in result.videos_by_creator.values():
        assert len(videos) == 5


def test_import_payload_shapes_match_repository_expectations() -> None:
    provider = TikTokOfficialProvider()
    result = provider.run(ProviderRunRequest(dry_run=True, max_results=1))

    assert result.creator_import_payload["source_type"] == "official_api"
    assert result.creator_import_payload["source_risk_level"] == "low"
    creator_items = result.creator_import_payload["items"]
    assert len(creator_items) == result.creator_count
    for item in creator_items:
        assert {"country", "username", "profile_url"}.issubset(item)

    assert len(result.video_import_payloads) == len(result.videos_by_creator)
    for video_payload in result.video_import_payloads:
        assert video_payload["source_type"] == "official_api"
        assert video_payload["source_risk_level"] == "low"
        assert "provider_creator_id" in video_payload
        for video_item in video_payload["items"]:
            assert "url" in video_item


def test_live_without_flag_or_keys_is_blocked_not_crashed(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_settings(
        monkeypatch,
        tiktok_client_key="",
        tiktok_client_secret="",
        tiktok_access_token="",
        allow_live_provider_calls=False,
    )

    provider = TikTokOfficialProvider()
    result = provider.run(
        ProviderRunRequest(dry_run=False, allow_live_provider_calls=False)
    )

    assert result.status == "blocked"
    assert result.mode == "live"
    assert result.creator_count == 0
    assert result.video_count == 0
    assert result.errors
    assert any("ALLOW_LIVE_PROVIDER_CALLS" in error for error in result.errors)


def test_live_with_flag_but_no_keys_is_still_blocked() -> None:
    provider = TikTokOfficialProvider()
    result = provider.run(
        ProviderRunRequest(dry_run=False, allow_live_provider_calls=True)
    )

    assert result.status == "blocked"
    assert result.creator_count == 0
    assert result.errors


def test_live_with_flag_and_keys_is_still_blocked_pending_oauth_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Even with credentials configured and the live flag enabled, no real
    # network call is ever made in tests: no automated per-creator OAuth
    # token exchange is wired up, so the provider stays blocked rather than
    # attempting a live call.
    _patched_settings(
        monkeypatch,
        tiktok_client_key="ck_test",
        tiktok_client_secret="cs_test",
        tiktok_access_token="at_test",
    )

    provider = TikTokOfficialProvider()
    result = provider.run(
        ProviderRunRequest(dry_run=False, allow_live_provider_calls=True)
    )

    assert result.status == "blocked"
    assert result.mode == "live"
    assert result.creator_count == 0
    assert result.video_count == 0
    assert result.errors


def test_research_api_surface_live_is_not_implemented() -> None:
    provider = TikTokOfficialProvider()
    result = provider.run(
        ProviderRunRequest(
            dry_run=False,
            allow_live_provider_calls=True,
            payload={"surface": "research_api"},
        )
    )
    assert result.status == "not_implemented"
    assert result.creator_count == 0
    assert result.errors


def test_research_api_surface_dry_run_still_returns_dummy_output() -> None:
    provider = TikTokOfficialProvider()
    result = provider.run(
        ProviderRunRequest(dry_run=True, payload={"surface": "research_api"})
    )
    assert result.status == "dry_run_completed"
    assert result.creator_count > 0


@pytest.mark.parametrize("country", ["MX", "PE", "EC"])
def test_dry_run_supports_all_policy_countries(country: str) -> None:
    provider = TikTokOfficialProvider()
    result = provider.run(ProviderRunRequest(dry_run=True, countries=[country], max_results=1))
    assert result.creators[0].country == country
    assert result.creators[0].source_type in ALLOWED_COLLECTION_SOURCE_TYPES
