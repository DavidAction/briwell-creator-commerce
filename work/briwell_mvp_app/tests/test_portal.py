from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.routers import portal as portal_router


client = TestClient(app)

ADMIN = {"X-User-Role": "admin", "X-User-Email": "admin@briwell.test"}
OPERATOR = {"X-User-Role": "operator", "X-User-Email": "ops@briwell.test"}
VIEWER = {"X-User-Role": "viewer"}

CREATOR_ID = "11111111-1111-1111-1111-111111111111"
TOKEN = "a" * 32


# ---------------------------------------------------------------------------
# token issuance (operator side)
# ---------------------------------------------------------------------------


def test_issue_token_viewer_forbidden() -> None:
    response = client.post("/portal/tokens", headers=VIEWER, json={"creator_id": CREATOR_ID})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_issue_token_no_role_header_forbidden() -> None:
    response = client.post("/portal/tokens", json={"creator_id": CREATOR_ID})
    assert response.status_code == 403


def test_issue_token_without_database_returns_validated_not_persisted() -> None:
    response = client.post("/portal/tokens", headers=ADMIN, json={"creator_id": CREATOR_ID})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert body["creator_id"] == CREATOR_ID
    # Token is generated (so operators can see the shape) but NOT stored.
    assert isinstance(body["token"], str) and len(body["token"]) >= 32


def test_issue_token_unknown_creator_404(monkeypatch) -> None:
    monkeypatch.setattr(portal_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        portal_router.creators_repository, "get_creator_by_id", lambda creator_id: None
    )
    response = client.post("/portal/tokens", headers=OPERATOR, json={"creator_id": CREATOR_ID})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "CREATOR_NOT_FOUND"


def test_issue_token_persists_and_rotates(monkeypatch) -> None:
    issued: dict = {}

    def fake_issue(creator_id: str, token: str) -> dict:
        issued["creator_id"] = creator_id
        issued["token"] = token
        return {"id": "tok-1", "creator_id": creator_id, "token": token, "status": "active"}

    monkeypatch.setattr(portal_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        portal_router.creators_repository,
        "get_creator_by_id",
        lambda creator_id: {"id": creator_id, "username": "tu.usuario"},
    )
    monkeypatch.setattr(portal_router.portal_repository, "issue_token", fake_issue)

    response = client.post("/portal/tokens", headers=ADMIN, json={"creator_id": CREATOR_ID})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "persisted"
    assert body["token_id"] == "tok-1"
    assert issued["creator_id"] == CREATOR_ID
    assert body["token"] == issued["token"]


def test_revoke_tokens_viewer_forbidden() -> None:
    response = client.delete(f"/portal/tokens/{CREATOR_ID}", headers=VIEWER)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# creator-facing portal (public, token-gated)
# ---------------------------------------------------------------------------


def test_portal_me_without_database_is_503() -> None:
    response = client.get(f"/portal/me?token={TOKEN}")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "PORTAL_UNAVAILABLE"


def test_portal_me_short_token_rejected() -> None:
    response = client.get("/portal/me?token=short")
    assert response.status_code == 422


def test_portal_me_invalid_token_404(monkeypatch) -> None:
    monkeypatch.setattr(portal_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        portal_router.portal_repository, "get_active_by_token", lambda token: None
    )
    response = client.get(f"/portal/me?token={TOKEN}")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PORTAL_TOKEN_INVALID"


def test_portal_me_happy_path_returns_sanitized_view(monkeypatch) -> None:
    now = datetime(2026, 7, 12, 9, 0, tzinfo=timezone.utc)
    touched: dict = {}

    monkeypatch.setattr(portal_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        portal_router.portal_repository,
        "get_active_by_token",
        lambda token: {"id": "tok-1", "creator_id": CREATOR_ID, "status": "active"},
    )
    monkeypatch.setattr(
        portal_router.portal_repository,
        "touch_last_seen",
        lambda token_id: touched.setdefault("id", token_id),
    )
    monkeypatch.setattr(
        portal_router.creators_repository,
        "get_creator_by_id",
        lambda creator_id: {
            "id": creator_id,
            "display_name": "Tu Nombre",
            "username": "tu.usuario",
            "country": "MX",
            "internal_notes": "MUST NOT LEAK",
        },
    )
    monkeypatch.setattr(
        portal_router.commerce_repository,
        "list_discount_codes",
        lambda creator_id, status, limit: [
            {
                "code": "GLOW10",
                "status": "active",
                "commission_rate": "0.15",
                "valid_until": None,
                "shopify_price_rule_id": "SECRET-INTERNAL",
            }
        ],
    )
    monkeypatch.setattr(
        portal_router.commerce_repository,
        "list_ledger",
        lambda creator_id, limit: [
            {
                "entry_type": "accrual",
                "amount": "240.00",
                "currency": "MXN",
                "created_at": now,
                "created_by_email": "ops@briwell.test",
                "memo": "internal memo MUST NOT LEAK",
            }
        ],
    )
    # Mock mirrors the REAL creator_commission_balance view columns
    # (migration 008) so this test fails if the view contract drifts.
    monkeypatch.setattr(
        portal_router.commerce_repository,
        "creator_balances",
        lambda creator_id: [
            {
                "creator_id": creator_id,
                "currency": "MXN",
                "balance_amount": "240.00",
                "balance_usd": "12.96",
                "accrual_count": 1,
                "reversal_count": 0,
                "adjustment_count": 0,
                "last_entry_at": now,
            }
        ],
    )

    response = client.get(f"/portal/me?token={TOKEN}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"

    portal = body["portal"]
    assert portal["creator"]["display_name"] == "Tu Nombre"
    assert portal["creator"]["country"] == "MX"
    assert touched["id"] == "tok-1"

    assert portal["codes"][0]["code"] == "GLOW10"
    assert portal["movements"][0]["amount"] == "240.00"
    assert portal["balances"][0]["currency"] == "MXN"
    assert portal["balances"][0]["balance_amount"] == "240.00"

    # Field whitelist: internal identifiers, emails and memos never leak.
    raw = response.text
    assert "MUST NOT LEAK" not in raw
    assert "ops@briwell.test" not in raw
    assert "SECRET-INTERNAL" not in raw
    assert "creator_id" not in portal["balances"][0]
