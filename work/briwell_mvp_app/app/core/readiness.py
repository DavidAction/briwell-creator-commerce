from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ReadinessSettings:
    app_env: str
    database_url: str
    use_database: bool
    gemini_api_key: str
    ai_dry_run: bool
    allow_live_provider_calls: bool
    auth_provider: str
    oidc_issuer_url: str
    oidc_audience: str
    oidc_jwks_url: str
    oidc_role_claim: str
    cors_allowed_origins: tuple[str, ...]
    managed_secret_provider: str
    backup_restore_tested_at: str
    rate_limit_enabled: bool


def evaluate_readiness(settings: ReadinessSettings) -> dict[str, object]:
    checks = {
        "database_enabled": settings.use_database,
        "database_managed": _database_looks_managed(settings.database_url),
        "database_localhost": _database_is_localhost(settings.database_url),
        "database_url_placeholder": _looks_like_placeholder(settings.database_url),
        "gemini_api_key_configured": _is_configured(settings.gemini_api_key),
        "live_ai_calls_enabled": settings.allow_live_provider_calls and not settings.ai_dry_run,
        "app_env": settings.app_env,
        "auth_provider": settings.auth_provider,
        "header_rbac_enabled": settings.auth_provider == "header",
        "oidc_configured": _is_configured(settings.oidc_issuer_url)
        and _is_configured(settings.oidc_audience),
        "oidc_jwks_url": settings.oidc_jwks_url or _default_jwks_url(settings.oidc_issuer_url),
        "oidc_role_claim": settings.oidc_role_claim,
        "oidc_jwks_configured": _is_configured(
            settings.oidc_jwks_url or _default_jwks_url(settings.oidc_issuer_url)
        ),
        "cors_allowed_origins": settings.cors_allowed_origins,
        "cors_allowed_origins_configured": any(
            _is_configured(origin) for origin in settings.cors_allowed_origins
        ),
        "cors_allowed_origins_placeholder": any(
            _looks_like_placeholder(origin) for origin in settings.cors_allowed_origins
        ),
        "cors_localhost_origin": any(
            _origin_is_localhost(origin) for origin in settings.cors_allowed_origins
        ),
        "managed_secret_provider_configured": _is_configured(settings.managed_secret_provider),
        "backup_restore_tested": _is_configured(settings.backup_restore_tested_at),
        "rate_limit_enabled": settings.rate_limit_enabled,
        "request_id_middleware_enabled": True,
        "security_headers_enabled": True,
    }
    blockers: list[str] = []
    warnings: list[str] = []

    if settings.app_env == "production":
        if settings.auth_provider not in {"header", "oidc"}:
            blockers.append("AUTH_PROVIDER_UNSUPPORTED")
        if not settings.use_database:
            blockers.append("DATABASE_NOT_ENABLED")
        if checks["database_url_placeholder"]:
            blockers.append("DATABASE_URL_PLACEHOLDER")
        if checks["database_localhost"]:
            blockers.append("LOCALHOST_DATABASE_NOT_ALLOWED_IN_PRODUCTION")
        if not checks["database_managed"]:
            warnings.append("DATABASE_DOES_NOT_LOOK_MANAGED")
        if settings.auth_provider == "header":
            blockers.append("HEADER_RBAC_NOT_ALLOWED_IN_PRODUCTION")
        if settings.auth_provider == "oidc" and not checks["oidc_configured"]:
            blockers.append("OIDC_CONFIGURATION_MISSING")
        if settings.auth_provider == "oidc" and not checks["oidc_jwks_configured"]:
            blockers.append("OIDC_JWKS_CONFIGURATION_MISSING")
        if settings.auth_provider == "oidc" and not settings.oidc_role_claim:
            blockers.append("OIDC_ROLE_CLAIM_MISSING")
        if not checks["cors_allowed_origins_configured"]:
            blockers.append("CORS_ALLOWED_ORIGINS_MISSING")
        if checks["cors_allowed_origins_placeholder"]:
            blockers.append("CORS_ALLOWED_ORIGINS_PLACEHOLDER")
        if checks["cors_localhost_origin"]:
            blockers.append("CORS_LOCALHOST_ORIGIN_NOT_ALLOWED_IN_PRODUCTION")
        if not checks["managed_secret_provider_configured"]:
            blockers.append("MANAGED_SECRET_PROVIDER_MISSING")
        if not checks["backup_restore_tested"]:
            blockers.append("BACKUP_RESTORE_TEST_REQUIRED")
        if not checks["rate_limit_enabled"]:
            blockers.append("RATE_LIMIT_NOT_ENABLED")
        if not checks["gemini_api_key_configured"]:
            blockers.append("GEMINI_API_KEY_MISSING")
    else:
        if settings.auth_provider == "header":
            warnings.append("HEADER_RBAC_IS_DEVELOPMENT_ONLY")
        if checks["database_localhost"]:
            warnings.append("LOCAL_DATABASE_IS_DEVELOPMENT_ONLY")

    status = "blocked" if blockers else "ready_with_warnings" if warnings else "ok"
    return {
        "status": status,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "production_note": "Use managed PostgreSQL, OIDC auth, managed secrets, backups, rate limits, and monitoring before production.",
    }


def _database_is_localhost(database_url: str) -> bool:
    host = urlsplit(database_url).hostname or ""
    return host in {"localhost", "127.0.0.1", "::1"}


def _database_looks_managed(database_url: str) -> bool:
    host = urlsplit(database_url).hostname or ""
    if not host or _database_is_localhost(database_url):
        return False
    managed_markers = (
        "amazonaws.com",
        "azure.com",
        "database.windows.net",
        "cloudsql",
        "neon.tech",
        "supabase.co",
        "render.com",
        "railway.app",
        "aivencloud.com",
    )
    return any(marker in host for marker in managed_markers)


def _default_jwks_url(issuer_url: str) -> str:
    if not issuer_url:
        return ""
    return issuer_url.rstrip("/") + "/.well-known/jwks.json"


def _is_configured(value: str) -> bool:
    return bool(value.strip()) and not _looks_like_placeholder(value)


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return False
    placeholder_markers = (
        "<",
        ">",
        "example.com",
        "example.neon.tech",
        "issuer.example",
        "managed-secret-reference",
        "iso8601-timestamp",
        "replace-with",
    )
    return any(marker in lowered for marker in placeholder_markers)


def _origin_is_localhost(origin: str) -> bool:
    host = urlsplit(origin).hostname or ""
    return host in {"localhost", "127.0.0.1", "::1"}
