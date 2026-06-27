from __future__ import annotations

from typing import Any
from uuid import UUID

from app.compliance.claims import ClaimsCheckInput, run_claims_check
from app.compliance.country_rules import CountryClaimsInput, evaluate_country_claims, list_country_rules
from app.core.config import settings
from app.core.db import database_enabled
from app.core.readiness import ReadinessSettings, evaluate_readiness
from app.operations.workflows import (
    apply_recent_screen_results,
    build_outreach_crm_board,
    build_outreach_plan,
    enrich_creator_profiles,
    evaluate_import_quality,
    match_campaign_candidates,
    rollup_performance,
)
from app.ai.contracts import AnalysisRequest
from app.repositories import creators as creator_repository
from app.repositories import operations as operations_repository
from app.repositories import videos as video_repository
from app.schemas.analysis import CommentAnalysisOutput, CreatorProfileAnalysisOutput
from app.workers.analysis_runner import AnalysisRunRequest, run_analysis
from app.workers.recent_posts_screening import RecentPostSnapshot, RecentPostsScreenRequest, run_recent_posts_screen
from app.workers.scoring_handoff import CreatorScoringHandoffRequest, run_creator_scoring_handoff


def run_acquisition_orchestration_workflow(
    payload: dict[str, Any],
    *,
    source_type: str,
    source_risk_level: str,
    user_email: str,
    user_role: str,
) -> dict[str, Any]:
    creator_inputs = list(payload["creator_candidates"])
    posts_by_input_key = {
        key: list(posts)
        for key, posts in (payload.get("recent_posts_by_creator") or {}).items()
    }
    quality_gate = evaluate_import_quality(
        creator_inputs,
        posts_by_input_key,
        expected_countries=[payload["country"]] if payload.get("country") else ["MX", "PE", "EC"],
    )
    persisted_import = _persist_acquisition_inputs(
        creators=creator_inputs,
        posts_by_creator=posts_by_input_key,
        source_type=source_type,
        source_risk_level=source_risk_level,
        persist_imports=bool(payload.get("persist_imports", True)),
    )
    resolved_creators = _resolve_creator_snapshots(creator_inputs, persisted_import)
    enrichment = enrich_creator_profiles(resolved_creators)
    enrichment_persistence = _persist_enrichment_if_possible(enrichment, source_risk_level)
    recent_screen = _run_recent_screen_batch(
        payload=payload,
        creators=resolved_creators,
        posts_by_creator=posts_by_input_key,
        source_risk_level=source_risk_level,
    )
    applied_recent = apply_recent_screen_results(recent_screen["apply_items"])
    screen_results_by_creator = {
        item["creator_id"]: item["screen_result"]
        for item in recent_screen["apply_items"]
        if item.get("creator_id") and item.get("screen_result")
    }
    analysis_by_creator = _run_full_analysis_batch(
        payload=payload,
        creators=resolved_creators,
        posts_by_creator=posts_by_input_key,
        screen_results_by_creator=screen_results_by_creator,
        source_risk_level=source_risk_level,
    )
    campaign_match = _build_campaign_match_section(
        payload=payload,
        creators=resolved_creators,
        screen_results_by_creator=screen_results_by_creator,
        analysis_by_creator=analysis_by_creator,
    )
    outreach_plan = (
        _build_outreach_section(payload, campaign_match["items"])
        if payload.get("build_outreach_plan", True)
        else {"status": "skipped", "items": [], "reason": "build_outreach_plan=false"}
    )
    crm_board = build_outreach_crm_board(outreach_plan.get("items", []))

    return {
        "status": "ok",
        "mode": "offline_ready_no_paid_provider_benchmark",
        "source": {
            "source_type": source_type,
            "source_risk_level": source_risk_level,
            "upload_name": payload.get("upload_name"),
        },
        "quality_gate": quality_gate,
        "import": persisted_import,
        "enrichment": {
            "items": enrichment,
            "persistence_status": enrichment_persistence["status"],
            "persisted_count": enrichment_persistence["count"],
        },
        "recent_20_batch": {
            **recent_screen,
            "applied_items": applied_recent,
            "queue_counts": _count_by(applied_recent, "queue"),
        },
        "full_analysis": _build_full_analysis_summary(analysis_by_creator),
        "analysis_pipeline": _build_analysis_pipeline_section(applied_recent, analysis_by_creator),
        "campaign_match": campaign_match,
        "outreach_plan": outreach_plan,
        "crm_board": crm_board,
        "performance": rollup_performance(
            payload.get("performance_snapshots") or [],
            spend_usd=payload.get("spend_usd"),
        ),
        "settlement": _build_settlement_section(outreach_plan.get("items", [])),
        "compliance": _build_compliance_section(payload, outreach_plan.get("items", [])),
        "production_readiness": _build_production_readiness_section(),
        "handoff_package": _build_handoff_package_section(),
        "next_actions": _orchestration_next_actions(
            quality_gate=quality_gate,
            recent_queue_counts=_count_by(applied_recent, "queue"),
            matched_count=len(campaign_match.get("items", [])),
        ),
        "operator": {"email": user_email, "role": user_role},
    }


def _persist_acquisition_inputs(
    creators: list[dict[str, Any]],
    posts_by_creator: dict[str, list[dict[str, Any]]],
    source_type: str,
    source_risk_level: str,
    persist_imports: bool,
) -> dict[str, Any]:
    if not database_enabled() or not persist_imports:
        return {
            "persistence_status": "validated_not_persisted",
            "creator_count": len(creators),
            "video_count": sum(len(posts) for posts in posts_by_creator.values()),
            "creator_id_by_input_key": {
                str(creator.get("creator_id") or creator.get("username")): str(
                    creator.get("creator_id") or creator.get("username")
                )
                for creator in creators
            },
            "creator_id_by_username": {
                str(creator.get("username")): str(creator.get("creator_id") or creator.get("username"))
                for creator in creators
            },
        }

    imported_creators = creator_repository.import_creators(
        source_type=source_type,
        source_risk_level=source_risk_level,
        items=[
            {
                "country": creator["country"],
                "username": creator["username"],
                "display_name": creator.get("display_name"),
                "profile_url": creator["profile_url"],
                "bio": creator.get("bio"),
                "language": creator.get("language", "es"),
                "follower_count": creator.get("follower_count"),
                "source_url": creator.get("source_url") or creator.get("profile_url"),
            }
            for creator in creators
        ],
    )
    db_id_by_username = {row["username"]: str(row["id"]) for row in imported_creators}
    db_id_by_input_key: dict[str, str] = {}
    imported_video_count = 0
    video_count_by_creator: dict[str, int] = {}
    for creator in creators:
        username = str(creator.get("username"))
        db_creator_id = db_id_by_username.get(username)
        if not db_creator_id:
            continue
        for key in (
            str(creator.get("creator_id") or ""),
            username,
            str(creator.get("profile_url") or ""),
            db_creator_id,
        ):
            if key:
                db_id_by_input_key[key] = db_creator_id
        posts = _posts_for_creator(creator, posts_by_creator, db_creator_id)
        if not posts:
            continue
        imported = video_repository.import_videos(
            creator_id=db_creator_id,
            source_type=source_type,
            source_risk_level=source_risk_level,
            items=[
                {
                    **post,
                    "url": post.get("url")
                    or f"https://www.tiktok.com/@{username}/video/{post.get('platform_video_id')}",
                    "source_url": post.get("source_url") or post.get("url"),
                }
                for post in posts
            ],
        )
        imported_video_count += len(imported)
        video_count_by_creator[db_creator_id] = len(imported)

    return {
        "persistence_status": "persisted",
        "creator_count": len(imported_creators),
        "video_count": imported_video_count,
        "creator_id_by_input_key": db_id_by_input_key,
        "creator_id_by_username": db_id_by_username,
        "video_count_by_creator": video_count_by_creator,
    }


def _resolve_creator_snapshots(
    creators: list[dict[str, Any]],
    persisted_import: dict[str, Any],
) -> list[dict[str, Any]]:
    by_username = persisted_import.get("creator_id_by_username") or {}
    by_input_key = persisted_import.get("creator_id_by_input_key") or {}
    resolved = []
    for creator in creators:
        username = str(creator.get("username") or "")
        input_key = str(creator.get("creator_id") or username)
        creator_id = by_input_key.get(input_key) or by_username.get(username) or creator.get("creator_id") or username
        resolved.append({**creator, "creator_id": str(creator_id)})
    return resolved


def _persist_enrichment_if_possible(
    enrichment: list[dict[str, Any]],
    source_risk_level: str,
) -> dict[str, Any]:
    if not database_enabled():
        return {"status": "validated_not_persisted", "count": 0}
    count = 0
    for item in enrichment:
        if not _is_uuidish(item.get("creator_id")):
            continue
        operations_repository.upsert_creator_profile_enrichment(item, source_risk_level=source_risk_level)
        count += 1
    return {"status": "persisted" if count else "validated_not_persisted", "count": count}


def _run_recent_screen_batch(
    payload: dict[str, Any],
    creators: list[dict[str, Any]],
    posts_by_creator: dict[str, list[dict[str, Any]]],
    source_risk_level: str,
) -> dict[str, Any]:
    if not payload.get("run_recent_20_screen", True):
        return {
            "status": "skipped",
            "screened_count": 0,
            "skipped": [{"reason": "run_recent_20_screen=false"}],
            "errors": [],
            "apply_items": [],
        }

    apply_items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for creator in creators[: int(payload.get("max_recent_screen_creators") or 50)]:
        posts = _posts_for_creator(creator, posts_by_creator, str(creator.get("creator_id") or ""))
        if not posts:
            skipped.append(
                {
                    "creator_id": creator.get("creator_id"),
                    "username": creator.get("username"),
                    "reason": "recent_posts_missing",
                }
            )
            continue
        try:
            result = run_recent_posts_screen(
                RecentPostsScreenRequest(
                    creator_id=str(creator.get("creator_id") or creator.get("username")),
                    source_risk_level=source_risk_level,
                    recent_posts=[
                        RecentPostSnapshot(**_recent_post_snapshot_payload(post))
                        for post in posts[:20]
                    ],
                    expected_post_count=20,
                    creator_snapshot=creator,
                    product_context={
                        "product_category": payload.get("product_category"),
                        "product_name": payload.get("product_name"),
                        "campaign_goal": payload.get("campaign_goal"),
                    },
                    dry_run=bool(payload.get("recent_screen_dry_run", True)),
                    allow_live_provider_calls=False
                    if payload.get("recent_screen_dry_run", True)
                    else settings.allow_live_provider_calls,
                    persist_result=(
                        database_enabled()
                        and bool(payload.get("persist_recent_screen_results", True))
                        and _is_uuidish(creator.get("creator_id"))
                    ),
                )
            )
        except Exception as exc:  # pragma: no cover - defensive API boundary.
            errors.append(
                {
                    "creator_id": creator.get("creator_id"),
                    "username": creator.get("username"),
                    "error": str(exc),
                }
            )
            continue
        if result.status != "success":
            errors.append(
                {
                    "creator_id": creator.get("creator_id"),
                    "username": creator.get("username"),
                    "error": result.result.error_code or result.result.review_required_reason or "screen_failed",
                }
            )
            continue
        apply_items.append(
            {
                "creator_id": str(creator.get("creator_id") or creator.get("username")),
                "creator_snapshot": creator,
                "screen_result": result.result.output,
            }
        )
    return {
        "status": "completed",
        "screened_count": len(apply_items),
        "skipped": skipped,
        "errors": errors,
        "apply_items": apply_items,
    }


def _build_campaign_match_section(
    payload: dict[str, Any],
    creators: list[dict[str, Any]],
    screen_results_by_creator: dict[str, dict[str, Any]],
    analysis_by_creator: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not payload.get("run_campaign_match", True):
        return {"status": "skipped", "items": [], "reason": "run_campaign_match=false"}

    match_ready_candidates = []
    score_source_counts: dict[str, int] = {}
    for creator in creators:
        creator_id = str(creator.get("creator_id") or creator.get("username"))
        screen = screen_results_by_creator.get(creator_id, {})
        analysis = analysis_by_creator.get(creator_id) or {}
        risk_notes = screen.get("risk_notes") or []

        # Prefer the SYSTEM-COMPUTED creator score from the full-analysis chain.
        # Operator-supplied final_score is only a fallback when no analysis ran.
        if analysis.get("final_score") is not None:
            score = analysis["final_score"]
            score_source = "system_analysis"
        elif creator.get("final_score") is not None:
            score = creator.get("final_score")
            score_source = "operator_supplied"
        elif screen.get("suitability_score") is not None:
            score = screen.get("suitability_score")
            score_source = "recent_screen_fallback"
        else:
            score = 0
            score_source = "unscored"

        if analysis.get("risk_penalty") is not None:
            risk_penalty = analysis["risk_penalty"]
        elif creator.get("risk_penalty") is not None:
            risk_penalty = creator.get("risk_penalty")
        else:
            risk_penalty = 12 if risk_notes else 3

        matched_products = (
            analysis.get("recommended_products")
            or creator.get("recommended_products")
            or screen.get("matched_product_categories")
            or []
        )
        segment = analysis.get("segment") or creator.get("segment") or "review_creator"
        score_source_counts[score_source] = score_source_counts.get(score_source, 0) + 1
        match_ready_candidates.append(
            {
                **creator,
                "creator_id": creator_id,
                "final_score": score or 0,
                "risk_penalty": risk_penalty,
                "recommended_products": matched_products,
                "segment": segment,
                "score_source": score_source,
            }
        )

    items = match_campaign_candidates(
        match_ready_candidates,
        product_category=payload["product_category"],
        country=payload.get("country"),
        recent_screen_results=screen_results_by_creator,
        min_score=float(payload.get("min_score", 70)),
        max_risk_penalty=float(payload.get("max_risk_penalty", 10)),
        limit=50,
    )
    return {
        "status": "matched",
        "campaign_id": payload.get("campaign_id"),
        "items": items,
        "summary": {
            "matched_count": len(items),
            "priority_outreach": sum(1 for item in items if item.get("priority_label") == "priority_outreach"),
            "human_review": sum(1 for item in items if item.get("priority_label") == "human_review"),
            "score_source_counts": score_source_counts,
        },
    }


def _build_outreach_section(
    payload: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    if not candidates:
        return {
            "status": "empty",
            "items": [],
            "send_policy": {
                "auto_send_enabled": False,
                "required_before_send": ["claims_check_passed", "human_approval", "manual_send_confirmed"],
            },
        }
    plan = build_outreach_plan(
        candidates,
        product_category=payload["product_category"],
        product_name=payload.get("product_name"),
        dm_variant=payload.get("dm_variant", "product_review"),
    )
    return {
        "status": "planned",
        "items": plan,
        "send_policy": {
            "auto_send_enabled": False,
            "required_before_send": ["claims_check_passed", "human_approval", "manual_send_confirmed"],
        },
    }


def _build_compliance_section(
    payload: dict[str, Any],
    outreach_items: list[dict[str, Any]],
) -> dict[str, Any]:
    checks = []
    for item in outreach_items:
        country = _creator_country(payload, item)
        dm_message = str(item.get("dm_message") or "")
        claim_check = run_claims_check(
            ClaimsCheckInput(
                dm_message=dm_message,
                product_category=payload["product_category"],
                product_name=payload.get("product_name"),
                country=country,
            )
        )
        country_check = evaluate_country_claims(
            CountryClaimsInput(
                country=country,
                product_category=payload["product_category"],
                message=dm_message,
            )
        )
        checks.append(
            {
                "creator_id": item.get("creator_id"),
                "username": item.get("username"),
                "country": country,
                "claims_check": claim_check.model_dump(),
                "country_claims_check": country_check.model_dump(),
            }
        )
    return {
        "status": "passed" if all(check["claims_check"]["status"] == "passed" for check in checks) else "needs_review",
        "checks": checks,
        "country_rules_loaded": {
            country: len(list_country_rules(country=country, product_category=payload["product_category"]))
            for country in ("MX", "PE", "EC")
        },
        "policy": {
            "auto_send_enabled": False,
            "legal_review_required_for_failed_or_review_claims": True,
        },
    }


def _build_analysis_pipeline_section(
    applied_recent: list[dict[str, Any]],
    analysis_by_creator: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    queues = []
    executed_count = 0
    for item in applied_recent:
        creator_id = item.get("creator_id")
        decision = item.get("suitability_decision")
        if decision == "pass_to_full_analysis":
            analysis = analysis_by_creator.get(str(creator_id)) or {}
            executed = analysis.get("final_score") is not None
            if executed:
                executed_count += 1
            queues.append(
                {
                    "creator_id": creator_id,
                    "queue": "full_analysis_queue",
                    "tasks": [
                        "profile_analysis",
                        "comment_analysis",
                        "multimodal_analysis",
                        "creator_score_handoff",
                        "final_review",
                    ],
                    "status": "executed" if executed else "pending",
                    "executed_tasks": analysis.get("executed_tasks", []),
                    "pending_tasks": ["multimodal_analysis", "final_review"] if executed else [],
                    "final_score": analysis.get("final_score"),
                    "segment": analysis.get("segment"),
                    "risk_penalty": analysis.get("risk_penalty"),
                    "score_confidence": analysis.get("score_confidence"),
                    "review_required_reason": analysis.get("review_required_reason"),
                    "mode": analysis.get("mode", "dry_run_default_live_ready"),
                }
            )
        elif decision == "human_review":
            queues.append({"creator_id": creator_id, "queue": "human_review_queue", "tasks": ["operator_review"]})
        elif decision == "avoid":
            queues.append({"creator_id": creator_id, "queue": "avoid_queue", "tasks": ["exclude_from_campaign"]})
        else:
            queues.append({"creator_id": creator_id, "queue": "recheck_later_queue", "tasks": ["backfill_recent_posts"]})
    return {
        "status": "executed" if executed_count else "planned",
        "executed_count": executed_count,
        "items": queues,
        "live_ai_ready": bool(settings.gemini_api_key) and settings.allow_live_provider_calls and not settings.ai_dry_run,
        "multimodal_requirements": [
            "video URL or frame samples",
            "caption and transcript when available",
            "public metrics",
            "brand-safety claim review",
        ],
    }


def _run_full_analysis_batch(
    payload: dict[str, Any],
    creators: list[dict[str, Any]],
    posts_by_creator: dict[str, list[dict[str, Any]]],
    screen_results_by_creator: dict[str, dict[str, Any]],
    source_risk_level: str,
) -> dict[str, dict[str, Any]]:
    """Run the post-screen full-analysis chain for creators that passed the recent-20
    screen: profile analysis (+ comment analysis when comments are supplied) feeding a
    deterministic creator-score handoff. This makes the campaign-match score
    SYSTEM-COMPUTED instead of operator-supplied. Runs in dry-run by default; the scoring
    is deterministic, so a real final_score is produced even without live AI calls.
    Multimodal and final-review remain operator/asset-gated downstream steps.
    """
    if not payload.get("run_full_analysis", True):
        return {}

    dry_run = bool(payload.get("analysis_dry_run", payload.get("recent_screen_dry_run", True)))
    allow_live = False if dry_run else settings.allow_live_provider_calls
    comments_by_creator = payload.get("comments_by_creator") or {}
    max_creators = int(payload.get("max_full_analysis_creators") or 50)
    persist_scores = bool(payload.get("persist_scores", True))
    results: dict[str, dict[str, Any]] = {}

    for creator in creators[:max_creators]:
        creator_id = str(creator.get("creator_id") or creator.get("username"))
        screen = screen_results_by_creator.get(creator_id, {})
        if screen.get("suitability_decision") != "pass_to_full_analysis":
            continue

        persist_log = database_enabled() and _is_uuidish(creator.get("creator_id"))
        executed_tasks: list[str] = []

        profile_run = run_analysis(
            AnalysisRunRequest(
                target_entity_type="creator",
                target_entity_id=creator_id,
                dry_run=dry_run,
                allow_live_provider_calls=allow_live,
                persist_log=persist_log,
                mark_job_status=False,
                request=AnalysisRequest(
                    task_type="profile_analysis",
                    model_alias="low_cost_text",
                    source_risk_level=source_risk_level,
                    prompt_version="profile_analysis_v0",
                    payload={"creator": creator},
                ),
            )
        )
        profile_output = (
            CreatorProfileAnalysisOutput.model_validate(profile_run.result.output)
            if profile_run.status == "success"
            else None
        )
        if profile_output is not None:
            executed_tasks.append("profile_analysis")

        comment_output = None
        comments = _comments_for_creator(creator, comments_by_creator)
        if comments:
            comment_run = run_analysis(
                AnalysisRunRequest(
                    target_entity_type="creator",
                    target_entity_id=creator_id,
                    dry_run=dry_run,
                    allow_live_provider_calls=allow_live,
                    persist_log=persist_log,
                    mark_job_status=False,
                    request=AnalysisRequest(
                        task_type="comment_analysis",
                        model_alias="low_cost_text",
                        source_risk_level=source_risk_level,
                        prompt_version="comment_analysis_v0",
                        payload={"comments": comments},
                    ),
                )
            )
            if comment_run.status == "success":
                comment_output = CommentAnalysisOutput.model_validate(comment_run.result.output)
                executed_tasks.append("comment_analysis")

        handoff = run_creator_scoring_handoff(
            CreatorScoringHandoffRequest(
                creator_id=creator_id,
                source_risk_level=source_risk_level,
                creator_snapshot=creator,
                video_metrics=_video_metrics_from_posts(
                    _posts_for_creator(creator, posts_by_creator, creator_id)
                ),
                profile_analysis=profile_output,
                comment_analysis=comment_output,
                final_review=None,
                persist_score=persist_scores and persist_log,
            )
        )

        if handoff.status == "scored" and handoff.score is not None:
            executed_tasks.append("creator_score_handoff")
            results[creator_id] = {
                "final_score": handoff.score.final_score,
                "risk_penalty": handoff.score.risk_penalty,
                "segment": handoff.score.segment,
                "recommended_products": list(handoff.score.recommended_products),
                "recommended_campaign_angle": handoff.score.recommended_campaign_angle,
                "score_confidence": handoff.score.score_confidence,
                "review_required_reason": handoff.score.review_required_reason,
                "score_source": "system_analysis",
                "executed_tasks": executed_tasks,
                "persisted_analysis_id": handoff.persisted_analysis_id,
                "persistence_status": handoff.persistence_status,
                "mode": "dry_run" if dry_run else "live",
            }
        else:
            results[creator_id] = {
                "status": "rejected",
                "review_notes": handoff.review_notes,
                "executed_tasks": executed_tasks,
                "mode": "dry_run" if dry_run else "live",
            }
    return results


def _build_full_analysis_summary(analysis_by_creator: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scored = [item for item in analysis_by_creator.values() if item.get("final_score") is not None]
    return {
        "status": "executed" if analysis_by_creator else "skipped",
        "scored_count": len(scored),
        "rejected_count": len(analysis_by_creator) - len(scored),
        "score_source": "system_analysis",
        "note": (
            "final_score is computed by the profile(+comment) -> deterministic creator-score chain, "
            "not taken from operator input. Add multimodal asset review and final review for full confirmation."
        ),
        "results": analysis_by_creator,
    }


def _comments_for_creator(
    creator: dict[str, Any],
    comments_by_creator: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    for key in (str(creator.get("creator_id") or ""), str(creator.get("username") or "")):
        if key and key in comments_by_creator:
            return comments_by_creator[key]
    return []


def _video_metrics_from_posts(posts: list[dict[str, Any]]) -> dict[str, Any]:
    if not posts:
        return {}
    views = [int(post.get("view_count") or 0) for post in posts if post.get("view_count") is not None]
    metrics: dict[str, Any] = {}
    if views:
        metrics["avg_view_count"] = round(sum(views) / len(views), 2)
    engagement_rates: list[float] = []
    for post in posts:
        view_count = post.get("view_count")
        if not view_count:
            continue
        interactions = sum(
            int(post.get(field) or 0)
            for field in ("like_count", "comment_count", "share_count", "save_count")
        )
        engagement_rates.append(interactions / int(view_count))
    if engagement_rates:
        metrics["engagement_rate"] = round(sum(engagement_rates) / len(engagement_rates), 4)
    return metrics


def _build_settlement_section(outreach_items: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for item in outreach_items:
        terms = item.get("offer_terms") or {}
        items.append(
            {
                "creator_id": item.get("creator_id"),
                "username": item.get("username"),
                "contract_status": "draft_required",
                "payout_status": "pending_contract",
                "deliverables": terms.get("deliverables") or ["1 short-form video"],
                "fee_usd": terms.get("fee_usd"),
                "required_before_payout": [
                    "accepted_contract",
                    "content_delivered",
                    "post_url_registered",
                    "invoice_or_receipt_uploaded",
                    "tax_document_if_required",
                ],
            }
        )
    return {
        "status": "planned",
        "items": items,
        "payout_policy": {
            "no_payment_without_deliverable": True,
            "invoice_required_before_approval": True,
            "tax_document_required_before_paid": True,
        },
    }


def _build_production_readiness_section() -> dict[str, Any]:
    readiness = evaluate_readiness(
        ReadinessSettings(
            app_env=settings.app_env,
            database_url=settings.database_url,
            use_database=settings.use_database,
            gemini_api_key=settings.gemini_api_key,
            ai_dry_run=settings.ai_dry_run,
            allow_live_provider_calls=settings.allow_live_provider_calls,
            auth_provider=settings.auth_provider,
            oidc_issuer_url=settings.oidc_issuer_url,
            oidc_audience=settings.oidc_audience,
            oidc_jwks_url=settings.oidc_jwks_url,
            oidc_role_claim=settings.oidc_role_claim,
            cors_allowed_origins=settings.cors_allowed_origins,
            managed_secret_provider=settings.managed_secret_provider,
            backup_restore_tested_at=settings.backup_restore_tested_at,
            rate_limit_enabled=settings.rate_limit_enabled,
        )
    )
    return {
        **readiness,
        "recommended_order": [
            "Move DB to managed PostgreSQL",
            "Enable OIDC auth and role claims",
            "Move secrets to deployment secret manager",
            "Enable automatic backups and restore test",
            "Enable rate limits, logs, Sentry, and cost alerts",
        ],
    }


def _build_handoff_package_section() -> dict[str, Any]:
    return {
        "status": "ready",
        "github_repository": "https://github.com/DavidAction/briwell-creator-commerce",
        "local_entrypoints": [
            "work/briwell_mvp_app/README.md",
            "work/briwell_dashboard_app/README.md",
            "work/briwell_mvp_app/.env.example",
            "work/briwell_mvp_app/render.yaml",
        ],
        "verification_commands": [
            "cd work/briwell_mvp_app && .venv\\Scripts\\python.exe -m pytest -q",
            "cd work/briwell_dashboard_app && node tests\\smoke.mjs",
            "cd work/briwell_mvp_app && .venv\\Scripts\\python.exe scripts\\validate_csv_imports.py",
        ],
    }


def _orchestration_next_actions(
    quality_gate: dict[str, Any],
    recent_queue_counts: dict[str, int],
    matched_count: int,
) -> list[str]:
    actions = []
    if quality_gate.get("overall_status") != "ready":
        actions.append("Fix import blockers or review warnings before outreach.")
    if recent_queue_counts.get("human_review_queue"):
        actions.append("Review recent-20 borderline or risk cases before campaign matching.")
    if recent_queue_counts.get("full_analysis_queue"):
        actions.append(
            "Profile and creator-score analysis ran automatically; add multimodal asset review "
            "and final review for pass candidates."
        )
    if matched_count:
        actions.append("Run claims check, approve DM drafts, then manually send outreach.")
    else:
        actions.append("Load more qualified recent-20 data or lower test min_score for local validation.")
    actions.append("After Apify balance is topped up, rerun provider benchmark with identical keywords.")
    return actions


def _posts_for_creator(
    creator: dict[str, Any],
    posts_by_creator: dict[str, list[dict[str, Any]]],
    resolved_creator_id: str,
) -> list[dict[str, Any]]:
    keys = [
        str(creator.get("creator_id") or ""),
        str(creator.get("username") or ""),
        str(creator.get("profile_url") or ""),
        str(resolved_creator_id or ""),
    ]
    for key in keys:
        if key and key in posts_by_creator:
            return posts_by_creator[key]
    return []


def _recent_post_snapshot_payload(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "video_id": post.get("platform_video_id") or post.get("video_id"),
        "url": post.get("url"),
        "caption": post.get("caption"),
        "transcript": post.get("transcript"),
        "hashtags": post.get("hashtags") or [],
        "view_count": post.get("view_count"),
        "like_count": post.get("like_count"),
        "comment_count": post.get("comment_count"),
        "share_count": post.get("share_count"),
    }


def _creator_country(payload: dict[str, Any], item: dict[str, Any]) -> str:
    candidate_country = item.get("country") or payload.get("country") or "MX"
    return candidate_country if candidate_country in {"MX", "PE", "EC"} else "MX"


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _is_uuidish(value: Any) -> bool:
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False
