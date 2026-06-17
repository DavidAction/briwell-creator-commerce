from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.ai.dm import build_dm_drafts
from app.ranking.campaign_candidates import priority_label


COUNTRIES = {"MX", "PE", "EC"}
PRODUCT_TERMS = {
    "sunscreen": ("spf", "protector", "bloqueador", "solar"),
    "calming_serum": ("serum", "calmante", "barrera", "rojeces"),
    "cleanser": ("limpiador", "limpieza", "cleanser"),
    "sheet_mask": ("mascarilla", "mask"),
    "cushion_foundation": ("cushion", "base", "maquillaje"),
}
OUTREACH_FUNNEL_ORDER = [
    "discovered",
    "dm_drafted",
    "reviewing",
    "approved",
    "dm_sent",
    "replied",
    "negotiating",
    "accepted",
    "posted",
    "completed",
    "rejected",
    "paused",
]


def evaluate_import_quality(
    creators: list[dict[str, Any]],
    recent_posts_by_creator: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    recent_posts_by_creator = recent_posts_by_creator or {}
    blockers: list[str] = []
    warnings: list[str] = []
    seen_usernames: set[str] = set()
    seen_profiles: set[str] = set()
    invalid_creator_keys: set[str] = set()

    for index, creator in enumerate(creators, start=1):
        row_label = f"@{creator.get('username')}" if creator.get("username") else f"row {index}"
        creator_key = str(creator.get("creator_id") or creator.get("username") or index)
        username = str(creator.get("username") or "").strip().lower()
        profile_url = str(creator.get("profile_url") or "").strip().lower()
        country = creator.get("country")
        risk = creator.get("source_risk_level")

        if not username:
            blockers.append(f"{row_label}: username required")
            invalid_creator_keys.add(creator_key)
        if not profile_url:
            blockers.append(f"{row_label}: profile_url required")
            invalid_creator_keys.add(creator_key)
        if country not in COUNTRIES:
            blockers.append(f"{row_label}: country must be MX, PE, or EC")
            invalid_creator_keys.add(creator_key)
        if risk not in {"low", "low_medium", "medium"}:
            blockers.append(f"{row_label}: source_risk_level must be low, low_medium, or medium")
            invalid_creator_keys.add(creator_key)
        if username and username in seen_usernames:
            blockers.append(f"{row_label}: duplicate username")
            invalid_creator_keys.add(creator_key)
        if profile_url and profile_url in seen_profiles:
            blockers.append(f"{row_label}: duplicate profile_url")
            invalid_creator_keys.add(creator_key)
        seen_usernames.add(username)
        seen_profiles.add(profile_url)

        if creator.get("follower_count") in {None, ""}:
            warnings.append(f"{row_label}: follower_count missing")
        if creator.get("avg_views") in {None, ""}:
            warnings.append(f"{row_label}: avg_views missing")

    country_counts = {
        country: sum(1 for creator in creators if creator.get("country") == country)
        for country in sorted(COUNTRIES)
    }
    for country, count in country_counts.items():
        if count == 0:
            warnings.append(f"{country}: no creator candidate loaded")

    post_blockers: list[str] = []
    post_warnings: list[str] = []
    loaded_posts = 0
    required_posts = len(creators) * 20
    readiness: list[dict[str, Any]] = []
    for creator in creators:
        creator_id = str(creator.get("creator_id") or "")
        username = creator.get("username") or creator_id or "creator"
        posts = recent_posts_by_creator.get(creator_id) or recent_posts_by_creator.get(str(username)) or []
        post_count = min(len(posts), 20)
        loaded_posts += post_count
        readiness.append(
            {
                "creator_id": creator_id,
                "username": username,
                "post_count": post_count,
                "status": "ready" if post_count >= 20 else "needs_posts" if post_count else "missing",
            }
        )
        if post_count == 0:
            post_blockers.append(f"@{username}: recent 20 posts missing")
        elif post_count < 20:
            post_blockers.append(f"@{username}: {post_count}/20 recent posts loaded")

        duplicate_urls = _duplicates([str(post.get("url") or "") for post in posts])
        for url in duplicate_urls:
            post_blockers.append(f"@{username}: duplicate post URL {url}")
        missing_url = sum(1 for post in posts if not post.get("url"))
        missing_metrics = sum(
            1
            for post in posts
            if not any(post.get(key) is not None for key in ("view_count", "like_count", "comment_count"))
        )
        missing_transcripts = sum(1 for post in posts if not post.get("transcript"))
        if missing_url:
            post_blockers.append(f"@{username}: {missing_url} posts missing URL")
        if missing_metrics:
            post_warnings.append(f"@{username}: {missing_metrics} posts missing public metrics")
        if missing_transcripts:
            post_warnings.append(f"@{username}: {missing_transcripts} posts missing transcripts")

    all_blockers = _unique(blockers + post_blockers)
    all_warnings = _unique(warnings + post_warnings)
    status = "ready"
    if all_blockers:
        status = "blocked"
    elif all_warnings:
        status = "needs_review"

    return {
        "overall_status": status,
        "creator": {
            "total": len(creators),
            "valid": max(0, len(creators) - len(invalid_creator_keys)),
            "market_coverage": [country for country, count in country_counts.items() if count],
            "country_counts": country_counts,
            "blockers": _unique(blockers),
            "warnings": _unique(warnings),
            "readiness": readiness,
        },
        "posts": {
            "loaded": loaded_posts,
            "required": required_posts,
            "coverage_percent": round((loaded_posts / required_posts) * 100) if required_posts else 0,
            "blockers": _unique(post_blockers),
            "warnings": _unique(post_warnings),
        },
        "blocker_count": len(all_blockers),
        "warning_count": len(all_warnings),
        "summary": _quality_summary(status, len(all_blockers), len(all_warnings)),
    }


def enrich_creator_profiles(creators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for creator in creators:
        text = " ".join(
            str(value or "")
            for value in (
                creator.get("bio"),
                creator.get("recommended_campaign_angle"),
                " ".join(creator.get("signals") or []),
                " ".join(creator.get("recommended_products") or []),
            )
        ).lower()
        matched_categories = _matched_products(text)
        contact_channels = []
        if creator.get("contact_email"):
            contact_channels.append("email")
        if creator.get("instagram_url"):
            contact_channels.append("instagram")
        if creator.get("profile_url"):
            contact_channels.append(creator.get("platform") or "profile")
        missing_data = []
        for key in ("country", "profile_url", "follower_count"):
            if creator.get(key) in {None, ""}:
                missing_data.append(key)
        if not contact_channels:
            missing_data.append("contact_channel")

        status = "ready"
        if missing_data:
            status = "needs_review"
        if creator.get("source_risk_level") not in {"low", "low_medium", "medium"}:
            status = "blocked"

        country = creator.get("country") if creator.get("country") in COUNTRIES else "unknown"
        enriched.append(
            {
                "creator_id": creator.get("creator_id") or creator.get("id") or creator.get("username"),
                "username": creator.get("username"),
                "display_name": creator.get("display_name") or creator.get("username"),
                "primary_country": country,
                "country_confidence": 0.85 if country != "unknown" else 0.35,
                "language": creator.get("language") or "es",
                "platforms": _unique([creator.get("platform") or "tiktok"]),
                "contact_channels": contact_channels,
                "normalized_categories": matched_categories or list(creator.get("recommended_products") or []),
                "commerce_readiness": _commerce_readiness(creator, text),
                "duplicate_key": f"{creator.get('platform') or 'tiktok'}:{str(creator.get('username') or '').lower()}",
                "missing_data": _unique(missing_data),
                "enrichment_status": status,
                "next_action": "run_recent_20_screen" if status == "ready" else "complete_profile_data",
            }
        )
    return enriched


def apply_recent_screen_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for item in items:
        result = item.get("screen_result") or {}
        decision = result.get("suitability_decision") or "human_review"
        score = float(result.get("suitability_score") or 0)
        if decision == "pass_to_full_analysis":
            queue = "full_analysis_queue"
            action = "run_profile_comment_multimodal_analysis"
        elif decision == "human_review":
            queue = "human_review_queue"
            action = "operator_review"
        elif decision == "avoid":
            queue = "avoid_queue"
            action = "exclude_from_campaign"
        else:
            queue = "recheck_later_queue"
            action = "collect_more_data_or_recheck"
        applied.append(
            {
                "creator_id": item.get("creator_id"),
                "username": (item.get("creator_snapshot") or {}).get("username"),
                "suitability_decision": decision,
                "suitability_score": score,
                "queue": queue,
                "next_action": action,
                "matched_product_categories": result.get("matched_product_categories", []),
                "coverage_gaps": result.get("coverage_gaps", []),
                "risk_notes": result.get("risk_notes", []),
                "post_count_analyzed": result.get("post_count_analyzed", 0),
                "screen_result": result,
            }
        )
    return applied


def match_campaign_candidates(
    candidates: list[dict[str, Any]],
    product_category: str,
    country: str | None = None,
    recent_screen_results: dict[str, dict[str, Any]] | None = None,
    min_score: float = 70,
    max_risk_penalty: float = 10,
    limit: int = 50,
) -> list[dict[str, Any]]:
    recent_screen_results = recent_screen_results or {}
    matched: list[dict[str, Any]] = []
    for candidate in candidates:
        if country and candidate.get("country") != country:
            continue
        final_score = float(candidate.get("final_score") or candidate.get("score") or 0)
        risk_penalty = float(candidate.get("risk_penalty") or 0)
        if final_score < min_score or risk_penalty > max_risk_penalty or candidate.get("segment") == "avoid":
            continue
        creator_id = str(candidate.get("creator_id") or candidate.get("id") or candidate.get("username"))
        screen = recent_screen_results.get(creator_id) or {}
        recommended_products = candidate.get("recommended_products") or []
        product_match = product_category in recommended_products or product_category in screen.get(
            "matched_product_categories", []
        )
        recent_score = float(screen.get("suitability_score") or 0)
        pass_bonus = 8 if screen.get("suitability_decision") == "pass_to_full_analysis" else 0
        product_bonus = 12 if product_match else -6
        match_score = max(
            0,
            min(
                100,
                round(final_score * 0.55 + recent_score * 0.25 + product_bonus + pass_bonus - risk_penalty * 0.8, 2),
            ),
        )
        matched.append(
            {
                **candidate,
                "creator_id": creator_id,
                "campaign_product_category": product_category,
                "product_match": product_match,
                "recent_posts_decision": screen.get("suitability_decision"),
                "recent_posts_score": recent_score,
                "match_score": match_score,
                "priority_label": priority_label(final_score=match_score, risk_penalty=risk_penalty),
                "match_reasons": _match_reasons(candidate, screen, product_category, product_match),
            }
        )
    ranked = sorted(
        matched,
        key=lambda row: (
            -float(row.get("match_score") or 0),
            float(row.get("risk_penalty") or 0),
            -int(row.get("follower_count") or 0),
        ),
    )
    return [{**row, "rank": index + 1} for index, row in enumerate(ranked[: max(1, min(limit, 100))])]


def build_outreach_plan(
    candidates: list[dict[str, Any]],
    product_category: str,
    product_name: str | None = None,
    dm_variant: str = "product_review",
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.get("priority_label") in {"store_only", "recheck_later"}:
            continue
        drafts = build_dm_drafts(candidate, product_category=product_category, product_name=product_name)
        selected = next((draft for draft in drafts if draft["variant"] == dm_variant), drafts[0])
        terms = recommended_offer_terms(candidate)
        items.append(
            {
                "creator_id": candidate.get("creator_id"),
                "username": candidate.get("username"),
                "rank": candidate.get("rank"),
                "priority_label": candidate.get("priority_label"),
                "dm_variant": selected["variant"],
                "dm_message": selected["message"],
                "offer_terms": terms,
                "claims_check_status": "needs_review",
                "crm_status": "dm_drafted",
                "manual_send_required": True,
                "next_action": "run_claims_check_then_operator_approval",
            }
        )
    return items


def build_outreach_crm_board(outreach_items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(item.get("status") or item.get("crm_status") or "discovered" for item in outreach_items)
    stages = [
        {
            "status": status,
            "count": counts.get(status, 0),
            "items": [
                item
                for item in outreach_items
                if (item.get("status") or item.get("crm_status") or "discovered") == status
            ][:10],
        }
        for status in OUTREACH_FUNNEL_ORDER
        if counts.get(status, 0) or status in {"dm_drafted", "approved", "dm_sent", "replied", "accepted"}
    ]
    next_actions: list[str] = []
    if counts.get("dm_drafted", 0):
        next_actions.append("Run claims check and human approval for drafted DMs.")
    if counts.get("approved", 0):
        next_actions.append("Manually send approved DMs and record status.")
    if counts.get("replied", 0) or counts.get("negotiating", 0):
        next_actions.append("Record proposed terms and confirm deliverables.")
    if not next_actions:
        next_actions.append("Prepare outreach drafts for matched candidates.")
    return {
        "total": len(outreach_items),
        "counts": dict(counts),
        "stages": stages,
        "next_actions": next_actions,
        "manual_send_policy": {
            "auto_send_enabled": False,
            "required_before_send": ["claims_check_passed", "human_approval", "manual_send_confirmed"],
        },
    }


def rollup_performance(
    snapshots: list[dict[str, Any]],
    spend_usd: float | None = None,
) -> dict[str, Any]:
    totals = {
        "snapshot_count": len(snapshots),
        "view_count": sum(int(item.get("view_count") or 0) for item in snapshots),
        "like_count": sum(int(item.get("like_count") or 0) for item in snapshots),
        "comment_count": sum(int(item.get("comment_count") or 0) for item in snapshots),
        "share_count": sum(int(item.get("share_count") or 0) for item in snapshots),
        "click_count": sum(int(item.get("click_count") or 0) for item in snapshots),
        "conversion_count": sum(int(item.get("conversion_count") or 0) for item in snapshots),
        "revenue_usd": round(sum(float(item.get("revenue_usd") or 0) for item in snapshots), 2),
    }
    spend = float(spend_usd or 0)
    totals["engagement_count"] = totals["like_count"] + totals["comment_count"] + totals["share_count"]
    totals["engagement_rate"] = round(totals["engagement_count"] / totals["view_count"], 4) if totals["view_count"] else 0
    totals["click_through_rate"] = round(totals["click_count"] / totals["view_count"], 4) if totals["view_count"] else 0
    totals["conversion_rate"] = round(totals["conversion_count"] / totals["click_count"], 4) if totals["click_count"] else 0
    totals["roas"] = round(totals["revenue_usd"] / spend, 2) if spend else None

    by_creator: dict[str, dict[str, Any]] = defaultdict(lambda: {"view_count": 0, "revenue_usd": 0, "conversion_count": 0})
    for item in snapshots:
        creator_id = str(item.get("creator_id") or item.get("username") or "unknown")
        by_creator[creator_id]["creator_id"] = creator_id
        by_creator[creator_id]["view_count"] += int(item.get("view_count") or 0)
        by_creator[creator_id]["conversion_count"] += int(item.get("conversion_count") or 0)
        by_creator[creator_id]["revenue_usd"] += float(item.get("revenue_usd") or 0)
    leaderboard = sorted(
        (
            {**value, "revenue_usd": round(float(value["revenue_usd"]), 2)}
            for value in by_creator.values()
        ),
        key=lambda row: (-float(row["revenue_usd"]), -int(row["view_count"])),
    )
    return {
        "summary": totals,
        "creator_leaderboard": leaderboard[:20],
        "next_actions": _performance_next_actions(totals),
    }


def recommended_offer_terms(candidate: dict[str, Any]) -> dict[str, Any]:
    followers = int(candidate.get("follower_count") or 0)
    score = float(candidate.get("match_score") or candidate.get("final_score") or 0)
    base_fee = 80
    if followers >= 100000:
        base_fee = 350
    elif followers >= 50000:
        base_fee = 220
    elif followers >= 20000:
        base_fee = 140
    if score >= 90:
        base_fee = round(base_fee * 1.2)
    return {
        "fee_usd": base_fee,
        "sample_product": True,
        "deliverables": ["1 short-form video", "story/link placement if available"],
        "usage_rights_days": 30,
        "performance_bonus": {
            "eligible": True,
            "trigger": "tracked revenue or conversion target",
        },
        "tracking": {
            "coupon_code_required": True,
            "tracking_url_required": True,
        },
    }


def _commerce_readiness(creator: dict[str, Any], text: str) -> str:
    if any(term in text for term in ("link", "codigo", "código", "comprar", "descuento", "precio")):
        return "commerce_ready"
    if int(creator.get("follower_count") or 0) >= 20000:
        return "audience_ready"
    return "needs_validation"


def _matched_products(text: str) -> list[str]:
    return [
        product
        for product, terms in PRODUCT_TERMS.items()
        if any(term in text for term in terms)
    ]


def _match_reasons(
    candidate: dict[str, Any],
    screen: dict[str, Any],
    product_category: str,
    product_match: bool,
) -> list[str]:
    reasons = []
    if product_match:
        reasons.append(f"matched_product:{product_category}")
    if screen.get("suitability_decision") == "pass_to_full_analysis":
        reasons.append("recent_20_pass")
    if float(candidate.get("final_score") or 0) >= 85:
        reasons.append("high_creator_score")
    if float(candidate.get("risk_penalty") or 0) <= 5:
        reasons.append("low_risk_penalty")
    return reasons or ["candidate_meets_minimum_filters"]


def _performance_next_actions(summary: dict[str, Any]) -> list[str]:
    actions = []
    if summary["snapshot_count"] == 0:
        actions.append("Add post URL, tracking URL, coupon, and revenue snapshots.")
    if summary["click_count"] == 0 and summary["view_count"] > 0:
        actions.append("Attach tracking URLs to separate awareness from conversion performance.")
    if summary["conversion_count"] == 0 and summary["click_count"] > 0:
        actions.append("Review offer, landing page, and coupon activation.")
    if not actions:
        actions.append("Use creator leaderboard to expand budget toward top performers.")
    return actions


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        normalized = value.strip().lower()
        if not normalized:
            continue
        if normalized in seen:
            duplicates.add(value)
        seen.add(normalized)
    return sorted(duplicates)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _quality_summary(status: str, blocker_count: int, warning_count: int) -> str:
    if status == "blocked":
        return f"{blocker_count} blockers must be fixed before import or screening."
    if status == "needs_review":
        return f"{warning_count} warnings need operator review before outreach."
    return "Ready for import, screening, and operator review."
