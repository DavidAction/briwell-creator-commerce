from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import UserContext, require_roles
from app.core.config import settings
from app.core.readiness import ReadinessSettings
from app.core.readiness import evaluate_readiness


router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/readiness")
def readiness(
    _user: UserContext = Depends(require_roles("admin")),
) -> dict[str, Any]:
    return evaluate_readiness(
        ReadinessSettings(
            app_env=settings.app_env,
            database_url=settings.database_url,
            use_database=settings.use_database,
            gemini_api_key=settings.gemini_api_key,
            ai_dry_run=settings.ai_dry_run,
            allow_live_provider_calls=settings.allow_live_provider_calls,
            auth_provider=settings.auth_provider,
            oidc_issuer_url=settings.oidc_issuer_url,
            oidc_audience=settings.oidc_audience,
            oidc_jwks_url=settings.oidc_jwks_url,
            oidc_role_claim=settings.oidc_role_claim,
            cors_allowed_origins=settings.cors_allowed_origins,
            managed_secret_provider=settings.managed_secret_provider,
            backup_restore_tested_at=settings.backup_restore_tested_at,
            rate_limit_enabled=settings.rate_limit_enabled,
        )
    )


@router.get("/security-policy")
def security_policy(
    _user: UserContext = Depends(require_roles("admin")),
) -> dict[str, Any]:
    return {
        "auth": "Development can use MVP header RBAC; production must use OIDC bearer JWT validation.",
        "oidc_role_claim": settings.oidc_role_claim,
        "cors_allowed_origins": settings.cors_allowed_origins,
        "rate_limit": "Add gateway or middleware rate limits before public exposure.",
        "secrets": "Use managed secrets for DATABASE_URL and provider API keys.",
        "logging": "Persist request, audit, AI invocation, and payout events.",
        "backups": "Enable PostgreSQL backups and restore testing.",
        "alerts": "Monitor API errors, worker failures, DB health, and provider costs.",
        "production_blockers": [
            "HEADER_RBAC_NOT_ALLOWED_IN_PRODUCTION",
            "OIDC_CONFIGURATION_MISSING",
            "OIDC_JWKS_CONFIGURATION_MISSING",
            "OIDC_ROLE_CLAIM_MISSING",
            "LOCALHOST_DATABASE_NOT_ALLOWED_IN_PRODUCTION",
            "DATABASE_URL_PLACEHOLDER",
            "CORS_ALLOWED_ORIGINS_MISSING",
            "CORS_ALLOWED_ORIGINS_PLACEHOLDER",
            "CORS_LOCALHOST_ORIGIN_NOT_ALLOWED_IN_PRODUCTION",
            "MANAGED_SECRET_PROVIDER_MISSING",
            "BACKUP_RESTORE_TEST_REQUIRED",
            "RATE_LIMIT_NOT_ENABLED",
            "GEMINI_API_KEY_MISSING",
        ],
    }
