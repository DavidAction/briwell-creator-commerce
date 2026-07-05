from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, model_validator

from app.commerce.allocation import compute_accrual, compute_refund_reversal
from app.commerce.attribution import CodeMatch, UtmMatch, decide_attribution
from app.commerce.money import to_usd
from app.core.auth import UserContext, require_roles
from app.core.db import connection, database_enabled
from app.repositories import audit_events as audit_events_repository
from app.repositories import commerce as commerce_repository


router = APIRouter(prefix="/commerce", tags=["commerce"])

Currency = Literal["MXN", "PEN", "USD"]
FinancialStatus = Literal[
    "pending", "authorized", "paid", "partially_paid",
    "partially_refunded", "refunded", "voided", "cancelled",
]
DiscountCodeStatus = Literal["active", "paused", "expired", "revoked"]
UtmLinkStatus = Literal["active", "paused", "revoked"]
AttributionStatus = Literal["active", "needs_review", "superseded", "rejected"]
ResolveAction = Literal["confirm", "reassign", "reject"]


def _validate_currency_fx(currency: str, fx_rate_usd: Decimal) -> None:
    if currency == "USD" and fx_rate_usd != Decimal("1"):
        raise ValueError("fx_rate_usd must equal 1 when currency is USD.")


class LineItemPayload(BaseModel):
    shopify_line_item_id: str | None = None
    title: str = Field(min_length=1)
    sku: str | None = None
    product_id: str | None = None
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    total_discount: Decimal = Field(default=Decimal("0"), ge=0)


class ShopifyOrderIngestRequest(BaseModel):
    shopify_order_id: str = Field(min_length=1)
    order_number: str | None = None
    shop_domain: str | None = None
    country: Literal["MX", "PE", "EC"] | None = None
    currency: Currency
    subtotal_amount: Decimal = Field(ge=0)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    shipping_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    total_amount: Decimal = Field(ge=0)
    fx_rate_usd: Decimal = Field(gt=0)
    financial_status: FinancialStatus = "pending"
    discount_codes: list[str] = Field(default_factory=list)
    landing_site: str | None = None
    utm_params: dict[str, Any] = Field(default_factory=dict)
    customer_ref: str | None = None
    ordered_at: datetime
    line_items: list[LineItemPayload] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_fx_for_usd(self) -> "ShopifyOrderIngestRequest":
        _validate_currency_fx(self.currency, self.fx_rate_usd)
        return self


class OrderRefundIngestRequest(BaseModel):
    order_shopify_order_id: str = Field(min_length=1)
    shopify_refund_id: str = Field(min_length=1)
    currency: Currency
    commissionable_refund_amount: Decimal = Field(ge=0)
    total_refund_amount: Decimal = Field(ge=0)
    refund_line_items: list[dict[str, Any]] = Field(default_factory=list)
    reason: str | None = None
    processed_at: datetime
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class DiscountCodeCreateRequest(BaseModel):
    creator_id: str = Field(min_length=1)
    campaign_id: str | None = None
    code: str = Field(min_length=3, max_length=64)
    commission_rate: Decimal = Field(ge=0, le=Decimal("0.5"))
    shopify_price_rule_id: str | None = None
    shopify_discount_code_id: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    status: DiscountCodeStatus = "active"

    @model_validator(mode="after")
    def normalize_code(self) -> "DiscountCodeCreateRequest":
        object.__setattr__(self, "code", self.code.strip().upper())
        return self


class UtmLinkCreateRequest(BaseModel):
    creator_id: str = Field(min_length=1)
    campaign_id: str | None = None
    ref_token: str = Field(min_length=4, max_length=64)
    destination_url: str = Field(min_length=1)
    utm_source: str = "tiktok"
    utm_medium: str = "creator_bio"
    utm_campaign: str | None = None
    commission_rate: Decimal = Field(ge=0, le=Decimal("0.5"))
    status: UtmLinkStatus = "active"

    @model_validator(mode="after")
    def normalize_ref_token(self) -> "UtmLinkCreateRequest":
        object.__setattr__(self, "ref_token", self.ref_token.strip().lower())
        return self


class AttributionResolveRequest(BaseModel):
    action: ResolveAction
    creator_id: str | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_creator_for_reassign(self) -> "AttributionResolveRequest":
        if self.action == "reassign" and not self.creator_id:
            raise ValueError("creator_id is required when action=reassign.")
        return self


# ---------------------------------------------------------------------------
# Shared attribution/accrual decision helper (used by both persisted and
# validated_not_persisted paths so previews match what would actually happen).
# ---------------------------------------------------------------------------


def _decision_for_order(payload: ShopifyOrderIngestRequest) -> dict[str, Any]:
    code_matches: list[CodeMatch] = []
    if database_enabled() and payload.discount_codes:
        for row in commerce_repository.find_active_codes(payload.discount_codes):
            code_matches.append(
                CodeMatch(
                    id=str(row["id"]),
                    creator_id=str(row["creator_id"]),
                    commission_rate=str(row["commission_rate"]),
                )
            )

    utm_match: UtmMatch | None = None
    if database_enabled():
        ref_token = payload.utm_params.get("utm_content") or payload.utm_params.get("content")
        row = commerce_repository.find_active_utm_link(ref_token if isinstance(ref_token, str) else None)
        if row is not None:
            utm_match = UtmMatch(
                id=str(row["id"]),
                creator_id=str(row["creator_id"]),
                commission_rate=str(row["commission_rate"]),
            )

    decision = decide_attribution(code_matches, utm_match)

    commissionable_base = payload.subtotal_amount - payload.discount_amount
    accrual_preview: dict[str, Any] | None = None
    if decision.creator_id is not None and decision.commission_rate is not None:
        accrual = compute_accrual(
            commissionable_base=commissionable_base,
            commission_rate=Decimal(decision.commission_rate),
            currency=payload.currency,
            fx_rate_usd=payload.fx_rate_usd,
        )
        accrual_preview = {
            "amount": accrual.amount,
            "currency": accrual.currency,
            "fx_rate_usd": accrual.fx_rate_usd,
            "amount_usd": to_usd(accrual.amount, accrual.fx_rate_usd),
            "commission_rate": accrual.commission_rate,
        }

    return {
        "decision": decision,
        "accrual_preview": accrual_preview,
        "commissionable_base": commissionable_base,
    }


def _decision_to_dict(decision: Any) -> dict[str, Any]:
    return {
        "creator_id": decision.creator_id,
        "method": decision.method,
        "confidence": decision.confidence,
        "status": decision.status,
        "conflict_kind": decision.conflict_kind,
        "matched_discount_code_id": decision.matched_discount_code_id,
        "matched_utm_link_id": decision.matched_utm_link_id,
        "competing_creator_id": decision.competing_creator_id,
        "should_accrue": decision.should_accrue,
    }


# ---------------------------------------------------------------------------
# Shopify webhook-shaped ingestion
# ---------------------------------------------------------------------------


@router.post("/shopify/orders")
def ingest_shopify_order(
    payload: ShopifyOrderIngestRequest,
    user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    computed = _decision_for_order(payload)
    decision = computed["decision"]
    accrual_preview = computed["accrual_preview"]

    if not database_enabled():
        return {
            "status": "validated_not_persisted",
            "order": payload.model_dump(),
            "attribution": _decision_to_dict(decision),
            "accrual_preview": accrual_preview,
        }

    order_payload = payload.model_dump(exclude={"line_items", "discount_codes"})
    order_payload["discount_codes"] = payload.discount_codes

    attribution_record: dict[str, Any] | None = None
    ledger_entry: dict[str, Any] | None = None

    # The order upsert, line items, attribution insert, and accrual ledger
    # entry must land as a single all-or-nothing unit: if the ledger insert
    # fails after the attribution has already been committed, a webhook
    # redelivery would see `existing_live is not None` and permanently skip
    # accrual creation, silently losing the creator's commission.
    with connection() as conn:
        order = commerce_repository.upsert_shop_order(order_payload, conn=conn)
        order_id = str(order["id"])

        line_items = commerce_repository.insert_line_items(
            order_id,
            [item.model_dump() for item in payload.line_items],
            conn=conn,
        )

        existing_live = commerce_repository.get_live_attribution(order_id, conn=conn)

        if decision.creator_id is not None and existing_live is None:
            attribution_record = commerce_repository.insert_attribution(
                {
                    "order_id": order_id,
                    "creator_id": decision.creator_id,
                    "method": decision.method,
                    "confidence": decision.confidence,
                    "status": decision.status,
                    "conflict_kind": decision.conflict_kind,
                    "matched_discount_code_id": decision.matched_discount_code_id,
                    "matched_utm_link_id": decision.matched_utm_link_id,
                    "competing_creator_id": decision.competing_creator_id,
                    "decision_notes": None,
                    "decided_by": "rules_v1",
                    "resolved_by_email": None,
                    "resolved_at": None,
                },
                conn=conn,
            )
            if decision.should_accrue:
                commissionable_base = computed["commissionable_base"]
                accrual = compute_accrual(
                    commissionable_base=commissionable_base,
                    commission_rate=Decimal(decision.commission_rate),
                    currency=payload.currency,
                    fx_rate_usd=payload.fx_rate_usd,
                )
                ledger_entry = commerce_repository.insert_ledger_entry(
                    {
                        "creator_id": decision.creator_id,
                        "campaign_id": None,
                        "order_id": order_id,
                        "attribution_id": str(attribution_record["id"]),
                        "refund_id": None,
                        "entry_type": "accrual",
                        "amount": accrual.amount,
                        "currency": accrual.currency,
                        "fx_rate_usd": accrual.fx_rate_usd,
                        "reverses_entry_id": None,
                        "commission_rate": accrual.commission_rate,
                        "memo": None,
                        "created_by_email": None,
                    },
                    conn=conn,
                )
            audit_events_repository.record_event(
                conn,
                event_type="order_attribution.decided",
                aggregate_type="shop_order",
                aggregate_id=order_id,
                actor_role=user.role,
                actor_email=user.email,
                payload=Jsonb(
                    {
                        "attribution_id": str(attribution_record["id"]),
                        "method": decision.method,
                        "confidence": decision.confidence,
                        "status": decision.status,
                        "should_accrue": decision.should_accrue,
                    }
                ),
            )
        elif existing_live is not None:
            attribution_record = existing_live
        conn.commit()

    return {
        "status": "persisted",
        "order": order,
        "line_items": line_items,
        "attribution": attribution_record,
        "ledger_entry": ledger_entry,
    }


@router.post("/shopify/refunds")
def ingest_shopify_refund(
    payload: OrderRefundIngestRequest,
    user: UserContext = Depends(require_roles("admin", "operator")),
) -> dict[str, Any]:
    if not database_enabled():
        return {
            "status": "validated_not_persisted",
            "refund": payload.model_dump(),
        }

    order = commerce_repository.get_order_by_shopify_id(payload.order_shopify_order_id)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ORDER_NOT_FOUND",
                "message": f"No shop_order found for shopify_order_id={payload.order_shopify_order_id}",
            },
        )
    if payload.currency != order["currency"]:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REFUND_CURRENCY_MISMATCH",
                "message": f"Refund currency {payload.currency} does not match order currency {order['currency']}.",
            },
        )

    order_id = str(order["id"])
    refund = commerce_repository.insert_refund(
        {
            "order_id": order_id,
            "shopify_refund_id": payload.shopify_refund_id,
            "currency": payload.currency,
            "commissionable_refund_amount": payload.commissionable_refund_amount,
            "total_refund_amount": payload.total_refund_amount,
            "refund_line_items": payload.refund_line_items,
            "reason": payload.reason,
            "processed_at": payload.processed_at,
            "raw_payload": payload.raw_payload,
        }
    )
    refund_id = str(refund["id"])

    live_attribution = commerce_repository.get_live_attribution(order_id)
    reversal_entry: dict[str, Any] | None = None

    if live_attribution is not None and live_attribution["status"] == "active":
        accrual = commerce_repository.get_accrual_for_attribution(str(live_attribution["id"]))
        if accrual is not None:
            existing_reversal = commerce_repository.get_reversal_for_refund(str(accrual["id"]), refund_id)
            if existing_reversal is None:
                # Commissionable base is derived from the order itself (exact),
                # not back-derived from the accrual/rate (would compound rounding).
                commissionable_base = Decimal(str(order["subtotal_amount"])) - Decimal(str(order["discount_amount"]))
                cumulative_refunded_before = _cumulative_refunded_before(order_id, refund_id)
                reversal_amount = compute_refund_reversal(
                    accrual_amount=Decimal(str(accrual["amount"])),
                    commissionable_base=commissionable_base,
                    cumulative_refunded_before=cumulative_refunded_before,
                    refund_commissionable_amount=payload.commissionable_refund_amount,
                )
                if reversal_amount != 0:
                    reversal_entry = commerce_repository.insert_ledger_entry(
                        {
                            "creator_id": accrual["creator_id"],
                            "campaign_id": accrual["campaign_id"],
                            "order_id": order_id,
                            "attribution_id": accrual["attribution_id"],
                            "refund_id": refund_id,
                            "entry_type": "reversal",
                            "amount": reversal_amount,
                            "currency": accrual["currency"],
                            "fx_rate_usd": accrual["fx_rate_usd"],
                            "reverses_entry_id": str(accrual["id"]),
                            "commission_rate": None,
                            "memo": None,
                            "created_by_email": None,
                        }
                    )
            else:
                reversal_entry = existing_reversal

    return {
        "status": "persisted",
        "refund": refund,
        "reversal_entry": reversal_entry,
    }


def _cumulative_refunded_before(order_id: str, current_refund_id: str) -> Decimal:
    refunds = commerce_repository.list_refunds_for_order(order_id)
    total = Decimal("0")
    for refund in refunds:
        if str(refund["id"]) == current_refund_id:
            continue
        total += Decimal(str(refund["commissionable_refund_amount"]))
    return total


# ---------------------------------------------------------------------------
# Discount codes / UTM links
# ---------------------------------------------------------------------------


@router.post("/discount-codes")
def create_discount_code(
    payload: DiscountCodeCreateRequest,
    _user: UserContext = Depends(require_roles("admin", "campaign_manager")),
) -> dict[str, Any]:
    normalized = payload.model_dump()
    if database_enabled():
        created = commerce_repository.create_discount_code(normalized)
        return {"status": "persisted", "discount_code": created}
    return {"status": "validated_not_persisted", "discount_code": normalized}


@router.get("/discount-codes")
def list_discount_codes(
    creator_id: str | None = None,
    status: DiscountCodeStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager", "viewer")),
) -> dict[str, Any]:
    if database_enabled():
        items = commerce_repository.list_discount_codes(creator_id=creator_id, status=status, limit=limit)
    else:
        items = []
    return {"status": "ok", "items": items}


@router.post("/utm-links")
def create_utm_link(
    payload: UtmLinkCreateRequest,
    _user: UserContext = Depends(require_roles("admin", "campaign_manager")),
) -> dict[str, Any]:
    normalized = payload.model_dump()
    if database_enabled():
        created = commerce_repository.create_utm_link(normalized)
        return {"status": "persisted", "utm_link": created}
    return {"status": "validated_not_persisted", "utm_link": normalized}


@router.get("/utm-links")
def list_utm_links(
    creator_id: str | None = None,
    status: UtmLinkStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager", "viewer")),
) -> dict[str, Any]:
    if database_enabled():
        items = commerce_repository.list_utm_links(creator_id=creator_id, status=status, limit=limit)
    else:
        items = []
    return {"status": "ok", "items": items}


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


@router.get("/orders")
def list_orders(
    limit: int = Query(default=50, ge=1, le=200),
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager", "viewer")),
) -> dict[str, Any]:
    if database_enabled():
        items = commerce_repository.list_orders(limit=limit)
    else:
        items = []
    return {"status": "ok", "items": items}


@router.get("/orders/{order_id}")
def get_order(
    order_id: str,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager", "viewer")),
) -> dict[str, Any]:
    if not database_enabled():
        raise HTTPException(
            status_code=400,
            detail={
                "code": "DATABASE_DISABLED",
                "message": "Set USE_DATABASE=true to look up persisted orders.",
            },
        )
    order = commerce_repository.get_order_by_id(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "Order not found."})

    return {
        "status": "ok",
        "order": order,
        "line_items": commerce_repository.list_line_items_for_order(order_id),
        "refunds": commerce_repository.list_refunds_for_order(order_id),
        "attribution": commerce_repository.get_live_attribution(order_id),
        "ledger": commerce_repository.list_ledger(order_id=order_id),
    }


# ---------------------------------------------------------------------------
# Attributions
# ---------------------------------------------------------------------------


@router.get("/attributions")
def list_attributions(
    status: AttributionStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager", "viewer")),
) -> dict[str, Any]:
    if database_enabled():
        items = commerce_repository.list_attributions(status=status, limit=limit)
    else:
        items = []
    return {"status": "ok", "items": items}


@router.post("/attributions/{attribution_id}/resolve")
def resolve_attribution(
    attribution_id: str,
    payload: AttributionResolveRequest,
    user: UserContext = Depends(require_roles("admin", "campaign_manager")),
) -> dict[str, Any]:
    if not database_enabled():
        return {
            "status": "validated_not_persisted",
            "resolution": payload.model_dump(),
        }

    attribution = commerce_repository.get_attribution(attribution_id)
    if attribution is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ATTRIBUTION_NOT_FOUND", "message": "Attribution not found."},
        )
    if attribution["status"] not in {"active", "needs_review"}:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ATTRIBUTION_NOT_LIVE",
                "message": f"Attribution is already {attribution['status']} and cannot be resolved again.",
            },
        )

    if not user.email:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "OPERATOR_EMAIL_REQUIRED",
                "message": "X-User-Email is required to resolve an attribution.",
            },
        )

    order_id = str(attribution["order_id"])
    result: dict[str, Any] = {"status": "persisted"}

    if payload.action == "reject":
        with connection() as conn:
            updated = commerce_repository.supersede_attribution(
                attribution_id, "rejected", user.email, conn=conn
            )
            reversal_entry = _liquidate_attribution_accrual(
                attribution_id=attribution_id,
                order_id=order_id,
                reason=f"Attribution rejected by {user.email}: {payload.notes or 'no notes'}",
                user=user,
                conn=conn,
            )
            conn.commit()
        result["attribution"] = updated
        result["adjustment_entry"] = reversal_entry
        _audit_resolution(order_id, attribution_id, payload, user)
        return result

    if payload.action == "confirm":
        with connection() as conn:
            updated = commerce_repository.supersede_attribution(
                attribution_id, "active", user.email, conn=conn
            )
            ledger_entry = None
            existing_accrual = commerce_repository.get_accrual_for_attribution(attribution_id, conn=conn)
            if existing_accrual is None:
                order = commerce_repository.get_order_by_id(order_id, conn=conn)
                commissionable_base = Decimal(str(order["subtotal_amount"])) - Decimal(str(order["discount_amount"]))
                commission_rate = _resolve_commission_rate(updated)
                accrual = compute_accrual(
                    commissionable_base=commissionable_base,
                    commission_rate=commission_rate,
                    currency=order["currency"],
                    fx_rate_usd=Decimal(str(order["fx_rate_usd"])),
                )
                ledger_entry = commerce_repository.insert_ledger_entry(
                    {
                        "creator_id": updated["creator_id"],
                        "campaign_id": None,
                        "order_id": order_id,
                        "attribution_id": attribution_id,
                        "refund_id": None,
                        "entry_type": "accrual",
                        "amount": accrual.amount,
                        "currency": accrual.currency,
                        "fx_rate_usd": accrual.fx_rate_usd,
                        "reverses_entry_id": None,
                        "commission_rate": accrual.commission_rate,
                        "memo": None,
                        "created_by_email": None,
                    },
                    conn=conn,
                )
                # This attribution may have sat in needs_review while refund
                # webhooks arrived; ingest_shopify_refund only writes a
                # reversal when the attribution is already 'active', so any
                # refunds processed during the review window were never
                # offset. Backfill them now against the accrual we just made.
                backfilled = _backfill_refund_reversals(
                    order_id=order_id,
                    accrual=ledger_entry,
                    conn=conn,
                )
                if backfilled:
                    result["backfilled_reversal_entries"] = backfilled
            conn.commit()
        result["attribution"] = updated
        result["ledger_entry"] = ledger_entry
        _audit_resolution(order_id, attribution_id, payload, user)
        return result

    # reassign
    assert payload.creator_id is not None
    with connection() as conn:
        superseded = commerce_repository.supersede_attribution(
            attribution_id, "superseded", user.email, conn=conn
        )
        adjustment_entry = None
        existing_accrual = commerce_repository.get_accrual_for_attribution(attribution_id, conn=conn)
        if existing_accrual is not None:
            # Offset the attribution's NET balance (accrual + any refund
            # reversals already posted against it), never the gross accrual
            # amount -- otherwise a partially-refunded order leaves the old
            # creator with a phantom negative balance (money they never
            # received clawed back twice).
            net_balance = Decimal(str(commerce_repository.sum_ledger_for_attribution(attribution_id, conn=conn)))
            if net_balance != 0:
                adjustment_entry = commerce_repository.insert_ledger_entry(
                    {
                        "creator_id": existing_accrual["creator_id"],
                        "campaign_id": existing_accrual["campaign_id"],
                        "order_id": order_id,
                        "attribution_id": attribution_id,
                        "refund_id": None,
                        "entry_type": "adjustment",
                        "amount": -net_balance,
                        "currency": existing_accrual["currency"],
                        "fx_rate_usd": existing_accrual["fx_rate_usd"],
                        "reverses_entry_id": None,
                        "commission_rate": None,
                        "memo": f"Reassigned by {user.email}: {payload.notes or 'no notes'}",
                        "created_by_email": user.email,
                    },
                    conn=conn,
                )

        new_attribution = commerce_repository.insert_attribution(
            {
                "order_id": order_id,
                "creator_id": payload.creator_id,
                "method": "manual",
                "confidence": "high",
                "status": "active",
                "conflict_kind": "manual_override",
                "matched_discount_code_id": None,
                "matched_utm_link_id": None,
                "competing_creator_id": None,
                "decision_notes": payload.notes,
                "decided_by": user.email,
                "resolved_by_email": user.email,
                "resolved_at": datetime.utcnow(),
            },
            conn=conn,
        )

        order = commerce_repository.get_order_by_id(order_id, conn=conn)
        gross_commissionable_base = Decimal(str(order["subtotal_amount"])) - Decimal(str(order["discount_amount"]))
        # Net out refunds already processed on this order so a reassign
        # after a (partial) refund doesn't accrue commission on merchandise
        # that was already returned.
        already_refunded = _cumulative_refunded_for_order(order_id, conn=conn)
        net_commissionable_base = max(gross_commissionable_base - already_refunded, Decimal("0"))
        commission_rate = _resolve_commission_rate_for_creator(payload.creator_id, conn=conn)
        new_accrual = compute_accrual(
            commissionable_base=net_commissionable_base,
            commission_rate=commission_rate,
            currency=order["currency"],
            fx_rate_usd=Decimal(str(order["fx_rate_usd"])),
        )
        new_ledger_entry = commerce_repository.insert_ledger_entry(
            {
                "creator_id": payload.creator_id,
                "campaign_id": None,
                "order_id": order_id,
                "attribution_id": str(new_attribution["id"]),
                "refund_id": None,
                "entry_type": "accrual",
                "amount": new_accrual.amount,
                "currency": new_accrual.currency,
                "fx_rate_usd": new_accrual.fx_rate_usd,
                "reverses_entry_id": None,
                "commission_rate": new_accrual.commission_rate,
                "memo": None,
                "created_by_email": None,
            },
            conn=conn,
        )
        conn.commit()

    result["superseded_attribution"] = superseded
    result["adjustment_entry"] = adjustment_entry
    result["attribution"] = new_attribution
    result["ledger_entry"] = new_ledger_entry
    _audit_resolution(order_id, attribution_id, payload, user)
    return result


def _liquidate_attribution_accrual(
    attribution_id: str,
    order_id: str,
    reason: str,
    user: UserContext,
    conn: Any,
) -> dict[str, Any] | None:
    """Cancel out any ledger balance already posted for a rejected attribution.

    `reject` can be called on an attribution that was previously `confirm`ed
    (status stays 'active' until rejected), in which case an accrual (and
    possibly refund reversals) already exist. Without this offset, rejecting
    an attribution left the creator's derived balance carrying commission
    for an order that is no longer attributed to them.
    """
    existing_accrual = commerce_repository.get_accrual_for_attribution(attribution_id, conn=conn)
    if existing_accrual is None:
        return None
    net_balance = Decimal(str(commerce_repository.sum_ledger_for_attribution(attribution_id, conn=conn)))
    if net_balance == 0:
        return None
    return commerce_repository.insert_ledger_entry(
        {
            "creator_id": existing_accrual["creator_id"],
            "campaign_id": existing_accrual["campaign_id"],
            "order_id": order_id,
            "attribution_id": attribution_id,
            "refund_id": None,
            "entry_type": "adjustment",
            "amount": -net_balance,
            "currency": existing_accrual["currency"],
            "fx_rate_usd": existing_accrual["fx_rate_usd"],
            "reverses_entry_id": None,
            "commission_rate": None,
            "memo": reason,
            "created_by_email": user.email,
        },
        conn=conn,
    )


def _backfill_refund_reversals(
    order_id: str,
    accrual: dict[str, Any],
    conn: Any,
) -> list[dict[str, Any]]:
    """Write reversal entries for refunds that predate a just-created accrual.

    ingest_shopify_refund only reverses an accrual when the order's live
    attribution is already 'active' at the moment the refund webhook is
    processed. An attribution that was needs_review during that window (or
    that had no accrual at all) means refunds landed with no offsetting
    ledger entry. Confirming the attribution creates the accrual after the
    fact, so replay all refunds in processed_at order against it here.
    """
    order = commerce_repository.get_order_by_id(order_id, conn=conn)
    commissionable_base = Decimal(str(order["subtotal_amount"])) - Decimal(str(order["discount_amount"]))
    refunds = commerce_repository.list_refunds_for_order(order_id, conn=conn)
    created: list[dict[str, Any]] = []
    cumulative_before = Decimal("0")
    for refund in refunds:
        refund_id = str(refund["id"])
        existing = commerce_repository.get_reversal_for_refund(str(accrual["id"]), refund_id, conn=conn)
        refund_commissionable = Decimal(str(refund["commissionable_refund_amount"]))
        if existing is None:
            reversal_amount = compute_refund_reversal(
                accrual_amount=Decimal(str(accrual["amount"])),
                commissionable_base=commissionable_base,
                cumulative_refunded_before=cumulative_before,
                refund_commissionable_amount=refund_commissionable,
            )
            if reversal_amount != 0:
                created.append(
                    commerce_repository.insert_ledger_entry(
                        {
                            "creator_id": accrual["creator_id"],
                            "campaign_id": accrual["campaign_id"],
                            "order_id": order_id,
                            "attribution_id": accrual["attribution_id"],
                            "refund_id": refund_id,
                            "entry_type": "reversal",
                            "amount": reversal_amount,
                            "currency": accrual["currency"],
                            "fx_rate_usd": accrual["fx_rate_usd"],
                            "reverses_entry_id": str(accrual["id"]),
                            "commission_rate": None,
                            "memo": "Backfilled on confirm: refund predates accrual.",
                            "created_by_email": None,
                        },
                        conn=conn,
                    )
                )
        cumulative_before += refund_commissionable
    return created


def _cumulative_refunded_for_order(order_id: str, conn: Any) -> Decimal:
    refunds = commerce_repository.list_refunds_for_order(order_id, conn=conn)
    total = Decimal("0")
    for refund in refunds:
        total += Decimal(str(refund["commissionable_refund_amount"]))
    return total


def _resolve_commission_rate(attribution: dict[str, Any]) -> Decimal:
    if attribution.get("matched_discount_code_id"):
        row = commerce_repository.get_discount_code_by_id(str(attribution["matched_discount_code_id"]))
        if row is not None:
            return Decimal(str(row["commission_rate"]))
    if attribution.get("matched_utm_link_id"):
        row = commerce_repository.get_utm_link_by_id(str(attribution["matched_utm_link_id"]))
        if row is not None:
            return Decimal(str(row["commission_rate"]))
    return _default_manual_commission_rate()


def _resolve_commission_rate_for_creator(creator_id: str, conn: Any) -> Decimal:
    """Best-effort commission rate for a manually (re)assigned creator.

    Prefers the creator's own active discount code, then their active UTM
    link, so a reassign doesn't silently discount an already-contracted
    creator down to the generic manual default. Falls back to the manual
    default only when the creator has no active code or link on file.
    """
    code = commerce_repository.get_active_discount_code_for_creator(creator_id, conn=conn)
    if code is not None:
        return Decimal(str(code["commission_rate"]))
    link = commerce_repository.get_active_utm_link_for_creator(creator_id, conn=conn)
    if link is not None:
        return Decimal(str(link["commission_rate"]))
    return _default_manual_commission_rate()


def _default_manual_commission_rate() -> Decimal:
    return Decimal("0.10")


def _audit_resolution(
    order_id: str,
    attribution_id: str,
    payload: AttributionResolveRequest,
    user: UserContext,
) -> None:
    with connection() as conn:
        audit_events_repository.record_event(
            conn,
            event_type="order_attribution.resolved",
            aggregate_type="order_attribution",
            aggregate_id=attribution_id,
            actor_role=user.role,
            actor_email=user.email,
            payload=Jsonb(
                {
                    "order_id": order_id,
                    "action": payload.action,
                    "creator_id": payload.creator_id,
                    "notes": payload.notes,
                }
            ),
        )


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


@router.get("/ledger")
def get_ledger(
    creator_id: str | None = None,
    order_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager", "viewer")),
) -> dict[str, Any]:
    if database_enabled():
        items = commerce_repository.list_ledger(creator_id=creator_id, order_id=order_id, limit=limit)
    else:
        items = []
    return {"status": "ok", "items": items}


@router.get("/ledger/balances")
def get_ledger_balances(
    creator_id: str | None = None,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager", "viewer")),
) -> dict[str, Any]:
    if database_enabled():
        items = commerce_repository.creator_balances(creator_id=creator_id)
    else:
        items = []
    return {"status": "ok", "items": items}
