"""Creator self-serve portal (roadmap 3).

Two surfaces:

* Operator side (RBAC-gated): issue/rotate and revoke portal tokens.
* Creator side (public, token-gated): ``GET /portal/me?token=...`` returns a
  read-only, field-whitelisted view of the creator's own codes, commission
  movements and balances. No login flow by design for the pilot cohort —
  the unguessable token IS the credential and rotating it is the kill
  switch. Responses never include operator emails, internal notes or other
  creators' data.
"""

import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.repositories import commerce as commerce_repository
from app.repositories import creators as creators_repository
from app.repositories import portal as portal_repository

router = APIRouter(prefix="/portal", tags=["portal"])

TOKEN_BYTES = 24  # 32-char urlsafe token — unguessable for a pilot cohort.
MOVEMENTS_LIMIT = 50


class PortalTokenRequest(BaseModel):
    creator_id: str = Field(min_length=1)


def _generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


@router.post("/tokens")
def issue_portal_token(
    payload: PortalTokenRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    """Issue (or rotate) the personal portal link token for a creator."""

    token = _generate_token()
    if not database_enabled():
        return {
            "status": "validated_not_persisted",
            "token": token,
            "creator_id": payload.creator_id,
        }

    creator = creators_repository.get_creator_by_id(payload.creator_id)
    if creator is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CREATOR_NOT_FOUND", "message": "creator_id does not exist."},
        )
    created = portal_repository.issue_token(payload.creator_id, token)
    return {
        "status": "persisted",
        "token": token,
        "token_id": str(created["id"]),
        "creator_id": payload.creator_id,
    }


@router.delete("/tokens/{creator_id}")
def revoke_portal_tokens(
    creator_id: str,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    if not database_enabled():
        return {"status": "validated_not_persisted", "revoked": 0}
    revoked = portal_repository.revoke_for_creator(creator_id)
    return {"status": "persisted", "revoked": revoked}


def _sanitize_code(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": row.get("code"),
        "status": row.get("status"),
        "commission_rate": str(row.get("commission_rate")) if row.get("commission_rate") is not None else None,
        "valid_until": row.get("valid_until"),
    }


def _sanitize_movement(row: dict[str, Any]) -> dict[str, Any]:
    # Whitelist only: never expose operator emails, memos or foreign keys.
    return {
        "entry_type": row.get("entry_type"),
        "amount": str(row.get("amount")) if row.get("amount") is not None else None,
        "currency": row.get("currency"),
        "created_at": row.get("created_at"),
    }


def _sanitize_balance(row: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(row)
    sanitized.pop("creator_id", None)
    return sanitized


@router.get("/me")
def portal_me(token: str = Query(min_length=16, max_length=128)) -> dict[str, Any]:
    """Public, token-gated creator view. Read-only by construction.

    Unlike operator reads (which return empty lists when the database is
    off), this is a consumer-facing surface: a half-working portal would
    look like a broken promise, so without persistence we fail loudly.
    """

    if not database_enabled():
        raise HTTPException(
            status_code=503,
            detail={"code": "PORTAL_UNAVAILABLE", "message": "Portal requires persistence."},
        )

    token_row = portal_repository.get_active_by_token(token)
    if token_row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PORTAL_TOKEN_INVALID", "message": "Unknown or revoked portal link."},
        )

    creator_id = str(token_row["creator_id"])
    creator = creators_repository.get_creator_by_id(creator_id)
    if creator is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PORTAL_TOKEN_INVALID", "message": "Unknown or revoked portal link."},
        )

    portal_repository.touch_last_seen(str(token_row["id"]))

    codes = commerce_repository.list_discount_codes(creator_id=creator_id, status=None, limit=10)
    movements = commerce_repository.list_ledger(creator_id=creator_id, limit=MOVEMENTS_LIMIT)
    balances = commerce_repository.creator_balances(creator_id=creator_id)

    return {
        "status": "ok",
        "portal": {
            "creator": {
                "display_name": creator.get("display_name") or creator.get("username"),
                "username": creator.get("username"),
                "country": creator.get("country"),
            },
            "codes": [_sanitize_code(row) for row in codes],
            "movements": [_sanitize_movement(row) for row in movements],
            "balances": [_sanitize_balance(row) for row in balances],
        },
    }
