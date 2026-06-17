from app.core.readiness import ReadinessSettings
from app.core.readiness import evaluate_readiness


def base_settings(**overrides: object) -> ReadinessSettings:
    values = {
        "app_env": "development",
        "database_url": "postgresql://briwell:secret@127.0.0.1:55432/briwell",
        "use_database": True,
        "gemini_api_key": "",
        "ai_dry_run": True,
        "allow_live_provider_calls": False,
        "auth_provider": "header",
        "oidc_issuer_url": "",
        "oidc_audience": "",
        "oidc_jwks_url": "",
        "oidc_role_claim": "app_metadata.briwell_role",
        "cors_allowed_origins": ("http://127.0.0.1:8070", "http://localhost:8070"),
        "managed_secret_provider": "",
        "backup_restore_tested_at": "",
        "rate_limit_enabled": False,
    }
    values.update(overrides)
    return ReadinessSettings(**values)


def test_development_readiness_warns_for_local_db_and_header_auth() -> None:
    result = evaluate_readiness(base_settings())

    assert result["status"] == "ready_with_warnings"
    assert "HEADER_RBAC_IS_DEVELOPMENT_ONLY" in result["warnings"]
    assert "LOCAL_DATABASE_IS_DEVELOPMENT_ONLY" in result["warnings"]


def test_production_readiness_blocks_header_auth_local_db_and_missing_secrets() -> None:
    result = evaluate_readiness(base_settings(app_env="production"))

    assert result["status"] == "blocked"
    assert "HEADER_RBAC_NOT_ALLOWED_IN_PRODUCTION" in result["blockers"]
    assert "LOCALHOST_DATABASE_NOT_ALLOWED_IN_PRODUCTION" in result["blockers"]
    assert "MANAGED_SECRET_PROVIDER_MISSING" in result["blockers"]
    assert "BACKUP_RESTORE_TEST_REQUIRED" in result["blockers"]
    assert "RATE_LIMIT_NOT_ENABLED" in result["blockers"]


def test_production_readiness_allows_managed_oidc_configuration() -> None:
    result = evaluate_readiness(
        base_settings(
            app_env="production",
            database_url="postgresql://postgres.projectref:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres",
            gemini_api_key="configured",
            ai_dry_run=False,
            allow_live_provider_calls=True,
            auth_provider="oidc",
            oidc_issuer_url="https://projectref.supabase.co/auth/v1",
            oidc_audience="authenticated",
            oidc_jwks_url="https://projectref.supabase.co/auth/v1/.well-known/jwks.json",
            cors_allowed_origins=("https://dashboard.briwell.co",),
            managed_secret_provider="aws_secrets_manager",
            backup_restore_tested_at="2026-06-17T15:00:00",
            rate_limit_enabled=True,
        )
    )

    assert result["status"] == "ok"
    assert result["blockers"] == []


def test_production_readiness_blocks_placeholder_values() -> None:
    result = evaluate_readiness(
        base_settings(
            app_env="production",
            database_url="postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres",
            gemini_api_key="<managed-secret-reference>",
            ai_dry_run=False,
            allow_live_provider_calls=True,
            auth_provider="oidc",
            oidc_issuer_url="https://<project-ref>.supabase.co/auth/v1",
            oidc_audience="authenticated",
            oidc_jwks_url="https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json",
            cors_allowed_origins=("https://<dashboard-domain>",),
            managed_secret_provider="render_environment",
            backup_restore_tested_at="<iso8601-timestamp>",
            rate_limit_enabled=True,
        )
    )

    assert result["status"] == "blocked"
    assert "DATABASE_URL_PLACEHOLDER" in result["blockers"]
    assert "OIDC_CONFIGURATION_MISSING" in result["blockers"]
    assert "OIDC_JWKS_CONFIGURATION_MISSING" in result["blockers"]
    assert "CORS_ALLOWED_ORIGINS_PLACEHOLDER" in result["blockers"]
    assert "GEMINI_API_KEY_MISSING" in result["blockers"]
    assert "BACKUP_RESTORE_TEST_REQUIRED" in result["blockers"]


def test_production_readiness_blocks_localhost_cors_origin() -> None:
    result = evaluate_readiness(
        base_settings(
            app_env="production",
            database_url="postgresql://postgres.projectref:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres",
            gemini_api_key="configured",
            ai_dry_run=False,
            allow_live_provider_calls=True,
            auth_provider="oidc",
            oidc_issuer_url="https://projectref.supabase.co/auth/v1",
            oidc_audience="authenticated",
            oidc_jwks_url="https://projectref.supabase.co/auth/v1/.well-known/jwks.json",
            managed_secret_provider="aws_secrets_manager",
            backup_restore_tested_at="2026-06-17T15:00:00",
            rate_limit_enabled=True,
        )
    )

    assert result["status"] == "blocked"
    assert "CORS_LOCALHOST_ORIGIN_NOT_ALLOWED_IN_PRODUCTION" in result["blockers"]
