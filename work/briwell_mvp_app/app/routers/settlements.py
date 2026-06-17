from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.repositories import settlements as settlement_repository


router = APIRouter(prefix="/settlements", tags=["settlements"])

ContractStatus = Literal["draft", "sent", "accepted", "cancelled", "completed"]
PayoutStatus = Literal["pending", "approved", "paid", "blocked", "cancelled"]
PayoutMethod = Literal["bank_transfer", "paypal", "payoneer", "mercado_pago", "other"]


class ContractCreateRequest(BaseModel):
    outreach_id: str | None = None
    creator_id: str | None = None
    campaign_id: str | None = None
    deliverables: dict[str, Any] = Field(default_factory=dict)
    compensation_terms: dict[str, Any] = Field(default_factory=dict)
    due_date: date | None = None
    status: ContractStatus = "draft"
    contract_url: str | None = Field(default=None, max_length=2000)
    operator_notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_creator_or_outreach(self) -> "ContractCreateRequest":
        if not self.creator_id and not self.outreach_id:
            raise ValueError("creator_id or outreach_id is required.")
        return self


class PayoutCreateRequest(BaseModel):
    contract_id: str | None = None
    creator_id: str | None = None
    campaign_id: str | None = None
    amount_usd: float = Field(ge=0)
    payout_status: PayoutStatus = "pending"
    payout_method: PayoutMethod | None = None
    invoice_url: str | None = Field(default=None, max_length=2000)
    tax_document_url: str | None = Field(default=None, max_length=2000)
    blocker_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_blocked_reason(self) -> "PayoutCreateRequest":
        if self.payout_status == "blocked" and not self.blocker_reason:
            raise ValueError("blocker_reason is required when payout_status=blocked.")
        if self.payout_status in {"approved", "paid"} and not self.invoice_url:
            raise ValueError("invoice_url is required before payout approval or payment.")
        return self


@router.post("/contracts")
def create_contract(
    payload: ContractCreateRequest,
    _user: UserContext = Depends(require_roles("admin", "campaign_manager")),
) -> dict[str, Any]:
    normalized = payload.model_dump()
    if database_enabled():
        created = settlement_repository.create_contract(normalized)
        return {
            "status": "persisted",
            "contract": created,
        }

    return {
        "status": "validated_not_persisted",
        "contract": normalized,
    }


@router.post("/payouts")
def create_payout(
    payload: PayoutCreateRequest,
    _user: UserContext = Depends(require_roles("admin", "campaign_manager")),
) -> dict[str, Any]:
    normalized = payload.model_dump()
    if payload.payout_status == "paid" and not payload.tax_document_url:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TAX_DOCUMENT_REQUIRED",
                "message": "tax_document_url is required before marking a payout as paid.",
            },
        )

    if database_enabled():
        created = settlement_repository.create_payout(normalized)
        return {
            "status": "persisted",
            "payout": created,
        }

    return {
        "status": "validated_not_persisted",
        "payout": normalized,
    }
