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
