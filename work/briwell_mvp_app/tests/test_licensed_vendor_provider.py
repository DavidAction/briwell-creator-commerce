import dataclasses

import pytest

from app.core.config import settings as global_settings
from app.core.policy import ALLOWED_COLLECTION_SOURCE_TYPES
from app.providers import licensed_vendor
from app.providers.base import ProviderRunRequest
from app.providers.registry import get_provider
from app.providers.licensed_vendor import LicensedVendorProvider


def _patched_settings(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    patched = dataclasses.replace(global_settings, **overrides)
    monkeypatch.setattr(licensed_vendor, "settings", patched)


def test_registered_with_correct_source_type_and_risk() -> None:
    provider = get_provider("licensed_vendor")
    assert isinstance(provider, LicensedVendorProvider)
    assert provider.name == "licensed_vendor"
    assert provider.source_type == "approved_provider"
    assert provider.source_risk_level == "low_medium"
    assert provider.source_type in ALLOWED_COLLECTION_SOURCE_TYPES


def test_status_reports_approved_provider_low_medium_risk_and_dry_run_default() -> None:
    provider = LicensedVendorProvider()
    status = provider.status()
    assert status.name == "licensed_vendor"
    assert status.source_type == "approved_provider"
    assert status.source_risk_level == "low_medium"
    assert status.dry_run_default is True
    assert status.live_supported is True
    assert status.limits


def test_status_configured_reflects_vendor_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_settings(monkeypatch, data365_api_key="", brightdata_api_key="")
    provider = LicensedVendorProvider()
    assert provider.status().configured is False

    _patched_settings(monkeypatch, data365_api_key="d365_test", brightdata_api_key="")
    assert provider.status().configured is True

    _patched_settings(monkeypatch, data365_api_key="", brightdata_api_key="bd_test")
    assert provider.status().configured is True


def test_dry_run_default_makes_no_network_calls_and_returns_deterministic_output() -> None:
    provider = LicensedVendorProvider()
    result = provider.run(ProviderRunRequest())

    assert result.status == "dry_run_completed"
    assert result.mode == "dry_run"
    assert result.provider == "licensed_vendor"
    assert result.source_type == "approved_provider"
    assert result.creator_count == len(result.creators)
    assert result.video_count == sum(len(v) for v in result.videos_by_creator.values())
    assert result.creator_count > 0
    assert not result.errors

    for creator in result.creators:
        assert creator.source_type == "approved_provider"
        assert creator.source_risk_level == "low_medium"
        assert creator.provider == "licensed_vendor"

    for videos in result.videos_by_creator.values():
        for video in videos:
            assert video.source_type == "approved_provider"
            assert video.source_risk_level == "low_medium"
            assert video.provider == "licensed_vendor"


def test_dry_run_output_is_deterministic_across_calls() -> None:
    provider = LicensedVendorProvider()
    first = provider.run(ProviderRunRequest(dry_run=True, max_results=2))
    second = provider.run(ProviderRunRequest(dry_run=True, max_results=2))

    assert [c.username for c in first.creators] == [c.username for c in second.creators]
    assert first.creator_import_payload == second.creator_import_payload
    assert first.video_import_payloads == second.video_import_payloads


def test_dry_run_respects_max_results_and_recent_posts_per_creator() -> None:
    provider = LicensedVendorProvider()
    result = provider.run(
        ProviderRunRequest(dry_run=True, max_results=2, recent_posts_per_creator=5)
    )
    assert result.creator_count == 2
    for videos in result.videos_by_creator.values():
        assert len(videos) == 5


def test_import_payload_shapes_match_repository_expectations() -> None:
    provider = LicensedVendorProvider()
    result = provider.run(ProviderRunRequest(dry_run=True, max_results=1))

    assert result.creator_import_payload["source_type"] == "approved_provider"
    assert result.creator_import_payload["source_risk_level"] == "low_medium"
    creator_items = result.creator_import_payload["items"]
    assert len(creator_items) == result.creator_count
    for item in creator_items:
        assert {"country", "username", "profile_url"}.issubset(item)

    assert len(result.video_import_payloads) == len(result.videos_by_creator)
    for video_payload in result.video_import_payloads:
        assert video_payload["source_type"] == "approved_provider"
        assert video_payload["source_risk_level"] == "low_medium"
        assert "provider_creator_id" in video_payload
        for video_item in video_payload["items"]:
            assert "url" in video_item


def test_live_without_flag_key_or_contract_is_blocked_not_crashed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_settings(
        monkeypatch,
        data365_api_key="",
        brightdata_api_key="",
        licensed_vendor_contract_confirmed=False,
        allow_live_provider_calls=False,
    )

    provider = LicensedVendorProvider()
    result = provider.run(
        ProviderRunRequest(dry_run=False, allow_live_provider_calls=False)
    )

    assert result.status == "blocked"
    assert result.mode == "live"
    assert result.creator_count == 0
    assert result.video_count == 0
    assert result.errors
    assert any("ALLOW_LIVE_PROVIDER_CALLS" in error for error in result.errors)


def test_live_with_flag_and_key_but_without_contract_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_settings(
        monkeypatch,
        data365_api_key="d365_test",
        brightdata_api_key="",
        licensed_vendor_contract_confirmed=False,
    )

    provider = LicensedVendorProvider()
    result = provider.run(
        ProviderRunRequest(dry_run=False, allow_live_provider_calls=True)
    )

    assert result.status == "blocked"
    assert result.creator_count == 0
    assert result.errors
    assert any("LICENSED_VENDOR_CONTRACT_CONFIRMED" in error for error in result.errors)
    assert any("contract" in action.lower() for action in result.next_actions)


def test_live_with_flag_and_contract_but_without_key_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patched_settings(
        monkeypatch,
        data365_api_key="",
        brightdata_api_key="",
        licensed_vendor_contract_confirmed=True,
    )

    provider = LicensedVendorProvider()
    result = provider.run(
        ProviderRunRequest(dry_run=False, allow_live_provider_calls=True)
    )

    assert result.status == "blocked"
    assert result.creator_count == 0
    assert result.errors
    assert any("DATA365_API_KEY" in error for error in result.errors)


def test_live_with_all_gates_satisfied_is_still_blocked_pending_client_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Even with the flag enabled, a configured key, AND a confirmed
    # contract, no real network call is ever made in tests: there is no
    # live vendor API client wired up yet, so the provider stays blocked.
    _patched_settings(
        monkeypatch,
        data365_api_key="d365_test",
        brightdata_api_key="",
        licensed_vendor_contract_confirmed=True,
    )

    provider = LicensedVendorProvider()
    result = provider.run(
        ProviderRunRequest(dry_run=False, allow_live_provider_calls=True)
    )

    assert result.status == "blocked"
    assert result.mode == "live"
    assert result.creator_count == 0
    assert result.video_count == 0
    assert result.errors


def test_brightdata_vendor_selected_via_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _patched_settings(
        monkeypatch,
        data365_api_key="",
        brightdata_api_key="",
        licensed_vendor_contract_confirmed=False,
    )
    provider = LicensedVendorProvider()
    result = provider.run(
        ProviderRunRequest(
            dry_run=False,
            allow_live_provider_calls=True,
            payload={"vendor": "brightdata"},
        )
    )
    assert result.status == "blocked"
    assert any("BRIGHTDATA_API_KEY" in error for error in result.errors)


@pytest.mark.parametrize("country", ["MX", "PE", "EC"])
def test_dry_run_supports_all_policy_countries(country: str) -> None:
    provider = LicensedVendorProvider()
    result = provider.run(ProviderRunRequest(dry_run=True, countries=[country], max_results=1))
    assert result.creators[0].country == country
    assert result.creators[0].source_type in ALLOWED_COLLECTION_SOURCE_TYPES
