from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.core.auth as auth_module
from app.main import app


client = TestClient(app)


def oidc_settings(**overrides: object) -> SimpleNamespace:
    values = {
        "app_env": "production",
        "auth_provider": "oidc",
        "oidc_issuer_url": "https://project-id.supabase.co/auth/v1",
        "oidc_audience": "authenticated",
        "oidc_jwks_url": "https://project-id.supabase.co/auth/v1/.well-known/jwks.json",
        "oidc_role_claim": "app_metadata.briwell_role",
        "oidc_email_claim": "email",
        "oidc_allowed_algorithms": ("ES256", "RS256"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_header_auth_still_works_in_development_mode() -> None:
    response = client.get("/ops/readiness", headers={"X-User-Role": "admin"})

    assert response.status_code == 200


def test_oidc_mode_rejects_header_role_without_bearer_token(monkeypatch) -> None:
    monkeypatch.setattr(auth_module, "settings", oidc_settings())

    response = client.get("/ops/readiness", headers={"X-User-Role": "admin"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_TOKEN_REQUIRED"


def test_oidc_mode_uses_role_claim_from_verified_token(monkeypatch) -> None:
    monkeypatch.setattr(auth_module, "settings", oidc_settings())
    monkeypatch.setattr(
        auth_module,
        "_decode_oidc_token",
        lambda _token: {
            "sub": "user-1",
            "email": "admin@briwell.test",
            "app_metadata": {"briwell_role": "admin"},
        },
    )

    response = client.get("/ops/readiness", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200


def test_oidc_mode_defaults_missing_role_to_viewer(monkeypatch) -> None:
    monkeypatch.setattr(auth_module, "settings", oidc_settings())
    monkeypatch.setattr(
        auth_module,
        "_decode_oidc_token",
        lambda _token: {
            "sub": "user-1",
            "email": "viewer@briwell.test",
            "role": "authenticated",
        },
    )

    response = client.get("/ops/readiness", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"
