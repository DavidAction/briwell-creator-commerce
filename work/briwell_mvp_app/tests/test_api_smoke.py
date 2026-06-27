from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "v0.1"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_dashboard_cors_origin_allowed() -> None:
    response = client.get(
        "/health",
        headers={"Origin": "http://127.0.0.1:8070"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8070"


def test_list_products_placeholder() -> None:
    response = client.get("/products")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_ops_readiness_requires_admin() -> None:
    response = client.get("/ops/readiness", headers={"X-User-Role": "admin"})
    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["request_id_middleware_enabled"] is True
    assert "production_note" in body


def test_ops_readiness_rejects_operator() -> None:
    response = client.get("/ops/readiness", headers={"X-User-Role": "operator"})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_list_campaigns_placeholder() -> None:
    response = client.get("/campaigns", params={"country": "MX", "product_category": "sunscreen"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["filters"]["country"] == "MX"
    assert body["filters"]["product_category"] == "sunscreen"


def test_discovery_source_policy_lists_blocked_scraping_sources() -> None:
    response = client.get("/discovery/source-policy")
    assert response.status_code == 200
    body = response.json()
    assert "manual" in body["allowed_source_types"]
    assert "browser_automation" in body["blocked_source_types"]
    assert "Unauthorized scraping is blocked" in body["policy"]


def test_discovery_plan_builds_without_database() -> None:
    response = client.post(
        "/discovery/plans",
        headers={"X-User-Role": "operator"},
        json={
            "countries": ["MX", "PE", "EC"],
            "product_categories": ["sunscreen"],
            "platforms": ["tiktok"],
            "max_keywords_per_country_category": 2,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "planned"
    assert body["planned_count"] == 6
    assert {item["country"] for item in body["items"]} == {"MX", "PE", "EC"}
    assert all(item["platform"] == "tiktok" for item in body["items"])


def test_discovery_plan_rejects_viewer_role() -> None:
    response = client.post(
        "/discovery/plans",
        headers={"X-User-Role": "viewer"},
        json={
            "countries": ["MX"],
            "product_categories": ["sunscreen"],
            "platforms": ["tiktok"],
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_ai_provider_status_reports_live_gate() -> None:
    response = client.get(
        "/ai/provider-status",
        headers={"X-User-Role": "operator"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "google"
    assert body["default_adapter"] == "GeminiTextAdapter"
    assert body["live_ready"] is False
    assert body["live_limits"]["daily_call_limit"] >= 1
    assert body["live_limits"]["require_database"] is True


def test_create_campaign_validates_without_database() -> None:
    response = client.post(
        "/campaigns",
        headers={"X-User-Role": "campaign_manager"},
        json={
            "name": "MX Sunscreen Seeding",
            "country": "MX",
            "product_category": "sunscreen",
            "campaign_goal": "Find Spanish-speaking skincare creators for K-beauty SPF.",
            "budget": 1200,
            "sales_channel": "tiktok_shop",
            "target_creator_count": 20,
            "target_post_count": 30,
            "status": "draft",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert body["campaign"]["country"] == "MX"


def test_create_campaign_rejects_viewer_role() -> None:
    response = client.post(
        "/campaigns",
        headers={"X-User-Role": "viewer"},
        json={
            "name": "MX Sunscreen Seeding",
            "country": "MX",
            "product_category": "sunscreen",
            "campaign_goal": "Find Spanish-speaking skincare creators.",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_campaign_candidates_placeholder_without_database() -> None:
    response = client.get(
        "/campaigns/campaign-1/candidates",
        headers={"X-User-Role": "operator"},
        params={
            "min_score": 75,
            "max_risk_penalty": 8,
            "segment": "viral_micro",
            "product_category": "sunscreen",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["filters"]["min_score"] == 75
    assert body["filters"]["max_risk_penalty"] == 8
    assert body["filters"]["segment"] == "viral_micro"


def test_campaign_candidates_rejects_viewer_role() -> None:
    response = client.get(
        "/campaigns/campaign-1/candidates",
        headers={"X-User-Role": "viewer"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_campaign_candidates_rejects_avoid_segment() -> None:
    response = client.get(
        "/campaigns/campaign-1/candidates",
        headers={"X-User-Role": "operator"},
        params={"segment": "avoid"},
    )
    assert response.status_code == 422


def test_campaign_outreach_drafts_prepare_without_database() -> None:
    response = client.post(
        "/campaigns/campaign-1/outreach-drafts",
        headers={"X-User-Role": "campaign_manager"},
        json={
            "product_category": "sunscreen",
            "product_name": "Briwell Daily Sun",
            "dm_variant": "product_review",
            "candidate_snapshots": [
                {
                    "creator_id": "creator-1",
                    "country": "MX",
                    "username": "creator_mx",
                    "display_name": "Creator MX",
                    "profile_url": "https://example.com/@creator_mx",
                    "source_risk_level": "low",
                    "bio": "skincare reviews",
                    "follower_count": 12000,
                    "final_score": 86,
                    "risk_penalty": 4,
                    "segment": "beauty_educator",
                    "recommended_products": ["sunscreen"],
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert body["prepared_count"] == 1
    assert body["skipped_count"] == 0
    assert body["items"][0]["priority_label"] == "priority_outreach"
    assert body["items"][0]["outreach"]["status"] == "dm_drafted"
    assert body["items"][0]["outreach"]["claims_check_status"] == "needs_review"
    assert body["claims_check_policy"]["send_allowed"] is False


def test_campaign_outreach_drafts_skip_blocked_candidate() -> None:
    response = client.post(
        "/campaigns/campaign-1/outreach-drafts",
        headers={"X-User-Role": "operator"},
        json={
            "product_category": "sunscreen",
            "candidate_snapshots": [
                {
                    "creator_id": "creator-1",
                    "country": "MX",
                    "username": "creator_mx",
                    "profile_url": "https://example.com/@creator_mx",
                    "source_risk_level": "low",
                    "do_not_contact": True,
                },
                {
                    "creator_id": "creator-2",
                    "country": "MX",
                    "username": "creator_high",
                    "profile_url": "https://example.com/@creator_high",
                    "source_risk_level": "high",
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["prepared_count"] == 0
    assert body["skipped_count"] == 2
    assert {item["reason"] for item in body["skipped"]} == {
        "do_not_contact",
        "source_risk_not_allowed",
    }


def test_campaign_outreach_drafts_skip_low_score_candidate() -> None:
    response = client.post(
        "/campaigns/campaign-1/outreach-drafts",
        headers={"X-User-Role": "operator"},
        json={
            "product_category": "sunscreen",
            "min_score": 75,
            "candidate_snapshots": [
                {
                    "creator_id": "creator-1",
                    "country": "MX",
                    "username": "creator_mx",
                    "profile_url": "https://example.com/@creator_mx",
                    "source_risk_level": "low",
                    "final_score": 62,
                    "risk_penalty": 4,
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["prepared_count"] == 0
    assert body["skipped_count"] == 1
    assert body["skipped"][0]["reason"] == "below_min_score"


def test_campaign_outreach_drafts_rejects_viewer_role() -> None:
    response = client.post(
        "/campaigns/campaign-1/outreach-drafts",
        headers={"X-User-Role": "viewer"},
        json={
            "product_category": "sunscreen",
            "candidate_snapshots": [
                {
                    "creator_id": "creator-1",
                    "country": "MX",
                    "username": "creator_mx",
                    "profile_url": "https://example.com/@creator_mx",
                    "source_risk_level": "low",
                }
            ],
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_campaign_outreach_drafts_requires_product_category_without_database() -> None:
    response = client.post(
        "/campaigns/campaign-1/outreach-drafts",
        headers={"X-User-Role": "operator"},
        json={
            "candidate_snapshots": [
                {
                    "creator_id": "creator-1",
                    "country": "MX",
                    "username": "creator_mx",
                    "profile_url": "https://example.com/@creator_mx",
                    "source_risk_level": "low",
                }
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "PRODUCT_CATEGORY_REQUIRED"


def test_create_product_validates_without_database() -> None:
    response = client.post(
        "/products",
        headers={"X-User-Role": "admin"},
        json={
            "brand_name": "Briwell Test",
            "product_name": "SPF Test",
            "product_category": "sunscreen",
            "country_availability": ["MX"],
            "key_claims_allowed": ["Daily SPF routine"],
            "claims_disallowed": ["Cures acne"],
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "validated_not_persisted"


def test_creator_import_rejects_high_risk() -> None:
    response = client.post(
        "/creators/import",
        headers={"X-User-Role": "operator"},
        json={
            "source_type": "manual",
            "source_risk_level": "high",
            "items": [
                {
                    "country": "MX",
                    "username": "creator",
                    "profile_url": "https://example.com/@creator",
                }
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "SOURCE_RISK_NOT_ALLOWED"


def test_creator_import_rejects_unapproved_source_type() -> None:
    response = client.post(
        "/creators/import",
        headers={"X-User-Role": "operator"},
        json={
            "source_type": "random vendor export",
            "source_risk_level": "low",
            "items": [
                {
                    "country": "MX",
                    "username": "creator",
                    "profile_url": "https://example.com/@creator",
                }
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "COLLECTION_SOURCE_TYPE_NOT_ALLOWED"
    assert response.json()["detail"]["details"]["reason"] == "collection_source_type_not_approved"


def test_creator_import_accepts_medium_without_database() -> None:
    response = client.post(
        "/creators/import",
        headers={"X-User-Role": "operator"},
        json={
            "source_type": "manual",
            "source_risk_level": "medium",
            "items": [
                {
                    "country": "PE",
                    "username": "creator_pe",
                    "profile_url": "https://example.com/@creator_pe",
                    "language": "es",
                    "follower_count": 1200,
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["accepted"] == 1
    assert response.json()["status"] == "validated_not_persisted"


def test_write_endpoints_reject_viewer_role() -> None:
    response = client.post(
        "/products",
        headers={"X-User-Role": "viewer"},
        json={
            "brand_name": "Briwell Test",
            "product_name": "SPF Test",
            "product_category": "sunscreen",
            "country_availability": ["MX"],
            "key_claims_allowed": [],
            "claims_disallowed": [],
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_write_endpoints_reject_missing_role() -> None:
    response = client.post(
        "/creators/import",
        json={
            "source_type": "manual",
            "source_risk_level": "low",
            "items": [
                {
                    "country": "MX",
                    "username": "creator",
                    "profile_url": "https://example.com/@creator",
                }
            ],
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_analysis_job_accepts_low_risk_operator_without_database() -> None:
    response = client.post(
        "/analysis-jobs",
        headers={"X-User-Role": "operator"},
        json={
            "job_type": "profile_analysis",
            "source_risk_level": "low",
            "target_entity_type": "creator",
            "target_entity_ids": ["creator-1"],
            "model_alias": "low_cost_text",
            "estimated_cost_usd": 0.05,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert body["analysis_job"]["approval_required"] is False


def test_analysis_job_rejects_high_risk() -> None:
    response = client.post(
        "/analysis-jobs",
        headers={"X-User-Role": "admin"},
        json={
            "job_type": "profile_analysis",
            "source_risk_level": "high",
            "target_entity_type": "creator",
            "target_entity_ids": ["creator-1"],
            "model_alias": "low_cost_text",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "SOURCE_RISK_NOT_ALLOWED"


def test_analysis_job_medium_requires_admin() -> None:
    response = client.post(
        "/analysis-jobs",
        headers={"X-User-Role": "operator"},
        json={
            "job_type": "multimodal_analysis",
            "source_risk_level": "medium",
            "target_entity_type": "creator",
            "target_entity_ids": ["creator-1"],
            "model_alias": "multimodal_default",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_APPROVAL_REQUIRED"


def test_generate_dm_returns_two_drafts_without_database() -> None:
    response = client.post(
        "/outreach/creator-1/generate-dm",
        headers={"X-User-Role": "campaign_manager"},
        json={
            "product_category": "sunscreen",
            "product_name": "Briwell Daily Sun",
            "creator_snapshot": {
                "country": "MX",
                "username": "creator_mx",
                "display_name": "Creator MX",
                "profile_url": "https://example.com/@creator_mx",
                "source_risk_level": "low",
                "bio": "skincare reviews",
                "follower_count": 12000,
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert len(body["drafts"]) >= 2
    assert body["review_required"] is True
    assert body["outreach"]["claims_check_status"] == "needs_review"


def test_generate_dm_blocks_do_not_contact_creator() -> None:
    response = client.post(
        "/outreach/creator-1/generate-dm",
        headers={"X-User-Role": "operator"},
        json={
            "product_category": "sunscreen",
            "creator_snapshot": {
                "country": "MX",
                "username": "creator_mx",
                "profile_url": "https://example.com/@creator_mx",
                "source_risk_level": "low",
                "do_not_contact": True,
            },
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "DM_GENERATION_NOT_ALLOWED"


def test_generate_dm_blocks_high_risk_creator() -> None:
    response = client.post(
        "/outreach/creator-1/generate-dm",
        headers={"X-User-Role": "operator"},
        json={
            "product_category": "sunscreen",
            "creator_snapshot": {
                "country": "MX",
                "username": "creator_mx",
                "profile_url": "https://example.com/@creator_mx",
                "source_risk_level": "high",
            },
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "DM_GENERATION_NOT_ALLOWED"


def test_claims_check_passes_safe_dm_without_database() -> None:
    response = client.post(
        "/outreach/claims-check",
        headers={"X-User-Role": "operator"},
        json={
            "product_category": "sunscreen",
            "dm_message": (
                "Hola Creator, somos Briwell. Queremos compartir detalles de una "
                "colaboracion K-beauty para una resena honesta."
            ),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "passed"
    assert body["persistence_status"] == "validated_not_persisted"
    assert body["safe_to_send"] is True
    assert body["send_policy"]["human_approval_required"] is True


def test_claims_check_fails_medical_claim_without_database() -> None:
    response = client.post(
        "/outreach/claims-check",
        headers={"X-User-Role": "campaign_manager"},
        json={
            "product_category": "calming_serum",
            "dm_message": "Este serum cura acne y dermatitis.",
            "claims_disallowed": ["cura acne"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["safe_to_send"] is False
    assert body["send_policy"]["send_allowed"] is False
    assert "MEDICAL_OR_TREATMENT_CLAIM" in {issue["code"] for issue in body["issues"]}


def test_claims_check_requires_message_without_database() -> None:
    response = client.post(
        "/outreach/claims-check",
        headers={"X-User-Role": "operator"},
        json={
            "product_category": "sunscreen",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "DM_MESSAGE_REQUIRED"


def test_claims_check_rejects_viewer_role() -> None:
    response = client.post(
        "/outreach/claims-check",
        headers={"X-User-Role": "viewer"},
        json={
            "product_category": "sunscreen",
            "dm_message": "Hola, queremos compartir detalles.",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_outreach_review_decision_approves_passed_dm_without_database() -> None:
    response = client.post(
        "/outreach/review-decision",
        headers={"X-User-Role": "campaign_manager", "X-User-Email": "manager@briwell.test"},
        json={
            "decision": "approve",
            "claims_check_status": "passed",
            "current_status": "dm_drafted",
            "reviewer_notes": "Approved after claims check.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "decision_recorded"
    assert body["persistence_status"] == "validated_not_persisted"
    assert body["decision"] == "approve"
    assert body["outreach_status"] == "approved"
    assert body["send_gate"]["ready_for_manual_send"] is True
    assert body["send_gate"]["external_send_automated"] is False
    assert body["send_gate"]["manual_send_only"] is True
    assert body["reviewer"]["email"] == "manager@briwell.test"


def test_outreach_review_decision_blocks_unpassed_claims_without_database() -> None:
    response = client.post(
        "/outreach/review-decision",
        headers={"X-User-Role": "operator"},
        json={
            "decision": "approve",
            "claims_check_status": "needs_review",
            "current_status": "dm_drafted",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CLAIMS_CHECK_NOT_PASSED"


def test_outreach_review_decision_records_revision_request_without_database() -> None:
    response = client.post(
        "/outreach/review-decision",
        headers={"X-User-Role": "operator"},
        json={
            "decision": "request_revision",
            "claims_check_status": "needs_review",
            "current_status": "dm_drafted",
            "reviewer_notes": "Tone is fine, but claim needs legal review.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "request_revision"
    assert body["outreach_status"] == "reviewing"
    assert body["send_gate"]["ready_for_manual_send"] is False
    assert "claims_check_passed" in body["send_gate"]["required_before_send"]
    assert "human_approval" in body["send_gate"]["required_before_send"]


def test_outreach_review_decision_rejects_viewer_role() -> None:
    response = client.post(
        "/outreach/review-decision",
        headers={"X-User-Role": "viewer"},
        json={
            "decision": "approve",
            "claims_check_status": "passed",
            "current_status": "dm_drafted",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_outreach_status_transition_records_manual_send_without_database() -> None:
    response = client.post(
        "/outreach/status-transition",
        headers={"X-User-Role": "operator"},
        json={
            "current_status": "approved",
            "next_status": "dm_sent",
            "claims_check_status": "passed",
            "do_not_contact_checked": True,
            "manual_send_confirmed": True,
            "operator_notes": "Sent manually in TikTok app.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "transition_recorded"
    assert body["next_status"] == "dm_sent"
    assert body["send_policy"]["external_send_automated"] is False
    assert body["send_policy"]["manual_send_confirmed"] is True


def test_outreach_status_transition_blocks_unconfirmed_send_without_database() -> None:
    response = client.post(
        "/outreach/status-transition",
        headers={"X-User-Role": "operator"},
        json={
            "current_status": "approved",
            "next_status": "dm_sent",
            "claims_check_status": "passed",
            "do_not_contact_checked": True,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "MANUAL_SEND_CONFIRMATION_REQUIRED"


def test_outreach_status_transition_records_reply_without_database() -> None:
    response = client.post(
        "/outreach/status-transition",
        headers={"X-User-Role": "campaign_manager"},
        json={
            "current_status": "dm_sent",
            "next_status": "replied",
            "claims_check_status": "passed",
            "response_summary": "Creator asked about fee and sample delivery.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["next_status"] == "replied"
    assert body["persistence_status"] == "validated_not_persisted"


def test_performance_snapshot_validates_without_database() -> None:
    response = client.post(
        "/performance/snapshots",
        headers={"X-User-Role": "campaign_manager"},
        json={
            "campaign_id": "campaign-1",
            "creator_id": "creator-1",
            "post_url": "https://example.com/post/1",
            "tracking_url": "https://briwell.example/track",
            "coupon_code": "BRI-MX-10",
            "view_count": 12000,
            "click_count": 240,
            "conversion_count": 12,
            "revenue_usd": 320.5,
            "source_type": "manual",
            "source_risk_level": "low",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert body["snapshot"]["source_type"] == "manual"


def test_performance_snapshot_blocks_scrape_source() -> None:
    response = client.post(
        "/performance/snapshots",
        headers={"X-User-Role": "operator"},
        json={
            "source_type": "browser_automation",
            "source_risk_level": "low",
            "view_count": 10,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "PERFORMANCE_SOURCE_NOT_ALLOWED"


def test_performance_snapshot_blocks_unapproved_source_type() -> None:
    response = client.post(
        "/performance/snapshots",
        headers={"X-User-Role": "operator"},
        json={
            "source_type": "agency_screenshot",
            "source_risk_level": "low",
            "view_count": 10,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "PERFORMANCE_SOURCE_NOT_ALLOWED"
    assert response.json()["detail"]["details"]["reason"] == "collection_source_type_not_approved"


def test_compliance_country_claims_check_needs_review() -> None:
    response = client.post(
        "/compliance/country-claims-check",
        headers={"X-User-Role": "operator"},
        json={
            "country": "MX",
            "product_category": "sunscreen",
            "message": "Este SPF es ideal para la rutina diaria.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_review"
    assert body["legal_review_required"] is True


def test_settlement_contract_validates_without_database() -> None:
    response = client.post(
        "/settlements/contracts",
        headers={"X-User-Role": "campaign_manager"},
        json={
            "creator_id": "creator-1",
            "campaign_id": "campaign-1",
            "deliverables": {"videos": 1, "usage_rights_days": 30},
            "compensation_terms": {"fee_usd": 150, "sample": True},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert body["contract"]["deliverables"]["videos"] == 1


def test_settlement_payout_requires_tax_document_when_paid() -> None:
    response = client.post(
        "/settlements/payouts",
        headers={"X-User-Role": "campaign_manager"},
        json={
            "creator_id": "creator-1",
            "campaign_id": "campaign-1",
            "amount_usd": 150,
            "payout_status": "paid",
            "invoice_url": "https://example.com/invoice.pdf",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "TAX_DOCUMENT_REQUIRED"


def test_video_import_accepts_low_risk_without_database() -> None:
    response = client.post(
        "/videos/import",
        headers={"X-User-Role": "operator"},
        json={
            "creator_id": "creator-1",
            "source_type": "manual",
            "source_risk_level": "low",
            "items": [
                {
                    "url": "https://example.com/video/1",
                    "platform_video_id": "video-1",
                    "caption": "Rutina de skincare coreana",
                    "hashtags": ["kbeauty", "skincare"],
                    "view_count": 12000,
                    "like_count": 1200,
                    "comment_count": 48,
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert body["accepted"] == 1
    assert body["source_type"] == "manual"


def test_video_import_rejects_high_risk() -> None:
    response = client.post(
        "/videos/import",
        headers={"X-User-Role": "operator"},
        json={
            "creator_id": "creator-1",
            "source_type": "manual",
            "source_risk_level": "high",
            "items": [{"url": "https://example.com/video/1"}],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "SOURCE_RISK_NOT_ALLOWED"


def test_video_import_rejects_blocked_source_type() -> None:
    response = client.post(
        "/videos/import",
        headers={"X-User-Role": "operator"},
        json={
            "creator_id": "creator-1",
            "source_type": "public page scrape",
            "source_risk_level": "low",
            "items": [{"url": "https://example.com/video/1"}],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "COLLECTION_SOURCE_TYPE_NOT_ALLOWED"


def test_comment_import_accepts_manual_sample_without_database() -> None:
    response = client.post(
        "/comments/import",
        headers={"X-User-Role": "operator"},
        json={
            "video_id": "video-1",
            "sample_method": "manual",
            "source_risk_level": "low_medium",
            "items": [
                {
                    "comment_text": "Donde lo compro?",
                    "like_count": 4,
                    "sentiment": "positive",
                    "purchase_intent": True,
                    "question_type": "where_to_buy",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert body["accepted"] == 1
    assert body["sample_method"] == "manual"


def test_comment_import_rejects_high_risk() -> None:
    response = client.post(
        "/comments/import",
        headers={"X-User-Role": "operator"},
        json={
            "video_id": "video-1",
            "sample_method": "manual",
            "source_risk_level": "high",
            "items": [{"comment_text": "Donde lo compro?"}],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "SOURCE_RISK_NOT_ALLOWED"


def test_comment_import_rejects_sensitive_data() -> None:
    response = client.post(
        "/comments/import",
        headers={"X-User-Role": "operator"},
        json={
            "video_id": "video-1",
            "sample_method": "manual",
            "source_risk_level": "low",
            "items": [
                {
                    "comment_text": "Mi telefono es 555-0101",
                    "contains_sensitive_data": True,
                }
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "SENSITIVE_COMMENT_DATA_NOT_ALLOWED"


def test_ai_validate_output_accepts_profile_analysis() -> None:
    response = client.post(
        "/ai/validate-output",
        headers={"X-User-Role": "operator"},
        json={
            "task_type": "profile_analysis",
            "output": {
                "status": "ok",
                "creator_type": "beauty_reviewer",
                "primary_country": "MX",
                "language": "es",
                "beauty_relevance": 82,
                "contact_available": True,
                "contact_channels": ["tiktok"],
                "sponsorship_experience": "likely",
                "category_tags": ["skincare"],
                "risk_notes": [],
                "evidence": ["Bio mentions skincare reviews."],
                "missing_data": [],
                "confidence": 0.84,
                "review_required": False,
                "review_required_reason": None,
                "summary": "Strong skincare review fit.",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "validated"


def test_ai_validate_output_accepts_recent_posts_screen() -> None:
    response = client.post(
        "/ai/validate-output",
        headers={"X-User-Role": "operator"},
        json={
            "task_type": "recent_posts_screen",
            "output": {
                "status": "ok",
                "post_count_analyzed": 20,
                "expected_post_count": 20,
                "suitability_decision": "pass_to_full_analysis",
                "suitability_score": 86,
                "beauty_content_ratio": 0.9,
                "kbeauty_signal_ratio": 0.7,
                "skincare_relevance_score": 88,
                "commerce_signal_score": 75,
                "consistency_score": 84,
                "brand_safety_precheck_score": 92,
                "matched_product_categories": ["sunscreen"],
                "recent_post_observations": ["Strong recent skincare routine fit."],
                "coverage_gaps": [],
                "risk_notes": [],
                "next_step": "run_full_profile_comment_multimodal_analysis",
                "evidence": ["20 recent approved posts analyzed."],
                "missing_data": [],
                "confidence": 0.84,
                "review_required": False,
                "review_required_reason": None,
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "validated"


def test_ai_validate_output_rejects_invalid_schema() -> None:
    response = client.post(
        "/ai/validate-output",
        headers={"X-User-Role": "operator"},
        json={
            "task_type": "profile_analysis",
            "output": {
                "status": "ok",
                "creator_type": "beauty_reviewer",
            },
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "AI_SCHEMA_INVALID"


def test_ai_dry_run_returns_validated_result() -> None:
    response = client.post(
        "/ai/dry-run",
        headers={"X-User-Role": "operator"},
        json={
            "task_type": "profile_analysis",
            "model_alias": "low_cost_text",
            "source_risk_level": "low",
            "prompt_version": "profile_v0",
            "payload": {
                "creator": {
                    "country": "MX",
                    "username": "creator_mx",
                    "profile_url": "https://example.com/@creator_mx",
                    "bio": "skincare and kbeauty reviews",
                    "language": "es",
                }
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["output"]["primary_country"] == "MX"


def test_multimodal_analysis_job_runs_without_database() -> None:
    response = client.post(
        "/analysis-jobs/run-multimodal",
        headers={"X-User-Role": "operator"},
        json={
            "source_risk_level": "low",
            "video": {
                "video_id": "video-1",
                "caption": "Rutina de piel con protector solar coreano SPF.",
                "transcript": "Este protector se siente ligero y queda bien para diario.",
                "view_count": 24000,
            },
            "frame_samples": [
                {
                    "timestamp_seconds": 1.5,
                    "description": "Creator holds a sunscreen tube near the camera.",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["persistence_status"] == "validated_not_persisted"
    assert body["result"]["output"]["product_visibility_score"] >= 70
    assert "sunscreen" in body["result"]["output"]["visible_product_types"]


def test_recent_posts_screen_job_runs_without_database() -> None:
    recent_posts = [
        {
            "video_id": f"video-{index}",
            "caption": "Rutina skincare con protector solar coreano SPF y link de compra.",
            "transcript": "Protector solar coreano ligero para la piel.",
            "hashtags": ["skincare", "kbeauty", "protectorsolar"],
            "view_count": 15000 + index,
        }
        for index in range(20)
    ]
    response = client.post(
        "/analysis-jobs/run-recent-posts-screen",
        headers={"X-User-Role": "operator"},
        json={
            "creator_id": "creator-1",
            "source_risk_level": "low",
            "recent_posts": recent_posts,
            "creator_snapshot": {"username": "luzskincare", "country": "MX"},
            "product_context": {"product_category": "sunscreen"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["persistence_status"] == "validated_not_persisted"
    output = body["result"]["output"]
    assert output["post_count_analyzed"] == 20
    assert output["suitability_decision"] == "pass_to_full_analysis"
    assert output["next_step"] == "run_full_profile_comment_multimodal_analysis"


def test_analysis_job_run_dry_run_returns_log_preview() -> None:
    response = client.post(
        "/analysis-jobs/run-dry-run",
        headers={"X-User-Role": "operator"},
        json={
            "target_entity_type": "creator",
            "target_entity_id": "creator-1",
            "request": {
                "task_type": "profile_analysis",
                "model_alias": "low_cost_text",
                "source_risk_level": "low",
                "prompt_version": "profile_v0",
                "payload": {
                    "creator": {
                        "country": "MX",
                        "username": "creator_mx",
                        "profile_url": "https://example.com/@creator_mx",
                        "bio": "skincare and kbeauty reviews",
                        "language": "es",
                    }
                },
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["persistence_status"] == "validated_not_persisted"
    assert body["invocation_log"]["status"] == "success"


def test_creator_score_handoff_calculates_without_database() -> None:
    response = client.post(
        "/analysis-jobs/run-creator-score-handoff",
        headers={"X-User-Role": "operator"},
        json={
            "creator_id": "creator-1",
            "source_risk_level": "low",
            "creator_snapshot": {
                "country": "MX",
                "username": "creator_mx",
                "follower_count": 18000,
            },
            "video_metrics": {"avg_view_count": 25000, "engagement_rate": 0.08},
            "profile_analysis": {
                "status": "ok",
                "creator_type": "beauty_reviewer",
                "primary_country": "MX",
                "language": "es",
                "beauty_relevance": 84,
                "contact_available": True,
                "contact_channels": ["tiktok"],
                "sponsorship_experience": "likely",
                "category_tags": ["skincare"],
                "risk_notes": [],
                "evidence": ["Bio and recent content focus on skincare."],
                "missing_data": [],
                "confidence": 0.82,
                "review_required": False,
                "review_required_reason": None,
                "summary": "Strong skincare creator fit.",
            },
            "comment_analysis": {
                "status": "ok",
                "positive_sentiment_ratio": 0.7,
                "negative_sentiment_ratio": 0.05,
                "purchase_intent_comments": 3,
                "where_to_buy_comments": 2,
                "price_questions": 1,
                "skin_concern_questions": 2,
                "spam_or_low_quality_ratio": 0.05,
                "representative_comments": ["Donde lo compro?"],
                "insights": "Comments show purchase intent.",
                "evidence": ["Manual comment sample contains where-to-buy questions."],
                "missing_data": [],
                "confidence": 0.8,
                "review_required": False,
                "review_required_reason": None,
            },
            "final_review": {
                "status": "ok",
                "recommendation": "approve_for_outreach",
                "recommended_products": ["sunscreen"],
                "recommended_campaign_angle": "K-beauty SPF routine with shopping link.",
                "creator_segment": "beauty_educator",
                "strengths": ["Strong skincare relevance"],
                "risks": [],
                "missing_data": [],
                "operator_notes": "Good seed candidate.",
                "evidence": ["Final review approved outreach."],
                "confidence": 0.76,
                "review_required": False,
                "review_required_reason": None,
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "scored"
    assert body["persistence_status"] == "validated_not_persisted"
    assert body["score"]["final_score"] > 75
    assert body["score"]["recommended_products"] == ["sunscreen"]


def test_creator_score_handoff_medium_requires_admin() -> None:
    response = client.post(
        "/analysis-jobs/run-creator-score-handoff",
        headers={"X-User-Role": "operator"},
        json={
            "creator_id": "creator-1",
            "source_risk_level": "medium",
            "creator_snapshot": {"country": "MX"},
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_APPROVAL_REQUIRED"


def test_creator_score_handoff_rejects_high_risk() -> None:
    response = client.post(
        "/analysis-jobs/run-creator-score-handoff",
        headers={"X-User-Role": "admin"},
        json={
            "creator_id": "creator-1",
            "source_risk_level": "high",
            "creator_snapshot": {"country": "MX"},
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "SOURCE_RISK_NOT_ALLOWED"


def test_ai_invocation_logs_requires_admin() -> None:
    response = client.get(
        "/ai-invocation-logs",
        headers={"X-User-Role": "operator"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PERMISSION_DENIED"


def test_ai_invocation_logs_admin_placeholder_without_database() -> None:
    response = client.get(
        "/ai-invocation-logs",
        headers={"X-User-Role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_creator_score_calculates_without_database() -> None:
    response = client.post(
        "/creators/creator-1/score",
        headers={"X-User-Role": "operator"},
        json={
            "beauty_fit_score": 80,
            "engagement_quality_score": 70,
            "audience_locality_score": 90,
            "commerce_intent_score": 60,
            "content_quality_score": 75,
            "collaboration_probability_score": 65,
            "cost_efficiency_score": 70,
            "risk_score": 20,
            "risk_penalty": 5,
            "recommended_products": ["sunscreen"],
            "recommended_campaign_angle": "K-beauty sunscreen review",
            "ai_summary": "Strong fit for sunscreen review.",
            "ai_evidence": [{"source": "profile_analysis", "evidence": ["skincare bio"]}],
            "score_confidence": 0.82,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert body["score"]["final_score"] == 69.0
    assert body["score"]["segment"] == "beauty_educator"


def test_creator_score_rejects_direct_final_score_input() -> None:
    response = client.post(
        "/creators/creator-1/score",
        headers={"X-User-Role": "operator"},
        json={
            "beauty_fit_score": 80,
            "engagement_quality_score": 70,
            "audience_locality_score": 90,
            "commerce_intent_score": 60,
            "content_quality_score": 75,
            "collaboration_probability_score": 65,
            "cost_efficiency_score": 70,
            "risk_score": 20,
            "risk_penalty": 5,
            "score_confidence": 0.82,
            "final_score": 99,
        },
    )
    assert response.status_code == 422


def test_creator_analysis_list_placeholder_without_database() -> None:
    response = client.get("/creators/creator-1/analysis")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_acquisition_orchestration_runs_offline_operations_flow() -> None:
    recent_posts = [
        {
            "platform_video_id": f"orchestration-post-{index}",
            "url": f"https://www.tiktok.com/@luzskincare/video/79000000000000000{index:02d}",
            "caption": "Rutina skincare con protector solar coreano SPF y link de compra.",
            "transcript": "Protector solar coreano de textura ligera para uso diario.",
            "hashtags": ["skincare", "kbeauty", "protectorsolar"],
            "view_count": 18000 + index,
            "like_count": 1200 + index,
            "comment_count": 80 + index,
            "share_count": 20 + index,
        }
        for index in range(1, 21)
    ]
    response = client.post(
        "/operations/acquisition-orchestration",
        headers={"X-User-Role": "operator", "X-User-Email": "ops@briwell.test"},
        json={
            "source_type": "manual",
            "source_risk_level": "low",
            "product_category": "sunscreen",
            "product_name": "Briwell Daily Sun",
            "country": "MX",
            "campaign_goal": "SPF review pilot",
            "creator_candidates": [
                {
                    "creator_id": "creator-local-1",
                    "country": "MX",
                    "username": "luzskincare",
                    "profile_url": "https://www.tiktok.com/@luzskincare",
                    "source_risk_level": "low",
                    "display_name": "Luz Skincare",
                    "bio": "K-beauty skincare reviews with SPF routines and shopping links.",
                    "follower_count": 64000,
                    "avg_views": 21000,
                    "engagement_rate": 6.1,
                    "final_score": 88,
                    "risk_penalty": 3,
                    "segment": "review_creator",
                    "recommended_products": ["sunscreen"],
                }
            ],
            "recent_posts_by_creator": {"creator-local-1": recent_posts},
            "persist_imports": False,
            "recent_screen_dry_run": True,
            "persist_recent_screen_results": False,
            "run_campaign_match": True,
            "build_outreach_plan": True,
            "min_score": 55,
            "spend_usd": 150,
            "performance_snapshots": [
                {
                    "creator_id": "creator-local-1",
                    "view_count": 10000,
                    "like_count": 700,
                    "comment_count": 60,
                    "share_count": 30,
                    "click_count": 180,
                    "conversion_count": 12,
                    "revenue_usd": 360,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["import"]["persistence_status"] == "validated_not_persisted"
    assert body["recent_20_batch"]["screened_count"] == 1
    assert body["recent_20_batch"]["queue_counts"]["full_analysis_queue"] == 1
    assert body["analysis_pipeline"]["items"][0]["tasks"] == [
        "profile_analysis",
        "comment_analysis",
        "multimodal_analysis",
        "creator_score_handoff",
        "final_review",
    ]
    # Full-analysis chain now actually executes and produces a system-computed score,
    # rather than trusting the operator-supplied final_score.
    assert body["full_analysis"]["status"] == "executed"
    assert body["full_analysis"]["scored_count"] == 1
    assert body["analysis_pipeline"]["status"] == "executed"
    assert body["analysis_pipeline"]["items"][0]["status"] == "executed"
    assert "creator_score_handoff" in body["analysis_pipeline"]["items"][0]["executed_tasks"]
    assert body["campaign_match"]["summary"]["matched_count"] == 1
    assert body["campaign_match"]["items"][0]["score_source"] == "system_analysis"
    assert body["campaign_match"]["summary"]["score_source_counts"].get("system_analysis") == 1
    assert body["outreach_plan"]["send_policy"]["auto_send_enabled"] is False
    assert body["compliance"]["policy"]["auto_send_enabled"] is False
    assert body["performance"]["summary"]["roas"] == 2.4
    assert body["settlement"]["payout_policy"]["invoice_required_before_approval"] is True
    assert body["handoff_package"]["status"] == "ready"
