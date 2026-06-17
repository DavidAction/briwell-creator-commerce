from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.ai.dm import build_dm_drafts
from app.compliance.claims import ClaimsCheckInput, run_claims_check
from app.compliance.outreach_review import ClaimsCheckStatus
from app.compliance.outreach_review import OutreachReviewInput
from app.compliance.outreach_review import OutreachStatus
from app.compliance.outreach_review import ReviewDecision
from app.compliance.outreach_review import evaluate_outreach_review
from app.core.auth import UserContext, require_roles
from app.core.db import database_enabled
from app.core.policy import PolicyError, require_dm_allowed
from app.repositories import creators as creator_repository
from app.repositories import outreach as outreach_repository
from app.workflows.outreach_status import ClaimsCheckStatus as TransitionClaimsStatus
from app.workflows.outreach_status import OutreachStatus as TransitionOutreachStatus
from app.workflows.outreach_status import OutreachTransitionInput
from app.workflows.outreach_status import evaluate_outreach_transition


router = APIRouter(prefix="/outreach", tags=["outreach"])

Country = Literal["MX", "PE", "EC"]
ProductCategory = Literal[
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
]
DmVariant = Literal["soft_intro", "product_review", "ugc_collaboration", "commerce_collaboration"]


class CreatorSnapshot(BaseModel):
    country: Country
    username: str = Field(min_length=1)
    profile_url: str = Field(min_length=1)
    source_risk_level: str = Field(min_length=1)
    display_name: str | None = None
    bio: str | None = None
    follower_count: int | None = Field(default=None, ge=0)
    status: str = "active"
    do_not_contact: bool = False
    removal_requested_at: str | None = None


class GenerateDmRequest(BaseModel):
    campaign_id: str | None = None
    dm_variant: DmVariant = "soft_intro"
    product_category: ProductCategory
    product_name: str | None = None
    model_alias: str = "dm_draft"
    creator_snapshot: CreatorSnapshot | None = None


class ClaimsCheckRequest(BaseModel):
    outreach_id: str | None = None
    dm_message: str | None = Field(default=None, max_length=3000)
    product_category: ProductCategory
    product_name: str | None = None
    key_claims_allowed: list[str] = Field(default_factory=list, max_length=20)
    claims_disallowed: list[str] = Field(default_factory=list, max_length=20)
    country: Country | None = None
    strict_mode: bool = True
    persist_result: bool = True


class OutreachReviewDecisionRequest(BaseModel):
    outreach_id: str | None = None
    decision: ReviewDecision
    claims_check_status: ClaimsCheckStatus | None = None
    current_status: OutreachStatus = "dm_drafted"
    reviewer_notes: str | None = Field(default=None, max_length=2000)
    approver_user_id: UUID | None = None
    persist_result: bool = True


class OutreachStatusTransitionRequest(BaseModel):
    outreach_id: str | None = None
    current_status: TransitionOutreachStatus | None = None
    next_status: TransitionOutreachStatus
    claims_check_status: TransitionClaimsStatus | None = None
    do_not_contact_checked: bool = False
    manual_send_confirmed: bool = False
    response_summary: str | None = Field(default=None, max_length=2000)
    proposed_terms: dict[str, Any] = Field(default_factory=dict)
    operator_notes: str | None = Field(default=None, max_length=2000)
    persist_result: bool = True


@router.post("/claims-check")
def run_outreach_claims_check(
    payload: ClaimsCheckRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    dm_message = payload.dm_message
    outreach = None
    if database_enabled() and payload.outreach_id:
        outreach = outreach_repository.get_outreach(payload.outreach_id)
        if outreach is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "OUTREACH_NOT_FOUND",
                    "message": "Outreach record does not exist.",
                },
            )
        dm_message = dm_message or outreach.get("dm_message")

    if not dm_message:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "DM_MESSAGE_REQUIRED",
                "message": "Provide dm_message or a valid outreach_id in DB mode.",
            },
        )

    result = run_claims_check(
        ClaimsCheckInput(
            dm_message=dm_message,
            product_category=payload.product_category,
            product_name=payload.product_name,
            key_claims_allowed=payload.key_claims_allowed,
            claims_disallowed=payload.claims_disallowed,
            country=payload.country,
            strict_mode=payload.strict_mode,
        )
    )

    updated_outreach = None
    persistence_status = "validated_not_persisted"
    if database_enabled() and payload.outreach_id and payload.persist_result:
        updated_outreach = outreach_repository.update_claims_check_status(
            outreach_id=payload.outreach_id,
            claims_check_status=result.status,
            operator_notes=result.recommendation,
        )
        persistence_status = "persisted"

    return {
        "status": result.status,
        "persistence_status": persistence_status,
        "safe_to_send": result.safe_to_send,
        "human_review_required": result.human_review_required,
        "issues": [issue.model_dump() for issue in result.issues],
        "recommendation": result.recommendation,
        "normalized_message": result.normalized_message,
        "outreach": updated_outreach,
        "send_policy": {
            "send_allowed": result.status == "passed",
            "human_approval_required": True,
            "required_before_send": ["claims_check_passed", "human_approval"],
        },
    }


@router.post("/status-transition")
def record_outreach_status_transition(
    payload: OutreachStatusTransitionRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    outreach = None
    current_status = payload.current_status
    claims_check_status = payload.claims_check_status
    do_not_contact_checked = payload.do_not_contact_checked

    if database_enabled() and payload.outreach_id:
        outreach = outreach_repository.get_outreach(payload.outreach_id)
        if outreach is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "OUTREACH_NOT_FOUND",
                    "message": "Outreach record does not exist.",
                },
            )
        current_status = outreach["status"]
        claims_check_status = outreach["claims_check_status"]
        do_not_contact_checked = bool(outreach.get("do_not_contact_checked_at"))

    if current_status is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CURRENT_STATUS_REQUIRED",
                "message": "Provide current_status when USE_DATABASE=false.",
            },
        )
    if claims_check_status is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CLAIMS_CHECK_STATUS_REQUIRED",
                "message": "Provide claims_check_status when USE_DATABASE=false.",
            },
        )

    transition = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status=current_status,
            next_status=payload.next_status,
            claims_check_status=claims_check_status,
            do_not_contact_checked=do_not_contact_checked,
            manual_send_confirmed=payload.manual_send_confirmed,
            response_summary=payload.response_summary,
            proposed_terms=payload.proposed_terms,
        )
    )
    if not transition.allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": transition.reasons[0],
                "message": "Outreach status transition is not allowed.",
                "details": {
                    "current_status": current_status,
                    "next_status": payload.next_status,
                    "reasons": transition.reasons,
                },
            },
        )

    updated_outreach = None
    persistence_status = "validated_not_persisted"
    if database_enabled() and payload.outreach_id and payload.persist_result:
        updated_outreach = outreach_repository.update_status(
            outreach_id=payload.outreach_id,
            status=payload.next_status,
            response_summary=payload.response_summary,
            proposed_terms=payload.proposed_terms or None,
            operator_notes=payload.operator_notes,
        )
        persistence_status = "persisted"

    return {
        "status": "transition_recorded",
        "persistence_status": persistence_status,
        "current_status": current_status,
        "next_status": payload.next_status,
        "claims_check_status": claims_check_status,
        "outreach": updated_outreach or outreach,
        "send_policy": {
            "manual_send_confirmed": payload.manual_send_confirmed,
            "external_send_automated": transition.external_send_automated,
            "audit_required": transition.audit_required,
        },
    }


@router.post("/review-decision")
def record_outreach_review_decision(
    payload: OutreachReviewDecisionRequest,
    user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    claims_check_status = payload.claims_check_status
    current_status = payload.current_status
    outreach = None

    if database_enabled() and payload.outreach_id:
        outreach = outreach_repository.get_outreach(payload.outreach_id)
        if outreach is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "OUTREACH_NOT_FOUND",
                    "message": "Outreach record does not exist.",
                },
            )
        claims_check_status = outreach["claims_check_status"]
        current_status = outreach["status"]

    if claims_check_status is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CLAIMS_CHECK_STATUS_REQUIRED",
                "message": "Provide claims_check_status when USE_DATABASE=false.",
            },
        )

    review = evaluate_outreach_review(
        OutreachReviewInput(
            decision=payload.decision,
            claims_check_status=claims_check_status,
            current_status=current_status,
        )
    )
    if not review.can_record:
        raise HTTPException(
            status_code=400,
            detail={
                "code": review.reasons[0],
                "message": "Outreach review decision cannot be recorded.",
                "details": {
                    "decision": payload.decision,
                    "claims_check_status": claims_check_status,
                    "current_status": current_status,
                    "reasons": review.reasons,
                },
            },
        )

    updated_outreach = None
    persistence_status = "validated_not_persisted"
    if database_enabled() and payload.outreach_id and payload.persist_result:
        updated_outreach = outreach_repository.update_review_decision(
            outreach_id=payload.outreach_id,
            status=review.outreach_status,
            operator_notes=payload.reviewer_notes,
            approved_by_user_id=str(payload.approver_user_id)
            if payload.decision == "approve" and payload.approver_user_id
            else None,
        )
        persistence_status = "persisted"

    return {
        "status": "decision_recorded",
        "persistence_status": persistence_status,
        "decision": review.decision,
        "outreach_status": review.outreach_status,
        "claims_check_status": claims_check_status,
        "reviewer": {
            "role": user.role,
            "email": user.email,
        },
        "reviewer_notes": payload.reviewer_notes,
        "outreach": updated_outreach or outreach,
        "send_gate": {
            "ready_for_manual_send": review.ready_for_manual_send,
            "external_send_automated": review.external_send_automated,
            "required_before_send": review.required_before_send,
            "manual_send_only": True,
        },
    }


@router.post("/{creator_id}/generate-dm")
def generate_dm(
    creator_id: str,
    payload: GenerateDmRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    creator = _resolve_creator(creator_id, payload.creator_snapshot)

    try:
        require_dm_allowed(creator)
    except PolicyError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "DM_GENERATION_NOT_ALLOWED",
                "message": "This creator is not eligible for DM generation in MVP v0.1.",
                "details": {"reason": str(exc)},
            },
        ) from exc

    drafts = build_dm_drafts(
        creator=creator,
        product_category=payload.product_category,
        product_name=payload.product_name,
    )
    selected = next(
        (draft for draft in drafts if draft["variant"] == payload.dm_variant),
        drafts[0],
    )

    if database_enabled():
        outreach = outreach_repository.create_dm_draft(
            creator_id=creator_id,
            campaign_id=payload.campaign_id,
            dm_variant=selected["variant"],
            dm_message=selected["message"],
        )
        return {
            "status": "persisted",
            "outreach": outreach,
            "drafts": drafts,
            "claims_check_job": {
                "status": "queued",
                "job_type": "claims_check",
                "source_risk_level": creator["source_risk_level"],
            },
            "model_alias": payload.model_alias,
            "review_required": True,
            "review_required_reason": "operator_approval_required",
        }

    return {
        "status": "validated_not_persisted",
        "outreach": {
            "creator_id": creator_id,
            "campaign_id": payload.campaign_id,
            "status": "dm_drafted",
            "dm_variant": selected["variant"],
            "dm_message": selected["message"],
            "claims_check_status": "needs_review",
        },
        "drafts": drafts,
        "claims_check_job": {
            "status": "validated_not_persisted",
            "job_type": "claims_check",
            "source_risk_level": creator["source_risk_level"],
        },
        "model_alias": payload.model_alias,
        "review_required": True,
        "review_required_reason": "operator_approval_required",
    }


def _resolve_creator(
    creator_id: str,
    snapshot: CreatorSnapshot | None,
) -> dict[str, Any]:
    if database_enabled():
        creator = creator_repository.get_creator_by_id(creator_id)
        if creator is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "NOT_FOUND",
                    "message": "Creator not found.",
                    "details": {"creator_id": creator_id},
                },
            )
        return creator

    if snapshot is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CREATOR_SNAPSHOT_REQUIRED",
                "message": "Provide creator_snapshot when USE_DATABASE=false.",
            },
        )
    return snapshot.model_dump()
