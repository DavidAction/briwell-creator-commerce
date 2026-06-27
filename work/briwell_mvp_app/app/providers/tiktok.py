from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.db import database_enabled
from app.providers.kbeauty_keywords import Country
from app.providers.kbeauty_keywords import ProductCategory
from app.providers.kbeauty_keywords import build_kbeauty_keyword_playbook
from app.repositories import creators as creator_repository
from app.repositories import videos as video_repository


ProviderName = Literal["apify", "data365", "bright_data", "tikapi"]


class TikTokProviderCapability(BaseModel):
    provider: ProviderName
    configured: bool
    live_supported: bool
    recommended_role: str
    strengths: list[str]
    limits: list[str]


class TikTokDiscoveryRunRequest(BaseModel):
    provider: ProviderName = "apify"
    countries: list[Country] = Field(default_factory=lambda: ["MX", "PE", "EC"])
    product_categories: list[ProductCategory] = Field(default_factory=lambda: ["sunscreen"])
    max_keywords_per_country_category: int = Field(default=8, ge=1, le=20)
    max_results_per_query: int = Field(default=3, ge=1, le=50)
    include_recent_posts: bool = True
    recent_posts_per_creator: int = Field(default=20, ge=1, le=20)
    dry_run: bool | None = None
    allow_live_provider_calls: bool | None = None
    persist_imports: bool = False


class NormalizedTikTokCreator(BaseModel):
    provider: ProviderName
    provider_creator_id: str
    country: Country
    username: str
    display_name: str | None = None
    profile_url: str
    profile_image_url: str | None = None
    bio: str | None = None
    follower_count: int | None = Field(default=None, ge=0)
    avg_views: int | None = Field(default=None, ge=0)
    engagement_rate: float | None = Field(default=None, ge=0)
    source_type: Literal["provider_scrape"] = "provider_scrape"
    source_risk_level: Literal["low_medium"] = "low_medium"
    matched_query: str
    matched_intent: str
    product_category: ProductCategory
    audience_age_fit: Literal["gen_z", "young_millennial", "both"]
    kbeauty_fit_signals: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedTikTokVideo(BaseModel):
    provider: ProviderName
    provider_creator_id: str
    creator_username: str
    url: str
    platform_video_id: str | None = None
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    save_count: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    thumbnail_url: str | None = None
    transcript: str | None = None
    source_type: Literal["provider_scrape"] = "provider_scrape"
    source_risk_level: Literal["low_medium"] = "low_medium"
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class TikTokDiscoveryRunResult(BaseModel):
    status: Literal[
        "dry_run_completed",
        "live_completed",
        "blocked",
        "provider_not_implemented",
    ]
    provider: ProviderName
    mode: Literal["dry_run", "live"]
    keyword_count: int
    provider_request_count: int
    creator_count: int
    video_count: int
    creators: list[NormalizedTikTokCreator]
    videos_by_creator: dict[str, list[NormalizedTikTokVideo]]
    creator_import_payload: dict[str, Any]
    video_import_payloads: list[dict[str, Any]]
    persisted: dict[str, Any] | None = None
    provider_request_preview: dict[str, Any] | None = None
    quality_gates: dict[str, Any]
    next_actions: list[str]
    errors: list[str] = Field(default_factory=list)


def provider_status() -> dict[str, Any]:
    capabilities = [
        TikTokProviderCapability(
            provider="apify",
            configured=bool(settings.apify_api_token),
            live_supported=True,
            recommended_role="MVP live connector",
            strengths=[
                "Fastest to integrate",
                "Search, hashtag, profile, URL inputs",
                "JSON/CSV/API/webhook friendly",
            ],
            limits=[
                "Actor input and output can evolve",
                "Quality must be benchmarked by country and keyword",
            ],
        ),
        TikTokProviderCapability(
            provider="data365",
            configured=bool(settings.data365_api_key),
            live_supported=False,
            recommended_role="Production benchmark candidate",
            strengths=[
                "Profile search, profiles, videos, comments, hashtags",
                "Async collection flow fits worker architecture",
            ],
            limits=["Adapter skeleton only until account API contract is confirmed"],
        ),
        TikTokProviderCapability(
            provider="bright_data",
            configured=bool(settings.brightdata_api_key),
            live_supported=False,
            recommended_role="Scale fallback",
            strengths=[
                "Profiles, posts, keyword or hashtag search, comments, TikTok Shop",
                "Enterprise-scale delivery options",
            ],
            limits=["Higher cost and onboarding complexity"],
        ),
        TikTokProviderCapability(
            provider="tikapi",
            configured=bool(settings.tikapi_api_key),
            live_supported=False,
            recommended_role="Experimental fallback",
            strengths=["Broad unofficial public-data endpoint coverage"],
            limits=["Higher operational and continuity risk"],
        ),
    ]
    return {
        "status": "ready" if any(item.configured for item in capabilities) else "not_configured",
        "default_provider": "apify",
        "dry_run_default": settings.tiktok_provider_dry_run,
        "live_provider_calls_allowed": settings.allow_live_tiktok_provider_calls,
        "daily_result_limit": settings.tiktok_provider_daily_result_limit,
        "capabilities": [item.model_dump() for item in capabilities],
    }


def run_discovery(request: TikTokDiscoveryRunRequest) -> TikTokDiscoveryRunResult:
    dry_run = settings.tiktok_provider_dry_run if request.dry_run is None else request.dry_run
    allow_live = (
        settings.allow_live_tiktok_provider_calls
        if request.allow_live_provider_calls is None
        else request.allow_live_provider_calls
    )
    keyword_items = build_kbeauty_keyword_playbook(
        countries=request.countries,
        product_categories=request.product_categories,
        max_keywords_per_country_category=request.max_keywords_per_country_category,
    )
    provider_preview = _provider_request_preview(request, keyword_items)

    if dry_run:
        return _dry_run_result(request, keyword_items, provider_preview)

    live_blockers = _live_blockers(request.provider, allow_live)
    if live_blockers:
        return _blocked_result(request, keyword_items, provider_preview, live_blockers)

    if request.provider != "apify":
        return TikTokDiscoveryRunResult(
            status="provider_not_implemented",
            provider=request.provider,
            mode="live",
            keyword_count=len(keyword_items),
            provider_request_count=len(keyword_items),
            creator_count=0,
            video_count=0,
            creators=[],
            videos_by_creator={},
            creator_import_payload=_creator_import_payload([]),
            video_import_payloads=[],
            provider_request_preview=provider_preview,
            quality_gates=_quality_gates([], {}),
            next_actions=[
                "Run Apify first for MVP live validation.",
                "Enable this provider after a documented sample response is mapped.",
            ],
            errors=[f"{request.provider} live adapter is not implemented yet."],
        )

    raw_items = _run_apify_live(request, keyword_items)
    creators, videos_by_creator = _normalize_apify_items(request, raw_items, keyword_items)
    persisted = _persist_if_requested(request, creators, videos_by_creator)
    return _result_from_normalized(
        request=request,
        keyword_count=len(keyword_items),
        provider_request_count=len(keyword_items),
        creators=creators,
        videos_by_creator=videos_by_creator,
        provider_preview=provider_preview,
        status="live_completed",
        mode="live",
        persisted=persisted,
    )


def _live_blockers(provider: ProviderName, allow_live: bool) -> list[str]:
    errors: list[str] = []
    if not allow_live:
        errors.append("ALLOW_LIVE_TIKTOK_PROVIDER_CALLS=true is required for live provider calls.")
    if provider == "apify" and not settings.apify_api_token:
        errors.append("APIFY_API_TOKEN is required for live Apify calls.")
    if provider == "data365" and not settings.data365_api_key:
        errors.append("DATA365_API_KEY is required for live Data365 calls.")
    if provider == "bright_data" and not settings.brightdata_api_key:
        errors.append("BRIGHTDATA_API_KEY is required for live Bright Data calls.")
    if provider == "tikapi" and not settings.tikapi_api_key:
        errors.append("TIKAPI_API_KEY is required for live TikAPI calls.")
    return errors


def _provider_request_preview(
    request: TikTokDiscoveryRunRequest,
    keyword_items: list[Any],
) -> dict[str, Any]:
    searches = [item.query for item in keyword_items if item.query_type == "keyword"]
    hashtags = [item.query.lstrip("#") for item in keyword_items if item.query_type == "hashtag"]
    if request.provider == "apify":
        return {
            "actor_id": settings.apify_tiktok_actor_id,
            "input": _apify_input(
                searches=searches,
                hashtags=hashtags,
                results_per_page=request.max_results_per_query,
                max_profiles_per_query=request.max_results_per_query,
                include_recent_posts=request.include_recent_posts,
            ),
        }
    return {
        "provider": request.provider,
        "search_queries": searches,
        "hashtags": hashtags,
        "max_results_per_query": request.max_results_per_query,
    }


def _apify_input(
    searches: list[str],
    hashtags: list[str],
    results_per_page: int,
    max_profiles_per_query: int,
    include_recent_posts: bool,
) -> dict[str, Any]:
    return {
        "excludePinnedPosts": False,
        "hashtags": hashtags,
        "proxyCountryCode": "None",
        "resultsPerPage": results_per_page,
        "scrapeRelatedVideos": False,
        "searchQueries": searches,
        "shouldDownloadAvatars": False,
        "shouldDownloadCovers": False,
        "shouldDownloadMusicCovers": False,
        "shouldDownloadSlideshowImages": False,
        "downloadSubtitlesOptions": "DOWNLOAD_SUBTITLES",
        "shouldDownloadVideos": False,
        "profileScrapeSections": ["videos"] if include_recent_posts else [],
        "profileSorting": "latest",
        "searchSection": "/video",
        "maxProfilesPerQuery": max_profiles_per_query,
        "videoSearchSorting": "MOST_RELEVANT",
        "videoSearchDateFilter": "LAST_6_MONTHS",
    }


def _run_apify_live(
    request: TikTokDiscoveryRunRequest,
    keyword_items: list[Any],
) -> list[dict[str, Any]]:
    preview = _provider_request_preview(request, keyword_items)
    actor_id = settings.apify_tiktok_actor_id.replace("/", "~")
    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    params = {
        "token": settings.apify_api_token,
        "format": "json",
        "clean": "true",
    }
    with httpx.Client(timeout=180) as client:
        response = client.post(url, params=params, json=preview["input"])
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Apify response must be a JSON list of dataset items.")
    return payload[: settings.tiktok_provider_daily_result_limit]


def _dry_run_result(
    request: TikTokDiscoveryRunRequest,
    keyword_items: list[Any],
    provider_preview: dict[str, Any],
) -> TikTokDiscoveryRunResult:
    creators: list[NormalizedTikTokCreator] = []
    videos_by_creator: dict[str, list[NormalizedTikTokVideo]] = {}
    max_creators_per_query = min(request.max_results_per_query, 2)
    for query_index, item in enumerate(keyword_items, start=1):
        for creator_index in range(1, max_creators_per_query + 1):
            creator = _fake_creator(request.provider, item, query_index, creator_index)
            creators.append(creator)
            if request.include_recent_posts:
                videos_by_creator[creator.provider_creator_id] = _fake_videos(
                    request.provider,
                    creator,
                    request.recent_posts_per_creator,
                )
    return _result_from_normalized(
        request=request,
        keyword_count=len(keyword_items),
        provider_request_count=len(keyword_items),
        creators=creators,
        videos_by_creator=videos_by_creator,
        provider_preview=provider_preview,
        status="dry_run_completed",
        mode="dry_run",
        persisted=None,
    )


def _blocked_result(
    request: TikTokDiscoveryRunRequest,
    keyword_items: list[Any],
    provider_preview: dict[str, Any],
    errors: list[str],
) -> TikTokDiscoveryRunResult:
    return TikTokDiscoveryRunResult(
        status="blocked",
        provider=request.provider,
        mode="live",
        keyword_count=len(keyword_items),
        provider_request_count=len(keyword_items),
        creator_count=0,
        video_count=0,
        creators=[],
        videos_by_creator={},
        creator_import_payload=_creator_import_payload([]),
        video_import_payloads=[],
        provider_request_preview=provider_preview,
        quality_gates=_quality_gates([], {}),
        next_actions=[
            "Keep dry_run=true until provider keys and spend limits are configured.",
            "Set ALLOW_LIVE_TIKTOK_PROVIDER_CALLS=true only for a controlled smoke run.",
        ],
        errors=errors,
    )


def _result_from_normalized(
    request: TikTokDiscoveryRunRequest,
    keyword_count: int,
    provider_request_count: int,
    creators: list[NormalizedTikTokCreator],
    videos_by_creator: dict[str, list[NormalizedTikTokVideo]],
    provider_preview: dict[str, Any],
    status: Literal["dry_run_completed", "live_completed"],
    mode: Literal["dry_run", "live"],
    persisted: dict[str, Any] | None,
) -> TikTokDiscoveryRunResult:
    video_payloads = _video_import_payloads(videos_by_creator)
    return TikTokDiscoveryRunResult(
        status=status,
        provider=request.provider,
        mode=mode,
        keyword_count=keyword_count,
        provider_request_count=provider_request_count,
        creator_count=len(creators),
        video_count=sum(len(items) for items in videos_by_creator.values()),
        creators=creators,
        videos_by_creator=videos_by_creator,
        creator_import_payload=_creator_import_payload(creators),
        video_import_payloads=video_payloads,
        persisted=persisted,
        provider_request_preview=provider_preview,
        quality_gates=_quality_gates(creators, videos_by_creator),
        next_actions=_next_actions(creators, videos_by_creator, request.persist_imports),
    )


def _normalize_apify_items(
    request: TikTokDiscoveryRunRequest,
    raw_items: list[dict[str, Any]],
    keyword_items: list[Any],
) -> tuple[list[NormalizedTikTokCreator], dict[str, list[NormalizedTikTokVideo]]]:
    keyword_lookup = {item.query.lower(): item for item in keyword_items}
    creator_map: dict[str, NormalizedTikTokCreator] = {}
    videos_by_creator: dict[str, list[NormalizedTikTokVideo]] = {}
    fallback_item = keyword_items[0] if keyword_items else None
    for raw in raw_items:
        author = _nested(raw, "authorMeta") or {}
        username = _clean_username(author.get("name") or raw.get("authorMeta.name") or raw.get("author"))
        if not username:
            continue
        search_query = str(raw.get("searchQuery") or "").lower()
        keyword_item = keyword_lookup.get(search_query) or fallback_item
        country = keyword_item.country if keyword_item else request.countries[0]
        category = keyword_item.product_category if keyword_item else request.product_categories[0]
        intent = keyword_item.intent_type if keyword_item else "discovery"
        audience = keyword_item.audience if keyword_item else "both"
        creator_id = str(author.get("id") or raw.get("authorMeta.id") or username)
        creator = creator_map.get(creator_id)
        if creator is None:
            creator = NormalizedTikTokCreator(
                provider=request.provider,
                provider_creator_id=creator_id,
                country=country,
                username=username,
                display_name=author.get("nickName") or raw.get("authorMeta.nickName") or username,
                profile_url=author.get("profileUrl") or f"https://www.tiktok.com/@{username}",
                profile_image_url=author.get("avatar") or author.get("originalAvatarUrl"),
                bio=author.get("signature") or raw.get("authorMeta.signature"),
                follower_count=_to_int(author.get("fans") or raw.get("authorMeta.fans")),
                avg_views=_to_int(raw.get("playCount")),
                engagement_rate=_engagement_rate(raw),
                matched_query=search_query or (keyword_item.query if keyword_item else ""),
                matched_intent=str(intent),
                product_category=category,
                audience_age_fit=audience,
                kbeauty_fit_signals=_signals_from_text(str(raw.get("text") or ""), category),
                raw_metadata={"provider_sample": _safe_raw_subset(raw)},
            )
            creator_map[creator_id] = creator
        video = _apify_video_from_raw(request.provider, creator, raw)
        if video:
            videos_by_creator.setdefault(creator.provider_creator_id, []).append(video)
    for creator_id, videos in list(videos_by_creator.items()):
        videos_by_creator[creator_id] = videos[: request.recent_posts_per_creator]
    return list(creator_map.values()), videos_by_creator


def _apify_video_from_raw(
    provider: ProviderName,
    creator: NormalizedTikTokCreator,
    raw: dict[str, Any],
) -> NormalizedTikTokVideo | None:
    url = raw.get("webVideoUrl") or raw.get("url")
    if not url:
        return None
    video_meta = _nested(raw, "videoMeta") or {}
    return NormalizedTikTokVideo(
        provider=provider,
        provider_creator_id=creator.provider_creator_id,
        creator_username=creator.username,
        url=str(url),
        platform_video_id=str(raw.get("id")) if raw.get("id") else None,
        caption=raw.get("text"),
        hashtags=_hashtags_from_raw(raw.get("hashtags")),
        posted_at=_parse_datetime(raw.get("createTimeISO")),
        view_count=_to_int(raw.get("playCount")),
        like_count=_to_int(raw.get("diggCount")),
        comment_count=_to_int(raw.get("commentCount")),
        share_count=_to_int(raw.get("shareCount")),
        save_count=_to_int(raw.get("collectCount")),
        duration_seconds=_to_int(video_meta.get("duration") or raw.get("videoMeta.duration")),
        thumbnail_url=video_meta.get("coverUrl") or raw.get("videoMeta.coverUrl"),
        transcript=_subtitle_hint(raw),
        raw_metadata={"provider_sample": _safe_raw_subset(raw)},
    )


def _persist_if_requested(
    request: TikTokDiscoveryRunRequest,
    creators: list[NormalizedTikTokCreator],
    videos_by_creator: dict[str, list[NormalizedTikTokVideo]],
) -> dict[str, Any] | None:
    if not request.persist_imports:
        return None
    if not database_enabled():
        return {
            "status": "not_persisted",
            "reason": "USE_DATABASE=true is required.",
        }
    imported_creators = creator_repository.import_creators(
        source_type="provider_scrape",
        source_risk_level="low_medium",
        items=[
            {
                "country": creator.country,
                "username": creator.username,
                "display_name": creator.display_name,
                "profile_url": creator.profile_url,
                "bio": creator.bio,
                "language": "es",
                "follower_count": creator.follower_count,
                "source_url": creator.profile_url,
            }
            for creator in creators
        ],
    )
    db_id_by_username = {row["username"]: str(row["id"]) for row in imported_creators}
    imported_video_count = 0
    for creator in creators:
        db_creator_id = db_id_by_username.get(creator.username)
        if not db_creator_id:
            continue
        videos = videos_by_creator.get(creator.provider_creator_id, [])
        if not videos:
            continue
        imported = video_repository.import_videos(
            creator_id=db_creator_id,
            source_type="provider_scrape",
            source_risk_level="low_medium",
            items=[_video_to_import_item(video) for video in videos],
        )
        imported_video_count += len(imported)
    return {
        "status": "persisted",
        "creator_count": len(imported_creators),
        "video_count": imported_video_count,
    }


def _creator_import_payload(creators: list[NormalizedTikTokCreator]) -> dict[str, Any]:
    return {
        "source_type": "provider_scrape",
        "source_risk_level": "low_medium",
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
    videos_by_creator: dict[str, list[NormalizedTikTokVideo]],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for provider_creator_id, videos in videos_by_creator.items():
        payloads.append(
            {
                "provider_creator_id": provider_creator_id,
                "source_type": "provider_scrape",
                "source_risk_level": "low_medium",
                "items": [_video_to_import_item(video) for video in videos],
            }
        )
    return payloads


def _video_to_import_item(video: NormalizedTikTokVideo) -> dict[str, Any]:
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


def _fake_creator(
    provider: ProviderName,
    keyword_item: Any,
    query_index: int,
    creator_index: int,
) -> NormalizedTikTokCreator:
    username = _slug_username(
        f"{keyword_item.country}-{keyword_item.product_category}-{keyword_item.intent_type}-{query_index}-{creator_index}"
    )
    followers = 12000 + query_index * 1700 + creator_index * 850
    avg_views = 6400 + query_index * 1200 + creator_index * 900
    engagement = round((avg_views * 0.07) / max(followers, 1) * 100, 2)
    signals = _signals_from_text(keyword_item.query, keyword_item.product_category)
    return NormalizedTikTokCreator(
        provider=provider,
        provider_creator_id=f"dry-{username}",
        country=keyword_item.country,
        username=username,
        display_name=_display_name(username),
        profile_url=f"https://www.tiktok.com/@{username}",
        profile_image_url=f"https://cdn.briwell.local/provider/{username}.jpg",
        bio=f"K-beauty, skincare routines, honest reviews. Query: {keyword_item.query}",
        follower_count=followers,
        avg_views=avg_views,
        engagement_rate=engagement,
        matched_query=keyword_item.query,
        matched_intent=keyword_item.intent_type,
        product_category=keyword_item.product_category,
        audience_age_fit=keyword_item.audience,
        kbeauty_fit_signals=signals,
        raw_metadata={"dry_run": True, "keyword_reason": keyword_item.reason},
    )


def _fake_videos(
    provider: ProviderName,
    creator: NormalizedTikTokCreator,
    count: int,
) -> list[NormalizedTikTokVideo]:
    videos: list[NormalizedTikTokVideo] = []
    tags = _tags_for_category(creator.product_category)
    for index in range(1, count + 1):
        views = int((creator.avg_views or 6000) * (1 + (index % 5) * 0.08))
        likes = int(views * 0.065)
        comments = max(8, int(views * 0.004))
        videos.append(
            NormalizedTikTokVideo(
                provider=provider,
                provider_creator_id=creator.provider_creator_id,
                creator_username=creator.username,
                url=f"https://www.tiktok.com/@{creator.username}/video/{7600000000000000000 + index}",
                platform_video_id=str(7600000000000000000 + index),
                caption=_caption_for_creator(creator, index),
                hashtags=tags,
                posted_at=datetime(2026, 6, max(1, 17 - index), 12, 0, tzinfo=timezone.utc),
                view_count=views,
                like_count=likes,
                comment_count=comments,
                share_count=int(views * 0.002),
                save_count=int(views * 0.003),
                duration_seconds=28 + index % 20,
                thumbnail_url=f"https://cdn.briwell.local/provider/{creator.username}-{index}.jpg",
                transcript=_caption_for_creator(creator, index),
                raw_metadata={"dry_run": True},
            )
        )
    return videos


def _quality_gates(
    creators: list[NormalizedTikTokCreator],
    videos_by_creator: dict[str, list[NormalizedTikTokVideo]],
) -> dict[str, Any]:
    creator_with_20 = sum(1 for creator in creators if len(videos_by_creator.get(creator.provider_creator_id, [])) >= 20)
    missing_recent_20 = [
        creator.username
        for creator in creators
        if len(videos_by_creator.get(creator.provider_creator_id, [])) < 20
    ][:20]
    country_counts: dict[str, int] = {}
    intent_counts: dict[str, int] = {}
    for creator in creators:
        country_counts[creator.country] = country_counts.get(creator.country, 0) + 1
        intent_counts[creator.matched_intent] = intent_counts.get(creator.matched_intent, 0) + 1
    return {
        "recent_20_coverage": {
            "ready_creators": creator_with_20,
            "total_creators": len(creators),
            "missing_recent_20_sample": missing_recent_20,
        },
        "country_counts": country_counts,
        "intent_counts": intent_counts,
        "minimum_viable_for_screening": creator_with_20 > 0,
        "recommended_minimum": "Run at least 30 queries and keep 100-300 first-pass creators for MX/PE/EC benchmark.",
    }


def _next_actions(
    creators: list[NormalizedTikTokCreator],
    videos_by_creator: dict[str, list[NormalizedTikTokVideo]],
    persist_requested: bool,
) -> list[str]:
    actions = [
        "Review provider sample quality by country, query, and product category.",
        "Import normalized creators and recent 20 posts into the Briwell DB.",
        "Run Recent 20 Posts Screen for creators with 20 post snapshots.",
        "Compare pass rate, duplicate rate, and cost per qualified creator before choosing the main provider.",
    ]
    if not persist_requested:
        actions.insert(1, "Set persist_imports=true after a small provider smoke test passes.")
    if any(len(videos_by_creator.get(creator.provider_creator_id, [])) < 20 for creator in creators):
        actions.append("Backfill creators with fewer than 20 posts before final exclusion.")
    return actions


def _safe_raw_subset(raw: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "id",
        "text",
        "textLanguage",
        "createTimeISO",
        "isAd",
        "webVideoUrl",
        "diggCount",
        "shareCount",
        "playCount",
        "collectCount",
        "commentCount",
        "searchQuery",
    ]
    return {key: raw.get(key) for key in keys if key in raw}


def _signals_from_text(text: str, category: ProductCategory) -> list[str]:
    lowered = text.lower()
    signals = ["kbeauty_query_match"]
    if any(term in lowered for term in ("viral", "tiktok", "grwm")):
        signals.append("young_audience_format")
    if any(term in lowered for term in ("resena", "honesta", "review", "probando")):
        signals.append("review_format")
    if any(term in lowered for term in ("comprar", "recomendado", "dupe", "barato")):
        signals.append("commerce_intent")
    if category in {"sunscreen", "calming_serum", "cleanser"}:
        signals.append("skincare_fit")
    else:
        signals.append("beauty_fit")
    return sorted(set(signals))


def _tags_for_category(category: ProductCategory) -> list[str]:
    tags = {
        "sunscreen": ["kbeauty", "protectorsolar", "skincare", "grwm"],
        "calming_serum": ["kbeauty", "serumcoreano", "pielsensible", "rutinafacial"],
        "cleanser": ["kbeauty", "limpiadorfacial", "doblelimpieza", "rutinafacial"],
        "sheet_mask": ["kbeauty", "mascarillacoreana", "selfcare", "hidratacion"],
        "cushion_foundation": ["kbeauty", "maquillajecoreano", "glassskin", "cushioncoreano"],
    }
    return tags[category]


def _caption_for_creator(creator: NormalizedTikTokCreator, index: int) -> str:
    templates = [
        "Probando {product} coreano con textura ligera y acabado natural.",
        "GRWM con rutina K-beauty para piel real, sin filtros.",
        "Resena honesta: lo que si funciona para rutina diaria.",
        "Lo vi en TikTok y lo comparo con mis favoritos de skincare.",
        "Rutina rapida para 20s y 30s: textura, precio y resultado cosmetico.",
    ]
    product = creator.product_category.replace("_", " ")
    return templates[(index - 1) % len(templates)].format(product=product)


def _nested(raw: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = raw.get(key)
    return value if isinstance(value, dict) else None


def _hashtags_from_raw(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, dict) and item.get("name"):
            result.append(str(item["name"]))
        elif isinstance(item, str):
            result.append(item.lstrip("#"))
    return result[:30]


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _subtitle_hint(raw: dict[str, Any]) -> str | None:
    links = raw.get("subtitleLinks")
    if isinstance(links, list) and links:
        return "Provider returned subtitle links; fetch subtitle assets in multimodal worker."
    return None


def _engagement_rate(raw: dict[str, Any]) -> float | None:
    views = _to_int(raw.get("playCount"))
    if not views:
        return None
    engagement = sum(
        value or 0
        for value in (
            _to_int(raw.get("diggCount")),
            _to_int(raw.get("commentCount")),
            _to_int(raw.get("shareCount")),
            _to_int(raw.get("collectCount")),
        )
    )
    return round((engagement / views) * 100, 2)


def _clean_username(value: Any) -> str:
    if not value:
        return ""
    return str(value).strip().lstrip("@").lower()


def _slug_username(value: str) -> str:
    lowered = value.lower().replace("_", "-")
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug.replace("-", ".")[:48] or "briwell.creator"


def _display_name(username: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[._-]+", username) if part)[:80]


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
