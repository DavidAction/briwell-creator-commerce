"""Creator-provided data intake provider.

This lane covers creators/agencies who directly upload (or paste) their own
profile and recent-post data -- e.g. a creator media kit, a CSV export from
their own analytics, or rows entered by a Briwell operator on the creator's
behalf with the creator's consent. There is NO network call and NO scraping
involved: "live" here simply means real supplied rows were present in the
request payload, as opposed to the deterministic dry-run sample used when no
rows are supplied (so the pipeline can be exercised offline in tests).

Per policy (``app.core.policy.ALLOWED_COLLECTION_SOURCE_TYPES``):
- source_type = "creator_provided"
- source_risk_level = "low"

Expected ``ProviderRunRequest.payload`` shapes (either works):
1. Structured:
   {
     "creators": [
        {
          "provider_creator_id": "...",   # optional, falls back to username
          "country": "MX", "username": "...", "profile_url": "...",
          "display_name": ..., "profile_image_url": ..., "bio": ...,
          "follower_count": ..., "avg_views": ..., "engagement_rate": ...,
          "product_category": ..., "signals": [...],
          "consent_ref": "...", "provided_at": "2026-07-01T00:00:00Z",
          ... (extra keys pass through into raw_metadata)
        },
        ...
     ],
     "videos_by_creator": {
        "<provider_creator_id_or_username>": [
           {"url": "...", "caption": "...", "posted_at": "...", ...},
           ...
        ],
        ...
     }
   }
2. Flat CSV-style list (creators only, no posts):
   {"rows": [{"country": "MX", "username": "...", "profile_url": "...", ...}, ...]}

Consent metadata (``consent_ref``, ``provided_at``) is passed through into
each normalized record's ``raw_metadata`` so downstream review can confirm the
creator (or their authorized agent) actually supplied the data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.providers.base import (
    CreatorDataProvider,
    NormalizedCreator,
    NormalizedVideo,
    ProviderRunRequest,
    ProviderRunResult,
    ProviderStatus,
)

SOURCE_TYPE = "creator_provided"
SOURCE_RISK_LEVEL = "low"


class CreatorProvidedProvider(CreatorDataProvider):
    """Normalizes creator-supplied (uploaded) profile and post data."""

    name = "creator_provided"
    source_type = SOURCE_TYPE
    source_risk_level = SOURCE_RISK_LEVEL

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            source_type=self.source_type,
            source_risk_level=self.source_risk_level,
            configured=True,
            live_supported=True,
            dry_run_default=True,
            limits=[
                "Requires the creator (or an authorized agent) to supply their own data.",
                "No network calls are made; data quality depends entirely on what is uploaded.",
                "Consent metadata (consent_ref/provided_at) should be captured whenever available.",
            ],
        )

    def run(self, req: ProviderRunRequest) -> ProviderRunResult:
        creator_rows, videos_by_creator_rows = _extract_rows(req.payload)
        dry_run = req.dry_run
        if dry_run is None:
            dry_run = not creator_rows

        if dry_run and not creator_rows:
            creator_rows, videos_by_creator_rows = _sample_rows()
            mode = "dry_run"
            status = "dry_run_completed"
        else:
            mode = "dry_run" if dry_run else "live"
            status = "dry_run_completed" if dry_run else "live_completed"

        creators = [_to_normalized_creator(row) for row in creator_rows[: req.max_results]]
        allowed_ids = {creator.provider_creator_id for creator in creators}
        allowed_usernames = {creator.username for creator in creators}

        videos_by_creator: dict[str, list[NormalizedVideo]] = {}
        for key, video_rows in videos_by_creator_rows.items():
            creator = _match_creator(key, creators)
            if creator is None:
                continue
            if creator.provider_creator_id not in allowed_ids and creator.username not in allowed_usernames:
                continue
            trimmed = video_rows[: req.recent_posts_per_creator]
            videos_by_creator[creator.provider_creator_id] = [
                _to_normalized_video(creator, row) for row in trimmed
            ]

        errors: list[str] = []
        if not creator_rows:
            errors.append("No creator rows were supplied in payload; nothing to normalize.")

        return ProviderRunResult(
            status=status,  # type: ignore[arg-type]
            provider=self.name,
            mode=mode,  # type: ignore[arg-type]
            source_type=self.source_type,
            creator_count=len(creators),
            video_count=sum(len(items) for items in videos_by_creator.values()),
            creators=creators,
            videos_by_creator=videos_by_creator,
            creator_import_payload=_creator_import_payload(creators),
            video_import_payloads=_video_import_payloads(videos_by_creator),
            next_actions=_next_actions(creators, videos_by_creator),
            errors=errors,
        )


def _extract_rows(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    if "creators" in payload or "videos_by_creator" in payload:
        creator_rows = list(payload.get("creators") or [])
        videos_by_creator_rows = {
            str(key): list(value or [])
            for key, value in (payload.get("videos_by_creator") or {}).items()
        }
        return creator_rows, videos_by_creator_rows
    if "rows" in payload:
        return list(payload.get("rows") or []), {}
    return [], {}


def _sample_rows() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    sample_creator = {
        "provider_creator_id": "sample-creator-provided-1",
        "country": "MX",
        "username": "sample.creator",
        "display_name": "Sample Creator",
        "profile_url": "https://www.tiktok.com/@sample.creator",
        "profile_image_url": "https://cdn.briwell.local/creator-provided/sample.jpg",
        "bio": "K-beauty skincare creator sharing my own media kit sample data.",
        "follower_count": 21000,
        "avg_views": 9500,
        "engagement_rate": 4.2,
        "product_category": "sunscreen",
        "signals": ["creator_provided_sample", "skincare_fit"],
        "consent_ref": "sample-consent-ref",
        "provided_at": "2026-07-01T00:00:00Z",
    }
    sample_video = {
        "url": "https://www.tiktok.com/@sample.creator/video/7000000000000000001",
        "platform_video_id": "7000000000000000001",
        "caption": "Sample post supplied directly by the creator for their media kit.",
        "hashtags": ["kbeauty", "skincare", "grwm"],
        "posted_at": "2026-06-20T12:00:00Z",
        "view_count": 9800,
        "like_count": 640,
        "comment_count": 52,
        "share_count": 30,
        "save_count": 41,
        "duration_seconds": 34,
        "thumbnail_url": "https://cdn.briwell.local/creator-provided/sample-1.jpg",
        "transcript": "Sample transcript supplied by the creator.",
        "consent_ref": "sample-consent-ref",
        "provided_at": "2026-07-01T00:00:00Z",
    }
    creators = [sample_creator]
    videos_by_creator = {sample_creator["provider_creator_id"]: [sample_video]}
    return creators, videos_by_creator


def _match_creator(key: str, creators: list[NormalizedCreator]) -> NormalizedCreator | None:
    for creator in creators:
        if creator.provider_creator_id == key or creator.username == key:
            return creator
    return None


def _consent_metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if row.get("consent_ref") is not None:
        metadata["consent_ref"] = row["consent_ref"]
    if row.get("provided_at") is not None:
        metadata["provided_at"] = row["provided_at"]
    return metadata


_CREATOR_KNOWN_KEYS = {
    "provider_creator_id",
    "country",
    "username",
    "display_name",
    "profile_url",
    "profile_image_url",
    "bio",
    "follower_count",
    "avg_views",
    "engagement_rate",
    "product_category",
    "signals",
    "consent_ref",
    "provided_at",
}

_VIDEO_KNOWN_KEYS = {
    "url",
    "platform_video_id",
    "caption",
    "hashtags",
    "posted_at",
    "view_count",
    "like_count",
    "comment_count",
    "share_count",
    "save_count",
    "duration_seconds",
    "thumbnail_url",
    "transcript",
    "consent_ref",
    "provided_at",
}


def _to_normalized_creator(row: dict[str, Any]) -> NormalizedCreator:
    username = str(row["username"]).strip().lstrip("@")
    provider_creator_id = str(row.get("provider_creator_id") or username)
    raw_metadata: dict[str, Any] = {
        "creator_supplied": True,
        **_consent_metadata(row),
        "extra": {k: v for k, v in row.items() if k not in _CREATOR_KNOWN_KEYS},
    }
    return NormalizedCreator(
        provider="creator_provided",
        provider_creator_id=provider_creator_id,
        country=row["country"],
        username=username,
        display_name=row.get("display_name"),
        profile_url=row.get("profile_url") or f"https://www.tiktok.com/@{username}",
        profile_image_url=row.get("profile_image_url"),
        bio=row.get("bio"),
        follower_count=row.get("follower_count"),
        avg_views=row.get("avg_views"),
        engagement_rate=row.get("engagement_rate"),
        source_type=SOURCE_TYPE,
        source_risk_level=SOURCE_RISK_LEVEL,
        product_category=row.get("product_category"),
        signals=list(row.get("signals") or []),
        raw_metadata=raw_metadata,
    )


def _to_normalized_video(creator: NormalizedCreator, row: dict[str, Any]) -> NormalizedVideo:
    raw_metadata: dict[str, Any] = {
        "creator_supplied": True,
        **_consent_metadata(row),
        "extra": {k: v for k, v in row.items() if k not in _VIDEO_KNOWN_KEYS},
    }
    return NormalizedVideo(
        provider="creator_provided",
        provider_creator_id=creator.provider_creator_id,
        creator_username=creator.username,
        url=row["url"],
        platform_video_id=row.get("platform_video_id"),
        caption=row.get("caption"),
        hashtags=list(row.get("hashtags") or []),
        posted_at=_parse_datetime(row.get("posted_at")),
        view_count=row.get("view_count"),
        like_count=row.get("like_count"),
        comment_count=row.get("comment_count"),
        share_count=row.get("share_count"),
        save_count=row.get("save_count"),
        duration_seconds=row.get("duration_seconds"),
        thumbnail_url=row.get("thumbnail_url"),
        transcript=row.get("transcript"),
        source_type=SOURCE_TYPE,
        source_risk_level=SOURCE_RISK_LEVEL,
        raw_metadata=raw_metadata,
    )


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


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


def _next_actions(
    creators: list[NormalizedCreator],
    videos_by_creator: dict[str, list[NormalizedVideo]],
) -> list[str]:
    actions = [
        "Confirm consent_ref/provided_at metadata is present before import.",
        "Import normalized creators and supplied posts into the Briwell DB.",
    ]
    if not creators:
        actions.append("Upload creator rows via payload.creators (or payload.rows) to run a real import.")
    if creators and not videos_by_creator:
        actions.append("Supply payload.videos_by_creator to include recent-post data for screening.")
    return actions
