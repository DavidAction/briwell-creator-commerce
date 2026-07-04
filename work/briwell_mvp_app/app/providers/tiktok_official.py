"""TikTok official API provider (dry-run skeleton).

This models Briwell's intended integration with TikTok's *official* APIs --
NOT scraping. Two official surfaces are modeled:

- OAuth2 client-credentials/authorization flow (``client_key``/``client_secret``
  producing a short-lived ``access_token``) used to authorize calls.
- Display API: a creator/business grants Briwell an OAuth token and Briwell
  reads that creator's own profile + their own videos + basic metrics. This
  is the primary path for creator-authorized data collection.
- Research API: TikTok's approved-researcher endpoint for querying public
  video/user data. It requires a *separate* TikTok Research API approval on
  top of the developer app; Briwell does not assume that approval exists, so
  the live path for this surface is always reported as unimplemented/blocked
  until an approved Research API credential is configured.

Per policy (``app.core.policy.ALLOWED_COLLECTION_SOURCE_TYPES``):
- source_type = "official_api"
- source_risk_level = "low"

Compliance notes:
- No scraping, anti-detection, IP rotation, or CAPTCHA bypass of any kind.
- ``dry_run`` (default True via ``settings.tiktok_official_dry_run``) returns
  deterministic dummy normalized creators/videos shaped like a real Display
  API response, with NO network calls and NO credentials required, so tests
  and offline environments always work.
- The live path is *structured only* here: it builds the OAuth2 token
  request and the Display API request payloads, but only actually executes
  them if ``allow_live_provider_calls`` is true AND TikTok credentials
  (``tiktok_client_key``/``tiktok_client_secret``/``tiktok_access_token``) are
  configured. Otherwise it returns ``status="blocked"`` with a clear
  next_action -- it never raises and never calls the network.
- The Research API surface is always reported as ``not_implemented`` for the
  live path (it needs a distinct TikTok approval Briwell does not assume is
  granted), even when Display API credentials are present.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import settings
from app.providers.base import (
    CreatorDataProvider,
    NormalizedCreator,
    NormalizedVideo,
    ProviderRunRequest,
    ProviderRunResult,
    ProviderStatus,
)

SOURCE_TYPE = "official_api"
SOURCE_RISK_LEVEL = "low"

ApiSurface = Literal["display_api", "research_api"]


class TikTokOAuthTokenRequest(BaseModel):
    """Models the TikTok OAuth2 client-credentials token request.

    See: POST https://open.tiktokapis.com/v2/oauth/token/
    """

    grant_type: Literal["client_credentials", "authorization_code"] = "client_credentials"
    client_key: str
    client_secret: str
    code: str | None = None
    redirect_uri: str | None = None


class TikTokDisplayApiRequest(BaseModel):
    """Models a TikTok Display API request for a creator's own data.

    Combines the "user info" and "video list" endpoints under the fields
    Briwell needs, scoped to the fields the creator has authorized via OAuth.
    """

    access_token_present: bool
    fields_user: list[str] = Field(
        default_factory=lambda: [
            "open_id",
            "union_id",
            "avatar_url",
            "display_name",
            "bio_description",
            "profile_deep_link",
            "follower_count",
            "following_count",
            "likes_count",
            "video_count",
        ]
    )
    fields_video: list[str] = Field(
        default_factory=lambda: [
            "id",
            "title",
            "video_description",
            "duration",
            "cover_image_url",
            "share_url",
            "create_time",
            "view_count",
            "like_count",
            "comment_count",
            "share_count",
        ]
    )
    max_videos_per_creator: int = 20


class ProviderRequestPreview(BaseModel):
    """Structured (never executed unless live+configured) request preview."""

    surface: ApiSurface
    oauth_token_request: dict[str, Any]
    display_api_request: dict[str, Any] | None = None
    research_api_note: str | None = None


class TikTokOfficialProvider(CreatorDataProvider):
    """Adapter for TikTok's official Display API / Research API surfaces."""

    name = "tiktok_official"
    source_type = SOURCE_TYPE
    source_risk_level = SOURCE_RISK_LEVEL

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            source_type=self.source_type,
            source_risk_level=self.source_risk_level,
            configured=_display_api_configured(),
            live_supported=True,
            dry_run_default=settings.tiktok_official_dry_run,
            limits=[
                "Display API only returns data for creators who have granted OAuth consent to Briwell's app.",
                "Research API requires a separate TikTok Research API approval; live calls for it are not implemented.",
                "Live calls require ALLOW_LIVE_PROVIDER_CALLS=true (or allow_live_provider_calls=true) and configured TikTok credentials.",
                "Rate limits and field availability are governed by TikTok's Developer Terms and the app's approved scopes.",
            ],
        )

    def run(self, req: ProviderRunRequest) -> ProviderRunResult:
        surface = _resolve_surface(req.payload)
        dry_run = settings.tiktok_official_dry_run if req.dry_run is None else req.dry_run
        allow_live = (
            settings.allow_live_provider_calls
            if req.allow_live_provider_calls is None
            else req.allow_live_provider_calls
        )

        if dry_run:
            return _dry_run_result(req, surface)

        if surface == "research_api":
            return _not_implemented_result(req, surface)

        live_blockers = _live_blockers(allow_live)
        if live_blockers:
            return _blocked_result(req, surface, live_blockers)

        # Live path is intentionally structured-only: Briwell has no
        # creator-consented OAuth token exchange wired up yet, so even with
        # keys configured and the flag enabled we do not have a safe,
        # already-authorized call to execute on a real creator's behalf.
        return _blocked_result(
            req,
            surface,
            [
                "Live Display API calls require a creator-authorized OAuth access token for that "
                "specific creator; no automated token exchange is wired up yet.",
            ],
        )


def _resolve_surface(payload: dict[str, Any]) -> ApiSurface:
    surface = str(payload.get("surface") or "display_api").strip().lower()
    if surface == "research_api":
        return "research_api"
    return "display_api"


def _display_api_configured() -> bool:
    return bool(settings.tiktok_client_key and settings.tiktok_client_secret)


def _live_blockers(allow_live: bool) -> list[str]:
    errors: list[str] = []
    if not allow_live:
        errors.append("ALLOW_LIVE_PROVIDER_CALLS=true is required for live TikTok official API calls.")
    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        errors.append("TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET are required for live TikTok official API calls.")
    if not settings.tiktok_access_token:
        errors.append("TIKTOK_ACCESS_TOKEN (a creator-authorized OAuth token) is required for live Display API calls.")
    return errors


def _oauth_token_request_preview() -> dict[str, Any]:
    request = TikTokOAuthTokenRequest(
        client_key=settings.tiktok_client_key or "<TIKTOK_CLIENT_KEY not configured>",
        client_secret="<redacted>",
    )
    return request.model_dump()


def _display_api_request_preview(req: ProviderRunRequest) -> dict[str, Any]:
    request = TikTokDisplayApiRequest(
        access_token_present=bool(settings.tiktok_access_token),
        max_videos_per_creator=req.recent_posts_per_creator,
    )
    return request.model_dump()


def _provider_request_preview(req: ProviderRunRequest, surface: ApiSurface) -> ProviderRequestPreview:
    if surface == "research_api":
        return ProviderRequestPreview(
            surface=surface,
            oauth_token_request=_oauth_token_request_preview(),
            display_api_request=None,
            research_api_note=(
                "TikTok Research API requires a separate approval beyond the standard developer "
                "app; Briwell has not implemented or validated a live integration for this surface."
            ),
        )
    return ProviderRequestPreview(
        surface=surface,
        oauth_token_request=_oauth_token_request_preview(),
        display_api_request=_display_api_request_preview(req),
        research_api_note=None,
    )


def _dry_run_result(req: ProviderRunRequest, surface: ApiSurface) -> ProviderRunResult:
    creators: list[NormalizedCreator] = []
    videos_by_creator: dict[str, list[NormalizedVideo]] = {}
    countries = req.countries or ["MX"]
    category = req.product_categories[0] if req.product_categories else None
    creator_count = min(req.max_results, 3)
    for index in range(1, creator_count + 1):
        country = countries[(index - 1) % len(countries)]
        creator = _fake_creator(index, country, category)
        creators.append(creator)
        videos_by_creator[creator.provider_creator_id] = _fake_videos(
            creator, req.recent_posts_per_creator
        )

    return ProviderRunResult(
        status="dry_run_completed",
        provider="tiktok_official",
        mode="dry_run",
        source_type=SOURCE_TYPE,
        creator_count=len(creators),
        video_count=sum(len(items) for items in videos_by_creator.values()),
        creators=creators,
        videos_by_creator=videos_by_creator,
        creator_import_payload=_creator_import_payload(creators),
        video_import_payloads=_video_import_payloads(videos_by_creator),
        next_actions=[
            "Onboard creators via TikTok Login Kit / Display API OAuth consent flow.",
            "Set ALLOW_LIVE_PROVIDER_CALLS=true and configure TikTok credentials for a controlled live smoke test.",
            "Import normalized creators and their own recent posts into the Briwell DB.",
        ],
        errors=[],
    )


def build_provider_request_preview(req: ProviderRunRequest) -> dict[str, Any]:
    """Expose the structured (never auto-executed) request preview.

    Useful for admin/debug tooling that wants to see exactly what a live call
    *would* send, without the shared ``ProviderRunResult`` contract needing a
    provider-specific field.
    """

    surface = _resolve_surface(req.payload)
    return _provider_request_preview(req, surface).model_dump()


def _not_implemented_result(req: ProviderRunRequest, surface: ApiSurface) -> ProviderRunResult:
    return ProviderRunResult(
        status="not_implemented",
        provider="tiktok_official",
        mode="live",
        source_type=SOURCE_TYPE,
        creator_count=0,
        video_count=0,
        creators=[],
        videos_by_creator={},
        creator_import_payload=_creator_import_payload([]),
        video_import_payloads=[],
        next_actions=[
            "TikTok Research API requires a separate approved-researcher credential.",
            "Use dry_run=true to exercise the pipeline, or use the Display API surface with creator OAuth consent.",
        ],
        errors=[f"{surface} live adapter is not implemented; TikTok Research API approval is required."],
    )


def _blocked_result(
    req: ProviderRunRequest,
    surface: ApiSurface,
    errors: list[str],
) -> ProviderRunResult:
    return ProviderRunResult(
        status="blocked",
        provider="tiktok_official",
        mode="live",
        source_type=SOURCE_TYPE,
        creator_count=0,
        video_count=0,
        creators=[],
        videos_by_creator={},
        creator_import_payload=_creator_import_payload([]),
        video_import_payloads=[],
        next_actions=[
            "Keep dry_run=true until TikTok credentials and a creator OAuth token are configured.",
            "Complete TikTok Login Kit consent for each creator before requesting their Display API data.",
        ],
        errors=errors,
    )


def _fake_creator(index: int, country: str, category: str | None) -> NormalizedCreator:
    username = f"official.creator.{index}"
    followers = 18000 + index * 2100
    avg_views = 7200 + index * 950
    engagement = round((avg_views * 0.08) / max(followers, 1) * 100, 2)
    return NormalizedCreator(
        provider="tiktok_official",
        provider_creator_id=f"official-open-id-{index}",
        country=country,  # type: ignore[arg-type]
        username=username,
        display_name=f"Official Creator {index}",
        profile_url=f"https://www.tiktok.com/@{username}",
        profile_image_url=f"https://cdn.briwell.local/tiktok-official/{username}.jpg",
        bio="K-beauty skincare creator authorized via TikTok Display API OAuth consent.",
        follower_count=followers,
        avg_views=avg_views,
        engagement_rate=engagement,
        source_type=SOURCE_TYPE,
        source_risk_level=SOURCE_RISK_LEVEL,
        product_category=category,
        signals=["official_api_authorized"],
        raw_metadata={"dry_run": True, "surface": "display_api"},
    )


def _fake_videos(creator: NormalizedCreator, count: int) -> list[NormalizedVideo]:
    videos: list[NormalizedVideo] = []
    for index in range(1, count + 1):
        views = int((creator.avg_views or 6000) * (1 + (index % 5) * 0.06))
        likes = int(views * 0.07)
        comments = max(6, int(views * 0.003))
        videos.append(
            NormalizedVideo(
                provider="tiktok_official",
                provider_creator_id=creator.provider_creator_id,
                creator_username=creator.username,
                url=f"https://www.tiktok.com/@{creator.username}/video/{7700000000000000000 + index}",
                platform_video_id=str(7700000000000000000 + index),
                caption=f"Official API dry-run sample post #{index} for {creator.username}.",
                hashtags=["kbeauty", "skincare"],
                posted_at=datetime(2026, 6, max(1, 17 - index), 12, 0, tzinfo=timezone.utc),
                view_count=views,
                like_count=likes,
                comment_count=comments,
                share_count=int(views * 0.002),
                save_count=int(views * 0.0025),
                duration_seconds=25 + index % 15,
                thumbnail_url=f"https://cdn.briwell.local/tiktok-official/{creator.username}-{index}.jpg",
                transcript=None,
                source_type=SOURCE_TYPE,
                source_risk_level=SOURCE_RISK_LEVEL,
                raw_metadata={"dry_run": True, "surface": "display_api"},
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
