from typing import Literal

from pydantic import BaseModel, Field


ReviewDecision = Literal["approve", "request_revision", "reject"]
ClaimsCheckStatus = Literal["not_checked", "passed", "failed", "needs_review"]
OutreachStatus = Literal[
    "discovered",
    "reviewing",
    "approved",
    "contact_found",
    "dm_drafted",
    "dm_sent",
    "replied",
    "negotiating",
    "accepted",
    "sample_sent",
    "content_posted",
    "completed",
    "rejected",
    "paused",
]


class OutreachReviewInput(BaseModel):
    decision: ReviewDecision
    claims_check_status: ClaimsCheckStatus
    current_status: OutreachStatus = "dm_drafted"


class OutreachReviewResult(BaseModel):
    decision: ReviewDecision
    can_record: bool
    outreach_status: OutreachStatus
    ready_for_manual_send: bool
    external_send_automated: bool = False
    reasons: list[str] = Field(default_factory=list)
    required_before_send: list[str] = Field(default_factory=list)


POST_SEND_STATUSES = {
    "dm_sent",
    "replied",
    "negotiating",
    "accepted",
    "sample_sent",
    "content_posted",
    "completed",
}

DECISION_STATUS_MAP: dict[ReviewDecision, OutreachStatus] = {
    "approve": "approved",
    "request_revision": "reviewing",
    "reject": "rejected",
}


def evaluate_outreach_review(payload: OutreachReviewInput) -> OutreachReviewResult:
    reasons: list[str] = []
    outreach_status = DECISION_STATUS_MAP[payload.decision]

    if payload.current_status in POST_SEND_STATUSES:
        reasons.append("OUTREACH_ALREADY_ADVANCED")

    if payload.current_status == "rejected" and payload.decision == "approve":
        reasons.append("REJECTED_OUTREACH_REQUIRES_NEW_DRAFT")

    if payload.decision == "approve" and payload.claims_check_status != "passed":
        reasons.append("CLAIMS_CHECK_NOT_PASSED")

    can_record = not reasons
    ready_for_manual_send = (
        can_record
        and payload.decision == "approve"
        and payload.claims_check_status == "passed"
    )
    required_before_send: list[str] = []
    if payload.claims_check_status != "passed":
        required_before_send.append("claims_check_passed")
    if payload.decision != "approve":
        required_before_send.append("human_approval")

    return OutreachReviewResult(
        decision=payload.decision,
        can_record=can_record,
        outreach_status=outreach_status,
        ready_for_manual_send=ready_for_manual_send,
        reasons=reasons,
        required_before_send=required_before_send,
    )
