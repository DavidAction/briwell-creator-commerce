from typing import Any

from psycopg.types.json import Jsonb

from app.core.db import fetch_all, fetch_one


def list_creator_analyses(creator_id: str, limit: int = 20) -> list[dict[str, Any]]:
    query = """
        SELECT
          id,
          creator_id,
          analysis_version,
          beauty_fit_score,
          engagement_quality_score,
          audience_locality_score,
          commerce_intent_score,
          content_quality_score,
          collaboration_probability_score,
          cost_efficiency_score,
          risk_score,
          risk_penalty,
          final_score,
          segment,
          recommended_products,
          recommended_campaign_angle,
          ai_summary,
          ai_evidence,
          score_confidence,
          review_required_reason,
          created_at
        FROM creator_analysis
        WHERE creator_id = %(creator_id)s
        ORDER BY created_at DESC
        LIMIT %(limit)s
    """
    return fetch_all(query, {"creator_id": creator_id, "limit": min(limit, 100)})


def upsert_creator_analysis(
    creator_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    query = """
        INSERT INTO creator_analysis (
          creator_id,
          analysis_version,
          beauty_fit_score,
          engagement_quality_score,
          audience_locality_score,
          commerce_intent_score,
          content_quality_score,
          collaboration_probability_score,
          cost_efficiency_score,
          risk_score,
          risk_penalty,
          final_score,
          segment,
          recommended_products,
          recommended_campaign_angle,
          ai_summary,
          ai_evidence,
          score_confidence,
          review_required_reason
        ) VALUES (
          %(creator_id)s,
          %(analysis_version)s,
          %(beauty_fit_score)s,
          %(engagement_quality_score)s,
          %(audience_locality_score)s,
          %(commerce_intent_score)s,
          %(content_quality_score)s,
          %(collaboration_probability_score)s,
          %(cost_efficiency_score)s,
          %(risk_score)s,
          %(risk_penalty)s,
          %(final_score)s,
          %(segment)s,
          %(recommended_products)s,
          %(recommended_campaign_angle)s,
          %(ai_summary)s,
          %(ai_evidence)s,
          %(score_confidence)s,
          %(review_required_reason)s
        )
        ON CONFLICT (creator_id, analysis_version)
        DO UPDATE SET
          beauty_fit_score = EXCLUDED.beauty_fit_score,
          engagement_quality_score = EXCLUDED.engagement_quality_score,
          audience_locality_score = EXCLUDED.audience_locality_score,
          commerce_intent_score = EXCLUDED.commerce_intent_score,
          content_quality_score = EXCLUDED.content_quality_score,
          collaboration_probability_score = EXCLUDED.collaboration_probability_score,
          cost_efficiency_score = EXCLUDED.cost_efficiency_score,
          risk_score = EXCLUDED.risk_score,
          risk_penalty = EXCLUDED.risk_penalty,
          final_score = EXCLUDED.final_score,
          segment = EXCLUDED.segment,
          recommended_products = EXCLUDED.recommended_products,
          recommended_campaign_angle = EXCLUDED.recommended_campaign_angle,
          ai_summary = EXCLUDED.ai_summary,
          ai_evidence = EXCLUDED.ai_evidence,
          score_confidence = EXCLUDED.score_confidence,
          review_required_reason = EXCLUDED.review_required_reason
        RETURNING
          id,
          creator_id,
          analysis_version,
          beauty_fit_score,
          engagement_quality_score,
          audience_locality_score,
          commerce_intent_score,
          content_quality_score,
          collaboration_probability_score,
          cost_efficiency_score,
          risk_score,
          risk_penalty,
          final_score,
          segment,
          recommended_products,
          recommended_campaign_angle,
          ai_summary,
          ai_evidence,
          score_confidence,
          review_required_reason,
          created_at
    """
    row = {
        **payload,
        "creator_id": creator_id,
        "ai_evidence": Jsonb(payload.get("ai_evidence", [])),
    }
    created = fetch_one(query, row)
    if created is None:
        raise RuntimeError("Creator analysis upsert did not return a row.")
    return created
