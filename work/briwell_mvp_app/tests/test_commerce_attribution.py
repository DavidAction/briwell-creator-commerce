from app.commerce.attribution import CodeMatch, UtmMatch, decide_attribution


def test_single_code_no_utm_is_high_confidence_active() -> None:
    decision = decide_attribution(
        code_matches=[CodeMatch(id="code-1", creator_id="creator-a", commission_rate="0.15")],
        utm_match=None,
    )
    assert decision.creator_id == "creator-a"
    assert decision.method == "discount_code"
    assert decision.confidence == "high"
    assert decision.status == "active"
    assert decision.should_accrue is True
    assert decision.conflict_kind is None


def test_single_code_matching_utm_creator_still_high_confidence() -> None:
    decision = decide_attribution(
        code_matches=[CodeMatch(id="code-1", creator_id="creator-a", commission_rate="0.15")],
        utm_match=UtmMatch(id="utm-1", creator_id="creator-a", commission_rate="0.10"),
    )
    assert decision.creator_id == "creator-a"
    assert decision.method == "discount_code"
    assert decision.confidence == "high"
    assert decision.status == "active"
    assert decision.should_accrue is True


def test_utm_only_is_medium_confidence_active() -> None:
    decision = decide_attribution(
        code_matches=[],
        utm_match=UtmMatch(id="utm-1", creator_id="creator-b", commission_rate="0.10"),
    )
    assert decision.creator_id == "creator-b"
    assert decision.method == "utm_link"
    assert decision.confidence == "medium"
    assert decision.status == "active"
    assert decision.should_accrue is True


def test_code_vs_different_utm_creator_is_conflict_needs_review() -> None:
    decision = decide_attribution(
        code_matches=[CodeMatch(id="code-1", creator_id="creator-a", commission_rate="0.15")],
        utm_match=UtmMatch(id="utm-1", creator_id="creator-b", commission_rate="0.10"),
    )
    assert decision.creator_id == "creator-a"
    assert decision.method == "discount_code"
    assert decision.confidence == "medium"
    assert decision.status == "needs_review"
    assert decision.conflict_kind == "code_vs_utm"
    assert decision.competing_creator_id == "creator-b"
    assert decision.should_accrue is False


def test_multi_code_different_creators_is_low_confidence_needs_review() -> None:
    decision = decide_attribution(
        code_matches=[
            CodeMatch(id="code-1", creator_id="creator-a", commission_rate="0.15"),
            CodeMatch(id="code-2", creator_id="creator-b", commission_rate="0.12"),
        ],
        utm_match=None,
    )
    assert decision.creator_id == "creator-a"
    assert decision.method == "discount_code"
    assert decision.confidence == "low"
    assert decision.status == "needs_review"
    assert decision.conflict_kind == "multi_code"
    assert decision.should_accrue is False


def test_multi_code_same_creator_is_high_confidence_active() -> None:
    decision = decide_attribution(
        code_matches=[
            CodeMatch(id="code-1", creator_id="creator-a", commission_rate="0.15"),
            CodeMatch(id="code-2", creator_id="creator-a", commission_rate="0.15"),
        ],
        utm_match=None,
    )
    assert decision.creator_id == "creator-a"
    assert decision.method == "discount_code"
    assert decision.confidence == "high"
    assert decision.status == "active"
    assert decision.should_accrue is True
    assert decision.conflict_kind is None


def test_no_match_at_all_returns_no_attribution() -> None:
    decision = decide_attribution(code_matches=[], utm_match=None)
    assert decision.creator_id is None
    assert decision.method is None
    assert decision.should_accrue is False
