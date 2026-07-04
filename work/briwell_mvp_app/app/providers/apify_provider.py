"""Adapter that wraps the existing Apify/TikTok scrape provider.

This adapter does NOT modify ``app.providers.tiktok`` (its internals and its
existing tests stay untouched). It simply maps the new provider-agnostic
``ProviderRunRequest``/``ProviderRunResult`` contract onto the existing
``TikTokDiscoveryRunRequest``/``TikTokDiscoveryRunResult`` types.

``apify`` remains a ``provider_scrape`` source (default OFF for live calls),
per the policy allowlist in ``app.core.policy``.
"""

from __future__ import annotations

from typing import Any, cast

from app.core.config import settings
from app.providers import tiktok
from app.providers.base import (
    CreatorDataProvider,
    NormalizedCreator,
    NormalizedVideo,
    ProviderRunRequest,
    ProviderRunResult,
    ProviderStatus,
)
from app.providers.kbeauty_keywords import Country, ProductCategory


class ApifyProvider(CreatorDataProvider):
    """Wraps the existing Apify TikTok scrape discovery flow."""

    name = "apify"
    source_type = "provider_scrape"
    source_risk_level = "low_medium"

    def status(self) -> ProviderStatus:
        raw_status = tiktok.provider_status()
        apify_capability = next(
            (
                item
                for item in raw_status["capabilities"]
                if item["provider"] == "apify"
            ),
            None,
        )
        limits = list(apify_capability["limits"]) if apify_capability else []
        return ProviderStatus(
            name=self.name,
            source_type=self.source_type,
            source_risk_level=self.source_risk_level,
            configured=bool(settings.apify_api_token),
            live_supported=True,
            dry_run_default=bool(raw_status["dry_run_default"]),
            limits=limits,
        )

    def run(self, req: ProviderRunRequest) -> ProviderRunResult:
        tiktok_request = tiktok.TikTokDiscoveryRunRequest(
            provider="apify",
            countries=cast(list[Country], list(req.countries)),
            product_categories=cast(list[ProductCategory], list(req.product_categories)),
            max_results_per_query=req.max_results,
            recent_posts_per_creator=req.recent_posts_per_creator,
            dry_run=req.dry_run,
            allow_live_provider_calls=req.allow_live_provider_calls,
            persist_imports=bool(req.payload.get("persist_imports", False)),
        )
        result = tiktok.run_discovery(tiktok_request)
        return _to_provider_run_result(result)


def _to_provider_run_result(result: tiktok.TikTokDiscoveryRunResult) -> ProviderRunResult:
    status_map = {
        "dry_run_completed": "dry_run_completed",
        "live_completed": "live_completed",
        "blocked": "blocked",
        "provider_not_implemented": "not_implemented",
    }
    creators = [_to_normalized_creator(creator) for creator in result.creators]
    videos_by_creator = {
        creator_id: [_to_normalized_video(video) for video in videos]
        for creator_id, videos in result.videos_by_creator.items()
    }
    return ProviderRunResult(
        status=cast(Any, status_map[result.status]),
        provider="apify",
        mode=result.mode,
        source_type="provider_scrape",
        creator_count=result.creator_count,
        video_count=result.video_count,
        creators=creators,
        videos_by_creator=videos_by_creator,
        creator_import_payload=result.creator_import_payload,
        video_import_payloads=result.video_import_payloads,
        next_actions=result.next_actions,
        errors=result.errors,
    )


def _to_normalized_creator(creator: tiktok.NormalizedTikTokCreator) -> NormalizedCreator:
    return NormalizedCreator(
        provider="apify",
        provider_creator_id=creator.provider_creator_id,
        country=creator.country,
        username=creator.username,
        display_name=creator.display_name,
        profile_url=creator.profile_url,
        profile_image_url=creator.profile_image_url,
        bio=creator.bio,
        follower_count=creator.follower_count,
        avg_views=creator.avg_views,
        engagement_rate=creator.engagement_rate,
        source_type=creator.source_type,
        source_risk_level=creator.source_risk_level,
        product_category=creator.product_category,
        signals=list(creator.kbeauty_fit_signals),
        raw_metadata=dict(creator.raw_metadata),
    )


def _to_normalized_video(video: tiktok.NormalizedTikTokVideo) -> NormalizedVideo:
    return NormalizedVideo(
        provider="apify",
        provider_creator_id=video.provider_creator_id,
        creator_username=video.creator_username,
        url=video.url,
        platform_video_id=video.platform_video_id,
        caption=video.caption,
        hashtags=list(video.hashtags),
        posted_at=video.posted_at,
        view_count=video.view_count,
        like_count=video.like_count,
        comment_count=video.comment_count,
        share_count=video.share_count,
        save_count=video.save_count,
        duration_seconds=video.duration_seconds,
        thumbnail_url=video.thumbnail_url,
        transcript=video.transcript,
        source_type=video.source_type,
        source_risk_level=video.source_risk_level,
        raw_metadata=dict(video.raw_metadata),
    )
