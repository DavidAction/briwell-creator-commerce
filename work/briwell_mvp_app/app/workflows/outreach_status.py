from typing import Literal

from pydantic import BaseModel, Field


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

ClaimsCheckStatus = Literal["not_checked", "passed", "failed", "needs_review"]


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "discovered": {"contact_found", "reviewing", "rejected", "paused"},
    "contact_found": {"dm_drafted", "rejected", "paused"},
    "dm_drafted": {"reviewing", "approved", "rejected", "paused"},
    "reviewing": {"dm_drafted", "approved", "rejected", "paused"},
    "approved": {"dm_sent", "rejected", "paused"},
    "dm_sent": {"replied", "negotiating", "rejected", "paused"},
    "replied": {"negotiating", "accepted", "rejected", "paused"},
    "negotiating": {"accepted", "rejected", "paused"},
    "accepted": {"sample_sent", "rejected", "paused"},
    "sample_sent": {"content_posted", "rejected", "paused"},
    "content_posted": {"completed", "paused"},
    "completed": set(),
    "rejected": set(),
    "paused": {"reviewing", "approved", "dm_sent", "rejected"},
}


class OutreachTransitionInput(BaseModel):
    current_status: OutreachStatus
    next_status: OutreachStatus
    claims_check_status: ClaimsCheckStatus = "not_checked"
    do_not_contact_checked: bool = False
    manual_send_confirmed: bool = False
    response_summary: str | None = Field(default=None, max_length=2000)
    proposed_terms: dict[str, object] = Field(default_factory=dict)


class OutreachTransitionResult(BaseModel):
    allowed: bool
    current_status: OutreachStatus
    next_status: OutreachStatus
    reasons: list[str] = Field(default_factory=list)
    external_send_automated: bool = False
    audit_required: bool = True


def evaluate_outreach_transition(payload: OutreachTransitionInput) -> OutreachTransitionResult:
    reasons: list[str] = []

    if payload.next_status not in ALLOWED_TRANSITIONS[payload.current_status]:
        reasons.append("OUTREACH_STATUS_TRANSITION_NOT_ALLOWED")

    if payload.next_status == "dm_sent":
        if payload.current_status != "approved":
            reasons.append("OUTREACH_MUST_BE_APPROVED_BEFORE_DM_SENT")
        if payload.claims_check_status != "passed":
            reasons.append("CLAIMS_CHECK_REQUIRED_BEFORE_DM_SENT")
        if not payload.do_not_contact_checked:
            reasons.append("DO_NOT_CONTACT_CHECK_REQUIRED_BEFORE_DM_SENT")
        if not payload.manual_send_confirmed:
            reasons.append("MANUAL_SEND_CONFIRMATION_REQUIRED")

    if payload.next_status in {"replied", "negotiating"} and not payload.response_summary:
        reasons.append("RESPONSE_SUMMARY_REQUIRED")

    if payload.next_status == "accepted" and not payload.proposed_terms:
        reasons.append("PROPOSED_TERMS_REQUIRED")

    return OutreachTransitionResult(
        allowed=not reasons,
        current_status=payload.current_status,
        next_status=payload.next_status,
        reasons=reasons,
    )
