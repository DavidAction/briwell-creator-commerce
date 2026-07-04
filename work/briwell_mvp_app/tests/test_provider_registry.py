import pytest

from app.providers.apify_provider import ApifyProvider
from app.providers.base import CreatorDataProvider, ProviderRunRequest, ProviderStatus
from app.providers.registry import PROVIDERS, UnknownProviderError, get_provider, list_status


def test_registry_contains_apify_provider() -> None:
    assert "apify" in PROVIDERS
    assert isinstance(PROVIDERS["apify"], ApifyProvider)


def test_get_provider_returns_registered_provider() -> None:
    provider = get_provider("apify")
    assert isinstance(provider, CreatorDataProvider)
    assert provider.name == "apify"
    assert provider.source_type == "provider_scrape"
    assert provider.source_risk_level == "low_medium"


def test_get_provider_unknown_name_raises_clear_error() -> None:
    with pytest.raises(UnknownProviderError) as exc_info:
        get_provider("does-not-exist")

    message = str(exc_info.value)
    assert "does-not-exist" in message
    assert "apify" in message


def test_get_provider_unknown_name_is_not_a_crash() -> None:
    # UnknownProviderError is a KeyError subclass: callers can catch it
    # specifically or as a KeyError without a generic exception escaping.
    with pytest.raises(KeyError):
        get_provider("unknown")


def test_list_status_returns_status_for_every_registered_provider() -> None:
    statuses = list_status()
    assert len(statuses) == len(PROVIDERS)
    assert all(isinstance(item, ProviderStatus) for item in statuses)
    names = {item.name for item in statuses}
    assert names == set(PROVIDERS)


def test_list_status_apify_entry_matches_policy_source_type() -> None:
    statuses = {item.name: item for item in list_status()}
    apify_status = statuses["apify"]
    assert apify_status.source_type == "provider_scrape"
    assert apify_status.source_risk_level == "low_medium"
    assert apify_status.dry_run_default is True


def test_apify_provider_run_dry_run_matches_import_payload_shape() -> None:
    provider = get_provider("apify")
    result = provider.run(
        ProviderRunRequest(
            countries=["MX"],
            product_categories=["sunscreen"],
            max_results=1,
            recent_posts_per_creator=20,
            dry_run=True,
        )
    )

    assert result.status == "dry_run_completed"
    assert result.mode == "dry_run"
    assert result.provider == "apify"
    assert result.source_type == "provider_scrape"
    assert result.creator_count == len(result.creators)
    assert result.video_count == sum(len(v) for v in result.videos_by_creator.values())

    assert result.creator_import_payload["source_type"] == "provider_scrape"
    assert result.creator_import_payload["source_risk_level"] == "low_medium"
    creator_items = result.creator_import_payload["items"]
    assert len(creator_items) == result.creator_count
    for item in creator_items:
        assert {"country", "username", "profile_url"}.issubset(item)

    assert len(result.video_import_payloads) == len(result.videos_by_creator)
    for video_payload in result.video_import_payloads:
        assert video_payload["source_type"] == "provider_scrape"
        assert video_payload["source_risk_level"] == "low_medium"
        assert "provider_creator_id" in video_payload
        for video_item in video_payload["items"]:
            assert "url" in video_item


def test_apify_provider_run_live_without_flag_is_blocked_not_crashed() -> None:
    provider = get_provider("apify")
    result = provider.run(
        ProviderRunRequest(
            countries=["MX"],
            product_categories=["sunscreen"],
            max_results=1,
            dry_run=False,
            allow_live_provider_calls=False,
        )
    )

    assert result.status == "blocked"
    assert result.creator_count == 0
    assert result.video_count == 0
    assert result.errors
