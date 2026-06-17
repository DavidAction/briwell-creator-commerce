from app.ranking.campaign_candidates import priority_label, rank_candidate_rows


def test_priority_label_classifies_candidate_bands() -> None:
    assert priority_label(final_score=88, risk_penalty=4) == "priority_outreach"
    assert priority_label(final_score=74, risk_penalty=8) == "outreach_candidate"
    assert priority_label(final_score=64, risk_penalty=12) == "human_review"
    assert priority_label(final_score=52, risk_penalty=18) == "recheck_later"
    assert priority_label(final_score=49, risk_penalty=0) == "store_only"


def test_rank_candidate_rows_orders_by_score_risk_confidence_followers() -> None:
    rows = [
        {
            "creator_id": "creator-b",
            "final_score": 82,
            "risk_penalty": 7,
            "score_confidence": 0.91,
            "follower_count": 5000,
        },
        {
            "creator_id": "creator-c",
            "final_score": 82,
            "risk_penalty": 7,
            "score_confidence": 0.91,
            "follower_count": 9000,
        },
        {
            "creator_id": "creator-a",
            "final_score": 91,
            "risk_penalty": 4,
            "score_confidence": 0.75,
            "follower_count": 1000,
        },
        {
            "creator_id": "creator-d",
            "final_score": 82,
            "risk_penalty": 3,
            "score_confidence": 0.7,
            "follower_count": 12000,
        },
    ]

    ranked = rank_candidate_rows(rows)

    assert [row["creator_id"] for row in ranked] == [
        "creator-a",
        "creator-d",
        "creator-c",
        "creator-b",
    ]
    assert [row["rank"] for row in ranked] == [1, 2, 3, 4]
    assert ranked[0]["priority_label"] == "priority_outreach"
    assert ranked[1]["priority_label"] == "outreach_candidate"


def test_rank_candidate_rows_caps_limit() -> None:
    rows = [
        {
            "creator_id": f"creator-{index}",
            "final_score": index,
            "risk_penalty": 0,
            "score_confidence": 1,
            "follower_count": 0,
        }
        for index in range(120)
    ]

    assert len(rank_candidate_rows(rows, limit=999)) == 100
