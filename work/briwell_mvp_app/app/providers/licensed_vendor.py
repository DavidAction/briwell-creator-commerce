"""Licensed data vendor provider (Data365 / Bright Data licensed data APIs).

This models Briwell's intended integration with LICENSED third-party data
vendors that sell structured social-data APIs under a commercial data
license/contract -- e.g. Data365 or Bright Data's "Web/Datasets API"
products. This is NOT scraping performed by Briwell: it is a paid API
contract with a vendor who represents that their data collection is
lawful and covered by their own ToS/licensing with the source platforms.

Per policy (``app.core.policy.ALLOWED_COLLECTION_SOURCE_TYPES``):
- source_type = "approved_provider"
- source_risk_level = "low_medium"

Compliance notes:
- No scraping, anti-detection, IP rotation, or CAPTCHA bypass of any kind is
  implemented by Briwell in this module -- vendor API calls only.
- ``dry_run`` (default True via ``settings.licensed_vendor_dry_run``) returns
  deterministic vendor-shaped dummy normalized creators/videos, with NO
  network calls and NO credentials required, so tests and offline
  environments always work.
- Live calls are gated behind THREE independent controls, all of which must
  be satisfied simultaneously:
  1. An explicit live opt-in (``allow_live_provider_calls``).
  2. A configured vendor API key (``data365_api_key`` or
     ``brightdata_api_key``).
  3. A recorded contract/ToS sign-off gate
     (``settings.licensed_vendor_contract_confirmed``), representing that
     Briwell has an actual signed data-license/contract with the vendor on
     file -- NOT merely possession of an API key.
  If any control is missing, the provider returns ``status="blocked"`` with
  a clear ``next_actions`` entry (e.g. "record the contract") -- it never
  raises and never calls the network.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from app.core.config import settings
from app.providers.base import (
    CreatorDataProvider,
    NormalizedCreator,
    NormalizedVideo,
    ProviderRunRequest,
    ProviderRunResult,
    ProviderStatus,
)

SOURCE_TYPE = "approved_provider"
SOURCE_RISK_LEVEL = "low_medium"

VendorName = Literal["data365", "brightdata"]


class LicensedVendorProvider(CreatorDataProvider):
    """Adapter for licensed data-vendor APIs (Data365 / Bright Data)."""

    name = "licensed_vendor"
    source_type = SOURCE_TYPE
    source_risk_level = SOURCE_RISK_LEVEL

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            source_type=self.source_type,
            source_risk_level=self.source_risk_level,
            configured=_any_vendor_configured(),
            live_supported=True,
            dry_run_default=settings.licensed_vendor_dry_run,
            limits=[
                "Requires a licensed data-vendor contract (Data365 or Bright Data); not a scraping integration.",
                "Live calls require ALLOW_LIVE_PROVIDER_CALLS=true (or allow_live_provider_calls=true).",
                "Live calls require a configured vendor API key (DATA365_API_KEY or BRIGHTDATA_API_KEY).",
                "Live calls require LICENSED_VENDOR_CONTRACT_CONFIRMED=true, recording that a signed "
                "data-license/ToS contract with the vendor is on file.",
                "Data freshness, coverage, and rate limits are governed by the vendor's plan and ToS.",
            ],
        )

    def run(self, req: ProviderRunRequest) -> ProviderRunResult:
        vendor = _resolve_vendor(req.payload)
        dry_run = settings.licensed_vendor_dry_run if req.dry_run is None else req.dry_run
        allow_live = (
            settings.allow_live_provider_calls
            if req.allow_live_provider_calls is None
            else req.allow_live_provider_calls
        )

        if dry_run:
            return _dry_run_result(req, vendor)

        live_blockers = _live_blockers(vendor, allow_live)
        if live_blockers:
            return _blocked_result(vendor, live_blockers)

        # Even with the flag enabled, a configured key, and a confirmed
        # contract, Briwell has no live vendor API client wired up yet in
        # this codebase version, so the live path stays structured-only and
        # blocked rather than attempting a real call.
        return _blocked_result(
            vendor,
            [
                f"No live API client is wired up yet for vendor '{vendor}'; "
                "the request/response mapping has not been implemented.",
            ],
        )


def _resolve_vendor(payload: dict[str, Any]) -> VendorName:
    vendor = str(payload.get("vendor") or "data365").strip().lower()
    if vendor == "brightdata":
        return "brightdata"
    return "data365"


def _any_vendor_configured() -> bool:
    return bool(settings.data365_api_key or settings.brightdata_api_key)


def _vendor_configured(vendor: VendorName) -> bool:
    if vendor == "brightdata":
        return bool(settings.brightdata_api_key)
    return bool(settings.data365_api_key)


def _live_blockers(vendor: VendorName, allow_live: bool) -> list[str]:
    errors: list[str] = []
    if not allow_live:
        errors.append("ALLOW_LIVE_PROVIDER_CALLS=true is required for live licensed-vendor calls.")
    if not _vendor_configured(vendor):
        key_name = "BRIGHTDATA_API_KEY" if vendor == "brightdata" else "DATA365_API_KEY"
        errors.append(f"{key_name} is required for live calls to vendor '{vendor}'.")
    if not settings.licensed_vendor_contract_confirmed:
        errors.append(
            "LICENSED_VENDOR_CONTRACT_CONFIRMED=true is required: record the signed data-license/ToS "
            "contract with the vendor before enabling live calls."
        )
    return errors


def _dry_run_result(req: ProviderRunRequest, vendor: VendorName) -> ProviderRunResult:
    creators: list[NormalizedCreator] = []
    videos_by_creator: dict[str, list[NormalizedVideo]] = {}
    countries = req.countries or ["MX"]
    category = req.product_categories[0] if req.product_categories else None
    creator_count = min(req.max_results, 3)
    for index in range(1, creator_count + 1):
        country = countries[(index - 1) % len(countries)]
        creator = _fake_creator(index, country, category, vendor)
        creators.append(creator)
        videos_by_creator[creator.provider_creator_id] = _fake_videos(
            creator, req.recent_posts_per_creator, vendor
        )

    return ProviderRunResult(
        status="dry_run_completed",
        provider="licensed_vendor",
        mode="dry_run",
        source_type=SOURCE_TYPE,
        creator_count=len(creators),
        video_count=sum(len(items) for items in videos_by_creator.values()),
        creators=creators,
        videos_by_creator=videos_by_creator,
        creator_import_payload=_creator_import_payload(creators),
        video_import_payloads=_video_import_payloads(videos_by_creator),
        next_actions=[
            f"Confirm a signed data-license/ToS contract with '{vendor}' is on file.",
            "Set ALLOW_LIVE_PROVIDER_CALLS=true, configure the vendor API key, and set "
            "LICENSED_VENDOR_CONTRACT_CONFIRMED=true for a controlled live smoke test.",
            "Import normalized creators and their recent posts into the Briwell DB.",
        ],
        errors=[],
    )


def _blocked_result(vendor: VendorName, errors: list[str]) -> ProviderRunResult:
    next_actions = [
        "Keep dry_run=true until the vendor contract is confirmed and credentials are configured.",
    ]
    if not settings.licensed_vendor_contract_confirmed:
        next_actions.insert(
            0,
            f"Record the signed data-license/ToS contract with '{vendor}' and set "
            "LICENSED_VENDOR_CONTRACT_CONFIRMED=true.",
        )
    return ProviderRunResult(
        status="blocked",
        provider="licensed_vendor",
        mode="live",
        source_type=SOURCE_TYPE,
        creator_count=0,
        video_count=0,
        creators=[],
        videos_by_creator={},
        creator_import_payload=_creator_import_payload([]),
        video_import_payloads=[],
        next_actions=next_actions,
        errors=errors,
    )


def _fake_creator(
    index: int, country: str, category: str | None, vendor: VendorName
) -> NormalizedCreator:
    username = f"{vendor}.vendor.creator.{index}"
    followers = 26000 + index * 3100
    avg_views = 11000 + index * 1400
    engagement = round((avg_views * 0.075) / max(followers, 1) * 100, 2)
    return NormalizedCreator(
        provider="licensed_vendor",
        provider_creator_id=f"{vendor}-creator-id-{index}",
        country=country,  # type: ignore[arg-type]
        username=username,
        display_name=f"Licensed Vendor Creator {index}",
        profile_url=f"https://www.tiktok.com/@{username}",
        profile_image_url=f"https://cdn.briwell.local/licensed-vendor/{username}.jpg",
        bio="K-beauty skincare creator profile sourced via a licensed data-vendor API.",
        follower_count=followers,
        avg_views=avg_views,
        engagement_rate=engagement,
        source_type=SOURCE_TYPE,
        source_risk_level=SOURCE_RISK_LEVEL,
        product_category=category,
        signals=["licensed_vendor_sourced"],
        raw_metadata={"dry_run": True, "vendor": vendor},
    )


def _fake_videos(
    creator: NormalizedCreator, count: int, vendor: VendorName
) -> list[NormalizedVideo]:
    videos: list[NormalizedVideo] = []
    for index in range(1, count + 1):
        views = int((creator.avg_views or 9000) * (1 + (index % 5) * 0.05))
        likes = int(views * 0.065)
        comments = max(5, int(views * 0.0028))
        videos.append(
            NormalizedVideo(
                provider="licensed_vendor",
                provider_creator_id=creator.provider_creator_id,
                creator_username=creator.username,
                url=f"https://www.tiktok.com/@{creator.username}/video/{7800000000000000000 + index}",
                platform_video_id=str(7800000000000000000 + index),
                caption=f"Licensed vendor ({vendor}) dry-run sample post #{index} for {creator.username}.",
                hashtags=["kbeauty", "skincare"],
                posted_at=datetime(2026, 6, max(1, 18 - index), 12, 0, tzinfo=timezone.utc),
                view_count=views,
                like_count=likes,
                comment_count=comments,
                share_count=int(views * 0.0018),
                save_count=int(views * 0.0022),
                duration_seconds=22 + index % 15,
                thumbnail_url=f"https://cdn.briwell.local/licensed-vendor/{creator.username}-{index}.jpg",
                transcript=None,
                source_type=SOURCE_TYPE,
                source_risk_level=SOURCE_RISK_LEVEL,
                raw_metadata={"dry_run": True, "vendor": vendor},
            )
        )
    return videos


def _creator_import_payload(creators: list[NormalizedCreator]) -> dict[str, Any]:
    return {
        "source_type": SOURCE_TYPE,
        "source_risk_level": SOURCE_RISK_LEVEL,
        "items": [
            {
                "country": creator.country,
                "username": creator.username,
                "profile_url": creator.profile_url,
                "display_name": creator.display_name,
                "bio": creator.bio,
                "language": "es",
                "follower_count": creator.follower_count,
                "source_url": creator.profile_url,
            }
            for creator in creators
        ],
    }


def _video_import_payloads(
    videos_by_creator: dict[str, list[NormalizedVideo]],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for provider_creator_id, videos in videos_by_creator.items():
        payloads.append(
            {
                "provider_creator_id": provider_creator_id,
                "source_type": SOURCE_TYPE,
                "source_risk_level": SOURCE_RISK_LEVEL,
                "items": [_video_to_import_item(video) for video in videos],
            }
        )
    return payloads


def _video_to_import_item(video: NormalizedVideo) -> dict[str, Any]:
    return {
        "url": video.url,
        "platform_video_id": video.platform_video_id,
        "caption": video.caption,
        "hashtags": video.hashtags,
        "posted_at": video.posted_at,
        "view_count": video.view_count,
        "like_count": video.like_count,
        "comment_count": video.comment_count,
        "share_count": video.share_count,
        "save_count": video.save_count,
        "duration_seconds": video.duration_seconds,
        "thumbnail_url": video.thumbnail_url,
        "transcript": video.transcript,
        "raw_metadata": video.raw_metadata,
        "source_url": video.url,
    }
