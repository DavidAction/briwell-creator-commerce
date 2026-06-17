from app.compliance.outreach_review import OutreachReviewInput
from app.compliance.outreach_review import evaluate_outreach_review


def test_review_approval_passes_only_after_claims_check_passed() -> None:
    result = evaluate_outreach_review(
        OutreachReviewInput(
            decision="approve",
            claims_check_status="passed",
            current_status="dm_drafted",
        )
    )

    assert result.can_record is True
    assert result.outreach_status == "approved"
    assert result.ready_for_manual_send is True
    assert result.external_send_automated is False


def test_review_approval_blocks_failed_claims_check() -> None:
    result = evaluate_outreach_review(
        OutreachReviewInput(
            decision="approve",
            claims_check_status="failed",
            current_status="dm_drafted",
        )
    )

    assert result.can_record is False
    assert result.ready_for_manual_send is False
    assert "CLAIMS_CHECK_NOT_PASSED" in result.reasons
    assert "claims_check_passed" in result.required_before_send


def test_review_revision_request_keeps_outreach_in_review() -> None:
    result = evaluate_outreach_review(
        OutreachReviewInput(
            decision="request_revision",
            claims_check_status="needs_review",
            current_status="dm_drafted",
        )
    )

    assert result.can_record is True
    assert result.outreach_status == "reviewing"
    assert result.ready_for_manual_send is False


def test_review_blocks_post_send_status_changes() -> None:
    result = evaluate_outreach_review(
        OutreachReviewInput(
            decision="reject",
            claims_check_status="passed",
            current_status="dm_sent",
        )
    )

    assert result.can_record is False
    assert "OUTREACH_ALREADY_ADVANCED" in result.reasons
