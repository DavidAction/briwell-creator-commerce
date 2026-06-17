from collections.abc import Callable
from typing import Any
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.core.config import settings

try:
    import jwt
    from jwt import PyJWKClient
    from jwt import PyJWTError
except ImportError:  # pragma: no cover - exercised only if OIDC is enabled without dependency.
    jwt = None
    PyJWKClient = None
    PyJWTError = Exception


Role = str
VALID_ROLES = {"admin", "operator", "campaign_manager", "viewer"}


@dataclass(frozen=True)
class UserContext:
    role: Role
    email: str | None = None


def get_current_user(
    x_user_role: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> UserContext:
    if settings.auth_provider == "oidc":
        return _get_oidc_user(authorization)
    if settings.auth_provider != "header":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "AUTH_PROVIDER_UNSUPPORTED",
                "message": f"Unsupported AUTH_PROVIDER: {settings.auth_provider}",
            },
        )

    if x_user_role is None:
        return UserContext(role="viewer", email=x_user_email)

    role = x_user_role.strip().lower()
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PERMISSION_DENIED",
                "message": f"Unknown role: {x_user_role}",
            },
        )
    return UserContext(role=role, email=x_user_email)


def require_roles(*allowed_roles: Role) -> Callable[[UserContext], UserContext]:
    allowed = set(allowed_roles)

    def actual_dependency(
        x_user_role: str | None = Header(default=None),
        x_user_email: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> UserContext:
        user = get_current_user(
            x_user_role=x_user_role,
            x_user_email=x_user_email,
            authorization=authorization,
        )
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": f"Role {user.role} is not allowed for this action.",
                },
            )
        return user

    return actual_dependency


def _get_oidc_user(authorization: str | None) -> UserContext:
    token = _extract_bearer_token(authorization)
    claims = _decode_oidc_token(token)
    return UserContext(
        role=_role_from_claims(claims),
        email=_string_claim(claims, settings.oidc_email_claim) or _string_claim(claims, "sub"),
    )


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
            detail={
                "code": "AUTH_TOKEN_REQUIRED",
                "message": "Authorization Bearer token is required.",
            },
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
            detail={
                "code": "AUTH_TOKEN_INVALID",
                "message": "Authorization header must use Bearer token format.",
            },
        )
    return token.strip()


def _decode_oidc_token(token: str) -> dict[str, Any]:
    if jwt is None or PyJWKClient is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "OIDC_DEPENDENCY_MISSING",
                "message": "Install PyJWT[crypto] to enable OIDC token verification.",
            },
        )
    if not settings.oidc_issuer_url or not settings.oidc_audience:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "OIDC_CONFIGURATION_MISSING",
                "message": "OIDC_ISSUER_URL and OIDC_AUDIENCE are required.",
            },
        )

    jwks_client = PyJWKClient(_jwks_url())
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=list(settings.oidc_allowed_algorithms),
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer_url,
            options={"require": ["exp", "sub"]},
        )
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
            detail={
                "code": "AUTH_TOKEN_INVALID",
                "message": f"OIDC token validation failed: {exc}",
            },
        ) from exc

    if not isinstance(decoded, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
            detail={
                "code": "AUTH_TOKEN_INVALID",
                "message": "OIDC token claims must be a JSON object.",
            },
        )
    return decoded


def _jwks_url() -> str:
    if settings.oidc_jwks_url:
        return settings.oidc_jwks_url
    return settings.oidc_issuer_url.rstrip("/") + "/.well-known/jwks.json"


def _role_from_claims(claims: dict[str, Any]) -> Role:
    configured_role = _claim_value(claims, settings.oidc_role_claim)
    fallback_roles = (
        configured_role,
        _claim_value(claims, "app_metadata.briwell_role"),
        _claim_value(claims, "app_metadata.role"),
        _claim_value(claims, "user_metadata.briwell_role"),
        _claim_value(claims, "user_metadata.role"),
    )
    for value in fallback_roles:
        role = _first_valid_role(value)
        if role is not None:
            return role
    return "viewer"


def _first_valid_role(value: Any) -> Role | None:
    if isinstance(value, str):
        candidate = value.strip().lower()
        return candidate if candidate in VALID_ROLES else None
    if isinstance(value, list):
        for item in value:
            role = _first_valid_role(item)
            if role is not None:
                return role
    return None


def _string_claim(claims: dict[str, Any], claim_path: str) -> str | None:
    value = _claim_value(claims, claim_path)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _claim_value(claims: dict[str, Any], claim_path: str) -> Any:
    current: Any = claims
    for part in claim_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current
