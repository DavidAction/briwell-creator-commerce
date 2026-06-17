from app.workflows.outreach_status import OutreachTransitionInput
from app.workflows.outreach_status import evaluate_outreach_transition


def test_outreach_transition_allows_manual_send_after_approval() -> None:
    result = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status="approved",
            next_status="dm_sent",
            claims_check_status="passed",
            do_not_contact_checked=True,
            manual_send_confirmed=True,
        )
    )

    assert result.allowed is True
    assert result.external_send_automated is False
    assert result.audit_required is True


def test_outreach_transition_blocks_dm_sent_without_manual_confirmation() -> None:
    result = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status="approved",
            next_status="dm_sent",
            claims_check_status="passed",
            do_not_contact_checked=True,
            manual_send_confirmed=False,
        )
    )

    assert result.allowed is False
    assert "MANUAL_SEND_CONFIRMATION_REQUIRED" in result.reasons


def test_outreach_transition_blocks_dm_sent_without_claims_check() -> None:
    result = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status="approved",
            next_status="dm_sent",
            claims_check_status="needs_review",
            do_not_contact_checked=True,
            manual_send_confirmed=True,
        )
    )

    assert result.allowed is False
    assert "CLAIMS_CHECK_REQUIRED_BEFORE_DM_SENT" in result.reasons


def test_outreach_transition_requires_response_summary_for_reply() -> None:
    result = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status="dm_sent",
            next_status="replied",
            claims_check_status="passed",
        )
    )

    assert result.allowed is False
    assert "RESPONSE_SUMMARY_REQUIRED" in result.reasons


def test_outreach_transition_requires_terms_for_acceptance() -> None:
    result = evaluate_outreach_transition(
        OutreachTransitionInput(
            current_status="negotiating",
            next_status="accepted",
            claims_check_status="passed",
            response_summary="Creator agreed in principle.",
        )
    )

    assert result.allowed is False
    assert "PROPOSED_TERMS_REQUIRED" in result.reasons
