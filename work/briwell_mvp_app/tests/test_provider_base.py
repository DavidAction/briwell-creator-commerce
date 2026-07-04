from abc import ABC

import pytest
from pydantic import ValidationError

from app.core.policy import ALLOWED_COLLECTION_SOURCE_TYPES
from app.providers.base import (
    CreatorDataProvider,
    NormalizedCreator,
    NormalizedVideo,
    ProviderRunRequest,
    ProviderRunResult,
    ProviderStatus,
)


def test_creator_data_provider_is_abstract_base_class() -> None:
    assert issubclass(CreatorDataProvider, ABC)
    with pytest.raises(TypeError):
        CreatorDataProvider()  # type: ignore[abstract]


def test_creator_data_provider_requires_status_and_run() -> None:
    class Incomplete(CreatorDataProvider):
        name = "incomplete"
        source_type = "manual"
        source_risk_level = "low"

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_creator_data_provider_concrete_subclass_can_be_instantiated() -> None:
    class Complete(CreatorDataProvider):
        name = "complete"
        source_type = "manual"
        source_risk_level = "low"

        def status(self) -> ProviderStatus:
            return ProviderStatus(
                name=self.name,
                source_type=self.source_type,
                source_risk_level=self.source_risk_level,
                configured=True,
                live_supported=False,
                dry_run_default=True,
                limits=[],
            )

        def run(self, req: ProviderRunRequest) -> ProviderRunResult:
            return ProviderRunResult(
                status="dry_run_completed",
                provider=self.name,
                mode="dry_run",
                source_type=self.source_type,
                creator_count=0,
                video_count=0,
                creators=[],
                videos_by_creator={},
                creator_import_payload={"source_type": self.source_type, "items": []},
                video_import_payloads=[],
            )

    provider = Complete()
    status = provider.status()
    assert status.name == "complete"
    result = provider.run(ProviderRunRequest())
    assert result.status == "dry_run_completed"


def test_provider_status_requires_all_fields() -> None:
    with pytest.raises(ValidationError):
        ProviderStatus(name="x")  # type: ignore[call-arg]

    status = ProviderStatus(
        name="x",
        source_type="manual",
        source_risk_level="low",
        configured=False,
        live_supported=False,
        dry_run_default=True,
        limits=["a limit"],
    )
    assert status.limits == ["a limit"]


def test_normalized_creator_validates_country_literal() -> None:
    with pytest.raises(ValidationError):
        NormalizedCreator(
            provider="apify",
            provider_creator_id="1",
            country="US",  # not in MX/PE/EC
            username="u",
            profile_url="https://tiktok.com/@u",
            source_type="provider_scrape",
            source_risk_level="low_medium",
        )

    creator = NormalizedCreator(
        provider="apify",
        provider_creator_id="1",
        country="MX",
        username="u",
        profile_url="https://tiktok.com/@u",
        source_type="provider_scrape",
        source_risk_level="low_medium",
    )
    assert creator.signals == []
    assert creator.raw_metadata == {}
    assert creator.display_name is None


def test_normalized_creator_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        NormalizedCreator(
            provider="apify",
            provider_creator_id="1",
            country="MX",
            username="u",
            profile_url="https://tiktok.com/@u",
            source_type="provider_scrape",
            source_risk_level="low_medium",
            follower_count=-5,
        )


def test_normalized_video_defaults_and_validation() -> None:
    video = NormalizedVideo(
        provider="apify",
        provider_creator_id="1",
        creator_username="u",
        url="https://tiktok.com/@u/video/1",
        source_type="provider_scrape",
        source_risk_level="low_medium",
    )
    assert video.hashtags == []
    assert video.raw_metadata == {}
    assert video.posted_at is None

    with pytest.raises(ValidationError):
        NormalizedVideo(
            provider="apify",
            provider_creator_id="1",
            creator_username="u",
            url="https://tiktok.com/@u/video/1",
            source_type="provider_scrape",
            source_risk_level="low_medium",
            view_count=-1,
        )


def test_provider_run_request_defaults() -> None:
    req = ProviderRunRequest()
    assert req.countries == ["MX", "PE", "EC"]
    assert req.product_categories == ["sunscreen"]
    assert req.max_results == 3
    assert req.recent_posts_per_creator == 20
    assert req.dry_run is None
    assert req.allow_live_provider_calls is None
    assert req.payload == {}


def test_provider_run_request_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        ProviderRunRequest(max_results=0)
    with pytest.raises(ValidationError):
        ProviderRunRequest(max_results=51)
    with pytest.raises(ValidationError):
        ProviderRunRequest(recent_posts_per_creator=0)
    with pytest.raises(ValidationError):
        ProviderRunRequest(recent_posts_per_creator=21)


def test_provider_run_result_status_literal_is_enforced() -> None:
    with pytest.raises(ValidationError):
        ProviderRunResult(
            status="unsupported_status",  # type: ignore[arg-type]
            provider="apify",
            mode="dry_run",
            source_type="provider_scrape",
            creator_count=0,
            video_count=0,
            creators=[],
            videos_by_creator={},
            creator_import_payload={},
            video_import_payloads=[],
        )


@pytest.mark.parametrize(
    "source_type",
    ["manual", "official_api", "approved_provider", "creator_provided", "provider_scrape"],
)
def test_normalized_models_accept_every_policy_allowed_source_type(source_type: str) -> None:
    assert source_type in ALLOWED_COLLECTION_SOURCE_TYPES
    creator = NormalizedCreator(
        provider="test",
        provider_creator_id="1",
        country="MX",
        username="u",
        profile_url="https://tiktok.com/@u",
        source_type=source_type,
        source_risk_level="low",
    )
    assert creator.source_type == source_type
