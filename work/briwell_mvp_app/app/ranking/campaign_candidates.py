from typing import Any, Literal


CampaignCandidatePriority = Literal[
    "priority_outreach",
    "outreach_candidate",
    "human_review",
    "recheck_later",
    "store_only",
]


def priority_label(final_score: float, risk_penalty: float) -> CampaignCandidatePriority:
    if final_score >= 85 and risk_penalty <= 5:
        return "priority_outreach"
    if final_score >= 70 and risk_penalty <= 10:
        return "outreach_candidate"
    if final_score >= 60 and risk_penalty <= 15:
        return "human_review"
    if final_score >= 50 and risk_penalty <= 20:
        return "recheck_later"
    return "store_only"


def rank_candidate_rows(
    rows: list[dict[str, Any]],
    limit: int = 50,
) -> list[dict[str, Any]]:
    normalized_limit = max(1, min(limit, 100))
    ranked = sorted(
        rows,
        key=lambda row: (
            -float(row.get("final_score") or 0),
            float(row.get("risk_penalty") or 0),
            -float(row.get("score_confidence") or 0),
            -int(row.get("follower_count") or 0),
        ),
    )
    return [
        {
            **row,
            "priority_label": priority_label(
                final_score=float(row.get("final_score") or 0),
                risk_penalty=float(row.get("risk_penalty") or 0),
            ),
            "rank": index + 1,
        }
        for index, row in enumerate(ranked[:normalized_limit])
    ]
