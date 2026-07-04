"""Shared abstraction for creator/video data providers.

Every provider that Briwell integrates with (TikTok official API, licensed
vendors, creator-provided data imports, and the existing Apify scrape lane)
must conform to the ``CreatorDataProvider`` contract defined here so the rest
of the pipeline (repositories, routers, screening) can treat them uniformly.

Compliance notes:
- ``source_type``/``source_risk_level`` must match the policy allowlist in
  ``app.core.policy.ALLOWED_COLLECTION_SOURCE_TYPES``.
- Every provider must default to a deterministic ``dry_run`` mode that makes
  no network calls and requires no credentials, so the test suite (and any
  offline environment) can exercise the full pipeline without secrets.
- Live calls must be gated behind an explicit opt-in flag AND a configured
  credential; when either is missing the provider must return a ``blocked``
  result rather than raising or attempting the call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProviderStatus(BaseModel):
    """Describes a provider's identity, compliance posture, and readiness."""

    name: str
    source_type: str
    source_risk_level: str
    configured: bool
    live_supported: bool
    dry_run_default: bool
    limits: list[str] = Field(default_factory=list)


class NormalizedCreator(BaseModel):
    """Provider-agnostic creator record."""

    provider: str
    provider_creator_id: str
    country: Literal["MX", "PE", "EC"]
    username: str
    display_name: str | None = None
    profile_url: str
    profile_image_url: str | None = None
    bio: str | None = None
    follower_count: int | None = Field(default=None, ge=0)
    avg_views: int | None = Field(default=None, ge=0)
    engagement_rate: float | None = Field(default=None, ge=0)
    source_type: str
    source_risk_level: str
    product_category: str | None = None
    signals: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedVideo(BaseModel):
    """Provider-agnostic video/post record."""

    provider: str
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
    source_type: str
    source_risk_level: str
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderRunRequest(BaseModel):
    """Provider-agnostic run request.

    ``payload`` carries provider-specific input, e.g. creator-provided rows
    or official-API query/handles.
    """

    countries: list[str] = Field(default_factory=lambda: ["MX", "PE", "EC"])
    product_categories: list[str] = Field(default_factory=lambda: ["sunscreen"])
    max_results: int = Field(default=3, ge=1, le=50)
    recent_posts_per_creator: int = Field(default=20, ge=1, le=20)
    dry_run: bool | None = None
    allow_live_provider_calls: bool | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ProviderRunResult(BaseModel):
    """Provider-agnostic run result."""

    status: Literal[
        "dry_run_completed",
        "live_completed",
        "blocked",
        "not_implemented",
    ]
    provider: str
    mode: Literal["dry_run", "live"]
    source_type: str
    creator_count: int
    video_count: int
    creators: list[NormalizedCreator]
    videos_by_creator: dict[str, list[NormalizedVideo]]
    creator_import_payload: dict[str, Any]
    video_import_payloads: list[dict[str, Any]]
    next_actions: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CreatorDataProvider(ABC):
    """Abstract base class every creator/video data provider must implement."""

    name: str
    source_type: str
    source_risk_level: str

    @abstractmethod
    def status(self) -> ProviderStatus:
        """Return this provider's identity, compliance posture, and readiness."""
        raise NotImplementedError

    @abstractmethod
    def run(self, req: ProviderRunRequest) -> ProviderRunResult:
        """Execute a discovery/import run for this provider."""
        raise NotImplementedError
