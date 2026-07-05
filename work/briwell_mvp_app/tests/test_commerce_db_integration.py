"""DB-backed integration tests for the Shopify commerce schema (migration 008).

Follows the tests/test_db_integration.py convention: skipped unless
RUN_DB_TESTS=1 with a live PostgreSQL DATABASE_URL. These tests exercise
DB-level invariants that cannot be verified with pure-Python unit tests:
append-only ledger enforcement, reversal-integrity triggers, webhook
idempotency via partial unique indexes, refund currency matching, and the
campaign_performance_snapshot currency backfill.
"""

import os
import time
from decimal import Decimal
from types import SimpleNamespace

import psycopg
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Set RUN_DB_TESTS=1 with a live PostgreSQL DATABASE_URL to run DB integration tests.",
)


def _use_live_database(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import db as db_module

    monkeypatch.setattr(
        db_module,
        "settings",
        SimpleNamespace(
            use_database=True,
            database_url=os.environ["DATABASE_URL"],
        ),
    )


def _make_creator(suffix: str) -> str:
    from app.repositories import creators as creators_repository

    imported = creators_repository.import_creators(
        source_type="manual",
        source_risk_level="low",
        items=[
            {
                "country": "MX",
                "username": f"commerce_e2e_creator_{suffix}",
                "profile_url": f"https://example.com/@commerce_e2e_creator_{suffix}",
                "display_name": "Commerce E2E Creator",
                "bio": "kbeauty",
                "language": "es",
                "follower_count": 10_000,
                "source_url": "https://example.com/manual-import",
            }
        ],
    )
    return str(imported[0]["id"])


def _make_order(suffix: str, **overrides) -> dict:
    from app.repositories import commerce as commerce_repository

    payload = {
        "shopify_order_id": f"order-{suffix}",
        "order_number": f"#{suffix}",
        "shop_domain": "briwell-mx.myshopify.com",
        "country": "MX",
        "currency": "MXN",
        "subtotal_amount": Decimal("1000.00"),
        "discount_amount": Decimal("0.00"),
        "shipping_amount": Decimal("50.00"),
        "tax_amount": Decimal("0.00"),
        "total_amount": Decimal("1050.00"),
        "fx_rate_usd": Decimal("0.054"),
        "financial_status": "paid",
        "discount_codes": [],
        "landing_site": None,
        "utm_params": {},
        "customer_ref": None,
        "ordered_at": "2026-07-06T12:00:00Z",
        "raw_payload": {},
    }
    payload.update(overrides)
    return commerce_repository.upsert_shop_order(payload)


def test_commission_ledger_is_append_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_live_database(monkeypatch)
    from app.core.db import connection
    from app.repositories import commerce as commerce_repository

    suffix = str(int(time.time() * 1000))
    creator_id = _make_creator(suffix)
    order = _make_order(suffix)

    attribution = commerce_repository.insert_attribution(
        {
            "order_id": str(order["id"]),
            "creator_id": creator_id,
            "method": "manual",
            "confidence": "high",
            "status": "active",
            "conflict_kind": None,
            "matched_discount_code_id": None,
            "matched_utm_link_id": None,
            "competing_creator_id": None,
            "decision_notes": None,
            "decided_by": "test@briwell.test",
            "resolved_by_email": "test@briwell.test",
            "resolved_at": "2026-07-06T12:00:00Z",
        }
    )
    entry = commerce_repository.insert_ledger_entry(
        {
            "creator_id": creator_id,
            "campaign_id": None,
            "order_id": str(order["id"]),
            "attribution_id": str(attribution["id"]),
            "refund_id": None,
            "entry_type": "accrual",
            "amount": Decimal("150.00"),
            "currency": "MXN",
            "fx_rate_usd": Decimal("0.054"),
            "reverses_entry_id": None,
            "commission_rate": Decimal("0.15"),
            "memo": None,
            "created_by_email": None,
        }
    )

    with connection() as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE commission_ledger SET amount = 999.99 WHERE id = %(id)s",
                    {"id": entry["id"]},
                )
        conn.rollback()

    with connection() as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM commission_ledger WHERE id = %(id)s",
                    {"id": entry["id"]},
                )
        conn.rollback()


def test_duplicate_webhook_order_delivery_does_not_double_accrue(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_live_database(monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    headers = {"X-User-Role": "admin", "X-User-Email": "commerce-e2e@briwell.test"}
    suffix = str(int(time.time() * 1000))
    creator_id = _make_creator(suffix)

    from app.repositories import commerce as commerce_repository

    code = commerce_repository.create_discount_code(
        {
            "creator_id": creator_id,
            "campaign_id": None,
            "code": f"CODE{suffix}",
            "commission_rate": Decimal("0.15"),
            "shopify_price_rule_id": None,
            "shopify_discount_code_id": None,
            "valid_from": None,
            "valid_until": None,
            "status": "active",
        }
    )

    order_payload = {
        "shopify_order_id": f"dup-order-{suffix}",
        "order_number": f"#{suffix}",
        "shop_domain": "briwell-mx.myshopify.com",
        "country": "MX",
        "currency": "MXN",
        "subtotal_amount": "1000.00",
        "discount_amount": "0.00",
        "shipping_amount": "50.00",
        "tax_amount": "0.00",
        "total_amount": "1050.00",
        "fx_rate_usd": "0.054",
        "financial_status": "paid",
        "discount_codes": [code["code"]],
        "landing_site": None,
        "utm_params": {},
        "ordered_at": "2026-07-06T12:00:00Z",
        "line_items": [],
        "raw_payload": {},
    }

    first = client.post("/commerce/shopify/orders", headers=headers, json=order_payload)
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["status"] == "persisted"
    assert first_body["ledger_entry"] is not None

    second = client.post("/commerce/shopify/orders", headers=headers, json=order_payload)
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["status"] == "persisted"

    order_id = first_body["order"]["id"]
    ledger_rows = commerce_repository.list_ledger(order_id=order_id)
    accrual_rows = [row for row in ledger_rows if row["entry_type"] == "accrual"]
    assert len(accrual_rows) == 1


def test_reversal_cannot_exceed_accrual(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_live_database(monkeypatch)
    from app.repositories import commerce as commerce_repository

    suffix = str(int(time.time() * 1000))
    creator_id = _make_creator(suffix)
    order = _make_order(suffix)

    attribution = commerce_repository.insert_attribution(
        {
            "order_id": str(order["id"]),
            "creator_id": creator_id,
            "method": "manual",
            "confidence": "high",
            "status": "active",
            "conflict_kind": None,
            "matched_discount_code_id": None,
            "matched_utm_link_id": None,
            "competing_creator_id": None,
            "decision_notes": None,
            "decided_by": "test@briwell.test",
            "resolved_by_email": "test@briwell.test",
            "resolved_at": "2026-07-06T12:00:00Z",
        }
    )
    accrual = commerce_repository.insert_ledger_entry(
        {
            "creator_id": creator_id,
            "campaign_id": None,
            "order_id": str(order["id"]),
            "attribution_id": str(attribution["id"]),
            "refund_id": None,
            "entry_type": "accrual",
            "amount": Decimal("150.00"),
            "currency": "MXN",
            "fx_rate_usd": Decimal("0.054"),
            "reverses_entry_id": None,
            "commission_rate": Decimal("0.15"),
            "memo": None,
            "created_by_email": None,
        }
    )
    refund = commerce_repository.insert_refund(
        {
            "order_id": str(order["id"]),
            "shopify_refund_id": f"refund-{suffix}",
            "currency": "MXN",
            "commissionable_refund_amount": Decimal("1000.00"),
            "total_refund_amount": Decimal("1000.00"),
            "refund_line_items": [],
            "reason": "test",
            "processed_at": "2026-07-06T13:00:00Z",
            "raw_payload": {},
        }
    )

    with pytest.raises(psycopg.errors.RaiseException):
        commerce_repository.insert_ledger_entry(
            {
                "creator_id": creator_id,
                "campaign_id": None,
                "order_id": str(order["id"]),
                "attribution_id": str(attribution["id"]),
                "refund_id": str(refund["id"]),
                "entry_type": "reversal",
                "amount": Decimal("-999.00"),
                "currency": "MXN",
                "fx_rate_usd": Decimal("0.054"),
                "reverses_entry_id": str(accrual["id"]),
                "commission_rate": None,
                "memo": None,
                "created_by_email": None,
            }
        )


def test_refund_currency_mismatch_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_live_database(monkeypatch)
    from app.repositories import commerce as commerce_repository

    suffix = str(int(time.time() * 1000))
    order = _make_order(suffix, currency="MXN", fx_rate_usd=Decimal("0.054"))

    with pytest.raises(psycopg.errors.RaiseException):
        commerce_repository.insert_refund(
            {
                "order_id": str(order["id"]),
                "shopify_refund_id": f"refund-mismatch-{suffix}",
                "currency": "PEN",
                "commissionable_refund_amount": Decimal("10.00"),
                "total_refund_amount": Decimal("10.00"),
                "refund_line_items": [],
                "reason": None,
                "processed_at": "2026-07-06T13:00:00Z",
                "raw_payload": {},
            }
        )


def test_creator_commission_balance_separates_currency_and_sums_usd(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_live_database(monkeypatch)
    from app.repositories import commerce as commerce_repository

    suffix = str(int(time.time() * 1000))
    creator_id = _make_creator(suffix)

    orders = {
        "MXN": _make_order(f"{suffix}-mxn", shopify_order_id=f"order-{suffix}-mxn", currency="MXN", fx_rate_usd=Decimal("0.054")),
        "PEN": _make_order(f"{suffix}-pen", shopify_order_id=f"order-{suffix}-pen", currency="PEN", fx_rate_usd=Decimal("0.27")),
        "USD": _make_order(f"{suffix}-usd", shopify_order_id=f"order-{suffix}-usd", currency="USD", fx_rate_usd=Decimal("1")),
    }

    for currency, order in orders.items():
        attribution = commerce_repository.insert_attribution(
            {
                "order_id": str(order["id"]),
                "creator_id": creator_id,
                "method": "manual",
                "confidence": "high",
                "status": "active",
                "conflict_kind": None,
                "matched_discount_code_id": None,
                "matched_utm_link_id": None,
                "competing_creator_id": None,
                "decision_notes": None,
                "decided_by": "test@briwell.test",
                "resolved_by_email": "test@briwell.test",
                "resolved_at": "2026-07-06T12:00:00Z",
            }
        )
        commerce_repository.insert_ledger_entry(
            {
                "creator_id": creator_id,
                "campaign_id": None,
                "order_id": str(order["id"]),
                "attribution_id": str(attribution["id"]),
                "refund_id": None,
                "entry_type": "accrual",
                "amount": Decimal("100.00"),
                "currency": currency,
                "fx_rate_usd": order["fx_rate_usd"],
                "reverses_entry_id": None,
                "commission_rate": Decimal("0.10"),
                "memo": None,
                "created_by_email": None,
            }
        )

    balances = commerce_repository.creator_balances(creator_id=creator_id)
    assert len(balances) == 3
    by_currency = {row["currency"]: row for row in balances}
    assert by_currency["MXN"]["balance_amount"] == Decimal("100.00")
    assert by_currency["PEN"]["balance_amount"] == Decimal("100.00")
    assert by_currency["USD"]["balance_amount"] == Decimal("100.00")
    assert by_currency["USD"]["balance_usd"] == Decimal("100.00")
    assert by_currency["MXN"]["balance_usd"] == Decimal("5.40")
    assert by_currency["PEN"]["balance_usd"] == Decimal("27.00")


def test_snapshot_backward_compatible_currency_backfill(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_live_database(monkeypatch)
    from app.core.db import fetch_one

    suffix = str(int(time.time() * 1000))
    created = fetch_one(
        """
        INSERT INTO campaign_performance_snapshot (
          source_type, source_risk_level, revenue_usd
        ) VALUES ('manual', 'low', %(revenue_usd)s)
        RETURNING *
        """,
        {"revenue_usd": Decimal("42.00")},
    )
    assert created is not None
    # Historical-style insert (revenue_usd only) does NOT auto-populate the
    # new currency triple -- that only happens via the one-time migration
    # backfill for rows that existed before 008 landed.
    assert created["revenue_amount"] is None
    assert created["revenue_currency"] is None

    # New-style insert with the full currency triple is accepted.
    created_new = fetch_one(
        """
        INSERT INTO campaign_performance_snapshot (
          source_type, source_risk_level, revenue_usd,
          revenue_amount, revenue_currency, fx_rate_usd
        ) VALUES ('manual', 'low', %(revenue_usd)s, %(revenue_amount)s, %(revenue_currency)s, %(fx_rate_usd)s)
        RETURNING *
        """,
        {
            "revenue_usd": Decimal("54.00"),
            "revenue_amount": Decimal("1000.00"),
            "revenue_currency": "MXN",
            "fx_rate_usd": Decimal("0.054"),
        },
    )
    assert created_new["revenue_currency"] == "MXN"

    # Partial triple (currency without amount/fx) violates the CHECK constraint.
    with pytest.raises(psycopg.errors.CheckViolation):
        fetch_one(
            """
            INSERT INTO campaign_performance_snapshot (
              source_type, source_risk_level, revenue_currency
            ) VALUES ('manual', 'low', 'MXN')
            RETURNING *
            """
        )


def test_snapshot_triple_auto_derives_revenue_usd(monkeypatch: pytest.MonkeyPatch) -> None:
    """Finding #6 follow-up: a triple-only insert must not silently leave
    revenue_usd NULL (which would drop that row's revenue from
    SUM(revenue_usd) aggregates), and an insert that supplies a WRONG
    revenue_usd alongside the triple must not persist the mismatched value
    (would mix currencies inside a USD aggregate)."""
    _use_live_database(monkeypatch)
    from app.core.db import fetch_one

    # Triple only, no revenue_usd supplied -- trigger must derive it.
    triple_only = fetch_one(
        """
        INSERT INTO campaign_performance_snapshot (
          source_type, source_risk_level,
          revenue_amount, revenue_currency, fx_rate_usd
        ) VALUES ('manual', 'low', %(revenue_amount)s, %(revenue_currency)s, %(fx_rate_usd)s)
        RETURNING *
        """,
        {
            "revenue_amount": Decimal("2000.00"),
            "revenue_currency": "PEN",
            "fx_rate_usd": Decimal("0.27"),
        },
    )
    assert triple_only is not None
    assert triple_only["revenue_usd"] == Decimal("540.00")

    # Triple + a stale/incorrect revenue_usd -- trigger must recompute from
    # the triple rather than trust the hand-entered value.
    mismatched = fetch_one(
        """
        INSERT INTO campaign_performance_snapshot (
          source_type, source_risk_level, revenue_usd,
          revenue_amount, revenue_currency, fx_rate_usd
        ) VALUES ('manual', 'low', %(revenue_usd)s, %(revenue_amount)s, %(revenue_currency)s, %(fx_rate_usd)s)
        RETURNING *
        """,
        {
            "revenue_usd": Decimal("999.99"),
            "revenue_amount": Decimal("2000.00"),
            "revenue_currency": "PEN",
            "fx_rate_usd": Decimal("0.27"),
        },
    )
    assert mismatched["revenue_usd"] == Decimal("540.00")


# ---------------------------------------------------------------------------
# resolve_attribution: reject/confirm/reassign ledger integrity
# (adversarial-review findings #1/#3/#4/#5/#6/#8/#9/#10/#11 in the 2026-07-05
# architecture audit)
# ---------------------------------------------------------------------------


def _resolve(client, attribution_id: str, headers: dict, **payload) -> dict:
    response = client.post(
        f"/commerce/attributions/{attribution_id}/resolve",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_reassign_offsets_net_balance_not_gross_accrual(monkeypatch: pytest.MonkeyPatch) -> None:
    """A partially-refunded order, then reassigned, must not leave the
    original creator with a phantom negative balance, and the new creator
    must not be accrued commission on the already-refunded portion."""
    _use_live_database(monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app
    from app.repositories import commerce as commerce_repository

    client = TestClient(app)
    headers = {"X-User-Role": "admin", "X-User-Email": "commerce-e2e@briwell.test"}
    suffix = str(int(time.time() * 1000))
    creator_a = _make_creator(f"{suffix}-a")
    creator_b = _make_creator(f"{suffix}-b")

    order = _make_order(
        f"reassign-{suffix}",
        shopify_order_id=f"reassign-order-{suffix}",
        subtotal_amount=Decimal("1000.00"),
        discount_amount=Decimal("0.00"),
    )
    order_id = str(order["id"])

    attribution = commerce_repository.insert_attribution(
        {
            "order_id": order_id,
            "creator_id": creator_a,
            "method": "manual",
            "confidence": "high",
            "status": "active",
            "conflict_kind": None,
            "matched_discount_code_id": None,
            "matched_utm_link_id": None,
            "competing_creator_id": None,
            "decision_notes": None,
            "decided_by": "test@briwell.test",
            "resolved_by_email": "test@briwell.test",
            "resolved_at": "2026-07-06T12:00:00Z",
        }
    )
    accrual = commerce_repository.insert_ledger_entry(
        {
            "creator_id": creator_a,
            "campaign_id": None,
            "order_id": order_id,
            "attribution_id": str(attribution["id"]),
            "refund_id": None,
            "entry_type": "accrual",
            "amount": Decimal("150.00"),
            "currency": "MXN",
            "fx_rate_usd": Decimal("0.054"),
            "reverses_entry_id": None,
            "commission_rate": Decimal("0.15"),
            "memo": None,
            "created_by_email": None,
        }
    )
    refund = commerce_repository.insert_refund(
        {
            "order_id": order_id,
            "shopify_refund_id": f"reassign-refund-{suffix}",
            "currency": "MXN",
            "commissionable_refund_amount": Decimal("500.00"),
            "total_refund_amount": Decimal("500.00"),
            "refund_line_items": [],
            "reason": "partial return",
            "processed_at": "2026-07-06T13:00:00Z",
            "raw_payload": {},
        }
    )
    commerce_repository.insert_ledger_entry(
        {
            "creator_id": creator_a,
            "campaign_id": None,
            "order_id": order_id,
            "attribution_id": str(attribution["id"]),
            "refund_id": str(refund["id"]),
            "entry_type": "reversal",
            "amount": Decimal("-75.00"),
            "currency": "MXN",
            "fx_rate_usd": Decimal("0.054"),
            "reverses_entry_id": str(accrual["id"]),
            "commission_rate": None,
            "memo": None,
            "created_by_email": None,
        }
    )

    body = _resolve(
        client,
        str(attribution["id"]),
        headers,
        action="reassign",
        creator_id=creator_b,
        notes="wrong creator",
    )
    assert body["adjustment_entry"]["amount"] == Decimal("-75.00")

    balances = {row["creator_id"]: row for row in commerce_repository.creator_balances()}
    assert balances[creator_a]["balance_amount"] == Decimal("0.00")
    # New creator is accrued on the UNREFUNDED remainder (500), at the
    # 10% manual default (creator_b has no discount code/UTM link on file).
    assert body["ledger_entry"]["amount"] == Decimal("50.00")
    assert balances[creator_b]["balance_amount"] == Decimal("50.00")


def test_reassign_uses_target_creators_own_commission_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_live_database(monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app
    from app.repositories import commerce as commerce_repository

    client = TestClient(app)
    headers = {"X-User-Role": "admin", "X-User-Email": "commerce-e2e@briwell.test"}
    suffix = str(int(time.time() * 1000))
    creator_a = _make_creator(f"{suffix}-a")
    creator_b = _make_creator(f"{suffix}-b")

    commerce_repository.create_discount_code(
        {
            "creator_id": creator_b,
            "campaign_id": None,
            "code": f"BCODE{suffix}",
            "commission_rate": Decimal("0.20"),
            "shopify_price_rule_id": None,
            "shopify_discount_code_id": None,
            "valid_from": None,
            "valid_until": None,
            "status": "active",
        }
    )

    order = _make_order(
        f"reassign-rate-{suffix}",
        shopify_order_id=f"reassign-rate-order-{suffix}",
        subtotal_amount=Decimal("1000.00"),
        discount_amount=Decimal("0.00"),
    )
    order_id = str(order["id"])
    attribution = commerce_repository.insert_attribution(
        {
            "order_id": order_id,
            "creator_id": creator_a,
            "method": "manual",
            "confidence": "high",
            "status": "active",
            "conflict_kind": None,
            "matched_discount_code_id": None,
            "matched_utm_link_id": None,
            "competing_creator_id": None,
            "decision_notes": None,
            "decided_by": "test@briwell.test",
            "resolved_by_email": "test@briwell.test",
            "resolved_at": "2026-07-06T12:00:00Z",
        }
    )

    body = _resolve(
        client,
        str(attribution["id"]),
        headers,
        action="reassign",
        creator_id=creator_b,
        notes="give to B",
    )
    # 1000 base * B's own 20% code rate = 200.00, not the 10% manual default.
    assert body["ledger_entry"]["commission_rate"] == Decimal("0.20")
    assert body["ledger_entry"]["amount"] == Decimal("200.00")


def test_reject_liquidates_existing_accrual(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rejecting an attribution that was already confirmed (has an accrual)
    must post an offsetting adjustment so the creator's balance goes to
    zero -- otherwise a rejected attribution still pays out."""
    _use_live_database(monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app
    from app.repositories import commerce as commerce_repository

    client = TestClient(app)
    headers = {"X-User-Role": "admin", "X-User-Email": "commerce-e2e@briwell.test"}
    suffix = str(int(time.time() * 1000))
    creator_id = _make_creator(suffix)
    order = _make_order(f"reject-{suffix}", shopify_order_id=f"reject-order-{suffix}")
    order_id = str(order["id"])

    attribution = commerce_repository.insert_attribution(
        {
            "order_id": order_id,
            "creator_id": creator_id,
            "method": "manual",
            "confidence": "high",
            "status": "active",
            "conflict_kind": None,
            "matched_discount_code_id": None,
            "matched_utm_link_id": None,
            "competing_creator_id": None,
            "decision_notes": None,
            "decided_by": "test@briwell.test",
            "resolved_by_email": "test@briwell.test",
            "resolved_at": "2026-07-06T12:00:00Z",
        }
    )
    commerce_repository.insert_ledger_entry(
        {
            "creator_id": creator_id,
            "campaign_id": None,
            "order_id": order_id,
            "attribution_id": str(attribution["id"]),
            "refund_id": None,
            "entry_type": "accrual",
            "amount": Decimal("100.00"),
            "currency": "MXN",
            "fx_rate_usd": Decimal("0.054"),
            "reverses_entry_id": None,
            "commission_rate": Decimal("0.10"),
            "memo": None,
            "created_by_email": None,
        }
    )

    body = _resolve(client, str(attribution["id"]), headers, action="reject")
    assert body["attribution"]["status"] == "rejected"
    assert body["adjustment_entry"]["amount"] == Decimal("-100.00")

    balances = {row["creator_id"]: row for row in commerce_repository.creator_balances(creator_id=creator_id)}
    assert balances[creator_id]["balance_amount"] == Decimal("0.00")


def test_reject_without_prior_accrual_is_a_no_op_ledger_wise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rejecting a needs_review attribution that never accrued must not
    fabricate a ledger entry."""
    _use_live_database(monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app
    from app.repositories import commerce as commerce_repository

    client = TestClient(app)
    headers = {"X-User-Role": "admin", "X-User-Email": "commerce-e2e@briwell.test"}
    suffix = str(int(time.time() * 1000))
    creator_id = _make_creator(suffix)
    order = _make_order(f"reject-noop-{suffix}", shopify_order_id=f"reject-noop-order-{suffix}")
    order_id = str(order["id"])

    attribution = commerce_repository.insert_attribution(
        {
            "order_id": order_id,
            "creator_id": creator_id,
            "method": "manual",
            "confidence": "medium",
            "status": "needs_review",
            "conflict_kind": "code_vs_utm",
            "matched_discount_code_id": None,
            "matched_utm_link_id": None,
            "competing_creator_id": None,
            "decision_notes": None,
            "decided_by": "rules_v1",
            "resolved_by_email": None,
            "resolved_at": None,
        }
    )

    body = _resolve(client, str(attribution["id"]), headers, action="reject")
    assert body["attribution"]["status"] == "rejected"
    assert body["adjustment_entry"] is None
    assert commerce_repository.list_ledger(order_id=order_id) == []


def test_confirm_backfills_refunds_that_predate_the_accrual(monkeypatch: pytest.MonkeyPatch) -> None:
    """A refund that arrives while an attribution is needs_review is not
    reversed (no accrual exists yet to reverse). Confirming afterwards must
    retroactively apply that refund against the newly created accrual."""
    _use_live_database(monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app
    from app.repositories import commerce as commerce_repository

    client = TestClient(app)
    headers = {"X-User-Role": "admin", "X-User-Email": "commerce-e2e@briwell.test"}
    suffix = str(int(time.time() * 1000))
    creator_id = _make_creator(suffix)

    order = _make_order(
        f"confirm-backfill-{suffix}",
        shopify_order_id=f"confirm-backfill-order-{suffix}",
        subtotal_amount=Decimal("1000.00"),
        discount_amount=Decimal("0.00"),
    )
    order_id = str(order["id"])

    attribution = commerce_repository.insert_attribution(
        {
            "order_id": order_id,
            "creator_id": creator_id,
            "method": "discount_code",
            "confidence": "medium",
            "status": "needs_review",
            "conflict_kind": "code_vs_utm",
            "matched_discount_code_id": None,
            "matched_utm_link_id": None,
            "competing_creator_id": None,
            "decision_notes": None,
            "decided_by": "rules_v1",
            "resolved_by_email": None,
            "resolved_at": None,
        }
    )

    # Refund processed while still needs_review -- ingest_shopify_refund
    # would have skipped writing a reversal (no active attribution/accrual).
    commerce_repository.insert_refund(
        {
            "order_id": order_id,
            "shopify_refund_id": f"confirm-backfill-refund-{suffix}",
            "currency": "MXN",
            "commissionable_refund_amount": Decimal("500.00"),
            "total_refund_amount": Decimal("500.00"),
            "refund_line_items": [],
            "reason": "partial return during review",
            "processed_at": "2026-07-06T13:00:00Z",
            "raw_payload": {},
        }
    )

    body = _resolve(client, str(attribution["id"]), headers, action="confirm")
    assert body["ledger_entry"]["amount"] == Decimal("150.00")  # 1000 * 0.10 default manual rate
    assert len(body["backfilled_reversal_entries"]) == 1
    assert body["backfilled_reversal_entries"][0]["amount"] == Decimal("-75.00")  # 50% of the 150 accrual

    balances = {row["creator_id"]: row for row in commerce_repository.creator_balances(creator_id=creator_id)}
    assert balances[creator_id]["balance_amount"] == Decimal("75.00")


def test_resolve_commission_rate_finds_code_beyond_default_list_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """confirm must resolve the ORIGINAL matched code's rate by direct id
    lookup, not by linearly scanning a limit=50 list_discount_codes() call
    that could miss an older code once >50 codes exist for other creators."""
    _use_live_database(monkeypatch)
    from fastapi.testclient import TestClient

    from app.main import app
    from app.repositories import commerce as commerce_repository

    client = TestClient(app)
    headers = {"X-User-Role": "admin", "X-User-Email": "commerce-e2e@briwell.test"}
    suffix = str(int(time.time() * 1000))
    creator_id = _make_creator(suffix)

    matched_code = commerce_repository.create_discount_code(
        {
            "creator_id": creator_id,
            "campaign_id": None,
            "code": f"OLD{suffix}",
            "commission_rate": Decimal("0.20"),
            "shopify_price_rule_id": None,
            "shopify_discount_code_id": None,
            "valid_from": None,
            "valid_until": None,
            "status": "active",
        }
    )

    # Push 55 newer codes for a throwaway creator so the matched code falls
    # outside list_discount_codes()'s default limit=50, ORDER BY created_at
    # DESC window.
    filler_creator = _make_creator(f"{suffix}-filler")
    for i in range(55):
        commerce_repository.create_discount_code(
            {
                "creator_id": filler_creator,
                "campaign_id": None,
                "code": f"FILLER{suffix}{i}",
                "commission_rate": Decimal("0.05"),
                "shopify_price_rule_id": None,
                "shopify_discount_code_id": None,
                "valid_from": None,
                "valid_until": None,
                "status": "active",
            }
        )

    order = _make_order(
        f"rate-limit-{suffix}",
        shopify_order_id=f"rate-limit-order-{suffix}",
        subtotal_amount=Decimal("1000.00"),
        discount_amount=Decimal("0.00"),
    )
    order_id = str(order["id"])
    attribution = commerce_repository.insert_attribution(
        {
            "order_id": order_id,
            "creator_id": creator_id,
            "method": "discount_code",
            "confidence": "medium",
            "status": "needs_review",
            "conflict_kind": "code_vs_utm",
            "matched_discount_code_id": str(matched_code["id"]),
            "matched_utm_link_id": None,
            "competing_creator_id": None,
            "decision_notes": None,
            "decided_by": "rules_v1",
            "resolved_by_email": None,
            "resolved_at": None,
        }
    )

    body = _resolve(client, str(attribution["id"]), headers, action="confirm")
    # Must resolve the matched code's real 20% rate, not silently fall back
    # to the 10% manual default because the code fell outside a limited scan.
    assert body["ledger_entry"]["commission_rate"] == Decimal("0.20")
    assert body["ledger_entry"]["amount"] == Decimal("200.00")


def test_find_active_codes_is_deterministically_ordered(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a creator has multiple active codes that both match an order's
    discount_codes list, the oldest-created code must always win -- not an
    arbitrary DB-returned order -- so repeated ingestion attempts (e.g.
    webhook redelivery hitting a different connection) reproduce the same
    accrual amount."""
    _use_live_database(monkeypatch)
    from app.repositories import commerce as commerce_repository

    suffix = str(int(time.time() * 1000))
    creator_id = _make_creator(suffix)

    older_code = commerce_repository.create_discount_code(
        {
            "creator_id": creator_id,
            "campaign_id": None,
            "code": f"OLDER{suffix}",
            "commission_rate": Decimal("0.10"),
            "shopify_price_rule_id": None,
            "shopify_discount_code_id": None,
            "valid_from": None,
            "valid_until": None,
            "status": "active",
        }
    )
    commerce_repository.create_discount_code(
        {
            "creator_id": creator_id,
            "campaign_id": None,
            "code": f"NEWER{suffix}",
            "commission_rate": Decimal("0.30"),
            "shopify_price_rule_id": None,
            "shopify_discount_code_id": None,
            "valid_from": None,
            "valid_until": None,
            "status": "active",
        }
    )

    matches = commerce_repository.find_active_codes([f"OLDER{suffix}", f"NEWER{suffix}"])
    assert len(matches) == 2
    assert str(matches[0]["id"]) == str(older_code["id"])
