from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Briwell Influencer Intelligence")
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/briwell",
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
    cors_allowed_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://127.0.0.1:8070,http://localhost:8070,http://127.0.0.1:5173,http://localhost:5173",
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


settings = Settings()
