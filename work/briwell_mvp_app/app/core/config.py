from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
if os.getenv("BRIWELL_SKIP_DOTENV", "").strip().lower() not in {"1", "true", "yes"}:
    load_dotenv(ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Briwell Influencer Intelligence")
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:5432/briwell",
    )
    use_database: bool = os.getenv("USE_DATABASE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    allowed_source_risk_levels: tuple[str, ...] = tuple(
        level.strip()
        for level in os.getenv("ALLOWED_SOURCE_RISK_LEVELS", "low,low_medium,medium").split(",")
        if level.strip()
    )
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_api_base_url: str = os.getenv(
        "GEMINI_API_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta",
    )
    ai_dry_run: bool = os.getenv("AI_DRY_RUN", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    allow_live_provider_calls: bool = os.getenv(
        "ALLOW_LIVE_PROVIDER_CALLS",
        "false",
    ).strip().lower() in {"1", "true", "yes"}
    auth_provider: str = os.getenv("AUTH_PROVIDER", "header").strip().lower()
    oidc_issuer_url: str = os.getenv("OIDC_ISSUER_URL", "")
    oidc_audience: str = os.getenv("OIDC_AUDIENCE", "")
    oidc_jwks_url: str = os.getenv("OIDC_JWKS_URL", "")
    oidc_role_claim: str = os.getenv("OIDC_ROLE_CLAIM", "app_metadata.briwell_role")
    oidc_email_claim: str = os.getenv("OIDC_EMAIL_CLAIM", "email")
    oidc_allowed_algorithms: tuple[str, ...] = tuple(
        algorithm.strip()
        for algorithm in os.getenv("OIDC_ALLOWED_ALGORITHMS", "ES256,RS256").split(",")
        if algorithm.strip()
    )
    # Development defaults cover every local page that talks to the API:
    # dashboard (8070), Vite (5173), creator portal (8072), partner hub (8073).
    # Production sets CORS_ALLOWED_ORIGINS explicitly and the readiness gate
    # rejects localhost entries there.
    cors_allowed_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://127.0.0.1:8070,http://localhost:8070,http://127.0.0.1:5173,http://localhost:5173"
            ",http://127.0.0.1:8072,http://localhost:8072,http://127.0.0.1:8073,http://localhost:8073",
        ).split(",")
        if origin.strip()
    )
    managed_secret_provider: str = os.getenv("MANAGED_SECRET_PROVIDER", "").strip().lower()
    backup_restore_tested_at: str = os.getenv("BACKUP_RESTORE_TESTED_AT", "")
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    rate_limit_requests_per_minute: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "120"))
    rate_limit_burst: int = int(os.getenv("RATE_LIMIT_BURST", "20"))
    ai_live_require_database: bool = os.getenv("AI_LIVE_REQUIRE_DATABASE", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    ai_live_daily_call_limit: int = int(os.getenv("AI_LIVE_DAILY_CALL_LIMIT", "50"))
    ai_live_daily_cost_limit_usd: float = float(os.getenv("AI_LIVE_DAILY_COST_LIMIT_USD", "2.00"))
    ai_live_per_creator_daily_call_limit: int = int(os.getenv("AI_LIVE_PER_CREATOR_DAILY_CALL_LIMIT", "3"))
    apify_api_token: str = os.getenv("APIFY_API_TOKEN", "")
    apify_tiktok_actor_id: str = os.getenv("APIFY_TIKTOK_ACTOR_ID", "clockworks/tiktok-scraper")
    data365_api_key: str = os.getenv("DATA365_API_KEY", "")
    brightdata_api_key: str = os.getenv("BRIGHTDATA_API_KEY", "")
    tikapi_api_key: str = os.getenv("TIKAPI_API_KEY", "")
    tiktok_provider_dry_run: bool = os.getenv("TIKTOK_PROVIDER_DRY_RUN", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    allow_live_tiktok_provider_calls: bool = os.getenv(
        "ALLOW_LIVE_TIKTOK_PROVIDER_CALLS",
        "false",
    ).strip().lower() in {"1", "true", "yes"}
    tiktok_provider_daily_result_limit: int = int(os.getenv("TIKTOK_PROVIDER_DAILY_RESULT_LIMIT", "2000"))
    tiktok_client_key: str = os.getenv("TIKTOK_CLIENT_KEY", "")
    tiktok_client_secret: str = os.getenv("TIKTOK_CLIENT_SECRET", "")
    tiktok_access_token: str = os.getenv("TIKTOK_ACCESS_TOKEN", "")
    tiktok_official_dry_run: bool = os.getenv("TIKTOK_OFFICIAL_DRY_RUN", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    licensed_vendor_dry_run: bool = os.getenv("LICENSED_VENDOR_DRY_RUN", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    licensed_vendor_contract_confirmed: bool = os.getenv(
        "LICENSED_VENDOR_CONTRACT_CONFIRMED",
        "false",
    ).strip().lower() in {"1", "true", "yes"}
    outbox_worker_enabled: bool = os.getenv("OUTBOX_WORKER_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    outbox_worker_poll_interval_seconds: float = float(
        os.getenv("OUTBOX_WORKER_POLL_INTERVAL_SECONDS", "2.0")
    )
    shopify_shop_domain: str = os.getenv("SHOPIFY_SHOP_DOMAIN", "").strip()
    shopify_admin_api_token: str = os.getenv("SHOPIFY_ADMIN_API_TOKEN", "")
    shopify_api_version: str = os.getenv("SHOPIFY_API_VERSION", "2026-01").strip()
    shopify_webhook_secret: str = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")
    shopify_dry_run: bool = os.getenv("SHOPIFY_DRY_RUN", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    allow_live_shopify_calls: bool = os.getenv(
        "ALLOW_LIVE_SHOPIFY_CALLS",
        "false",
    ).strip().lower() in {"1", "true", "yes"}
    # Recorded-at-ingest FX rates for webhook orders, e.g. "MXN:0.058,PEN:0.27".
    # USD is always 1. Webhook orders in a currency missing here are rejected
    # (fail-closed) rather than persisted with a guessed rate.
    shopify_fx_rates_raw: str = os.getenv("SHOPIFY_FX_RATES", "")
    # Public Google News RSS market-signal fetcher (app/trends/news_rss.py).
    # Same dual live-gate shape as the AI/TikTok/Shopify lanes.
    news_rss_dry_run: bool = os.getenv("NEWS_RSS_DRY_RUN", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    allow_live_news_rss_calls: bool = os.getenv(
        "ALLOW_LIVE_NEWS_RSS_CALLS",
        "false",
    ).strip().lower() in {"1", "true", "yes"}
    # Brand Partner Hub (migration 010). Same dual live-gate shape as the
    # other lanes: extraction is deterministic dry-run unless BOTH flags open.
    partner_ai_dry_run: bool = os.getenv("PARTNER_AI_DRY_RUN", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    allow_live_partner_ai_calls: bool = os.getenv(
        "ALLOW_LIVE_PARTNER_AI_CALLS",
        "false",
    ).strip().lower() in {"1", "true", "yes"}
    partner_upload_dir: str = os.getenv(
        "PARTNER_UPLOAD_DIR",
        str(ROOT / "data" / "partner_uploads"),
    )
    partner_upload_max_bytes: int = int(os.getenv("PARTNER_UPLOAD_MAX_BYTES", "15000000"))
    # v2 (design doc, David-approved 2026-07-12): provider-abstracted ingestion
    # model. Default = Claude Opus 4.8 (structured-extraction leader as of
    # 2026-07); escalation slot for Claude Fable 5 on hard documents (off by
    # default). Head-to-head vs Gemini 3.5 Pro planned after its 07-17 launch —
    # switching providers is a config change, not a code change.
    partner_ai_provider: str = os.getenv("PARTNER_AI_PROVIDER", "anthropic").strip().lower()
    partner_ai_model: str = os.getenv("PARTNER_AI_MODEL", "claude-opus-4-8").strip()
    partner_ai_escalation_model: str = os.getenv("PARTNER_AI_ESCALATION_MODEL", "").strip()
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")


settings = Settings()
