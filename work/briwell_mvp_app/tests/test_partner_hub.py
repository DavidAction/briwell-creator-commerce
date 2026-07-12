from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.partners import extraction as extraction_module
from app.partners.extraction import PartnerAIGateClosed, run_extraction
from app.partners.ingredient_data import REGULATORY_DISCLAIMER
from app.partners.normalization import normalize_ingredient, normalize_ingredient_list
from app.partners.pipeline import enrich_draft
from app.partners.scoring import completeness
from app.partners.screening import screen_ingredients
from app.partners.validation import validate_draft
from app.routers import partner_hub as hub_router

client = TestClient(app)

ADMIN = {"X-User-Role": "admin", "X-User-Email": "admin@briwell.test"}
OPERATOR = {"X-User-Role": "operator", "X-User-Email": "ops@briwell.test"}
VIEWER = {"X-User-Role": "viewer"}

PARTNER_ID = "22222222-2222-2222-2222-222222222222"
DRAFT_ID = "33333333-3333-3333-3333-333333333333"
UPLOAD_ID = "44444444-4444-4444-4444-444444444444"
TOKEN = "b" * 32

JPG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64
PDF_BYTES = b"%PDF-1.7\n" + b"0" * 64


def _dry_run_draft(**overrides):
    uploads = [{"sha256": "abc", "kind": "pdf", "original_filename": "catalog_2026.pdf"}]
    result = run_extraction(uploads, "파넬")
    draft = result["draft"]
    draft.update(overrides)
    return draft


# ---------------------------------------------------------------------------
# pipeline: normalization
# ---------------------------------------------------------------------------


def test_normalize_exact_and_alias_and_korean_alias() -> None:
    assert normalize_ingredient("Niacinamide")["match_status"] == "exact"
    aqua = normalize_ingredient("Aqua")
    assert aqua["match_status"] == "alias"
    assert aqua["inci_name"] == "Water"
    korean = normalize_ingredient("나이아신아마이드")
    assert korean["inci_name"] == "Niacinamide"


def test_normalize_fuzzy_catches_typo_but_not_garbage() -> None:
    typo = normalize_ingredient("Niacinamde")
    assert typo["match_status"] == "fuzzy"
    assert typo["inci_name"] == "Niacinamide"
    garbage = normalize_ingredient("Unknownium Extractide")
    assert garbage["match_status"] == "unmatched"
    assert garbage["inci_name"] is None


def test_normalize_list_preserves_order_and_counts() -> None:
    result = normalize_ingredient_list(["Water", "  ", "Glycerin", "Mysteryol"])
    assert result["total"] == 3
    assert result["matched"] == 2
    assert result["unmatched"] == 1
    assert [item["position"] for item in result["items"]] == [1, 2, 3]


# ---------------------------------------------------------------------------
# pipeline: regulatory screening (signals, never legal advice)
# ---------------------------------------------------------------------------


def test_screening_flags_banned_substance_in_all_markets() -> None:
    items = normalize_ingredient_list(["Water", "Tretinoin"])["items"]
    result = screen_ingredients(items)
    assert all(entry["grade"] == "blocked_candidate" for entry in result["by_country"].values())
    assert result["disclaimer"] == REGULATORY_DISCLAIMER
    assert result["seed_version"]


def test_screening_catches_seeded_substance_even_when_unmatched() -> None:
    # Tretinoin is deliberately NOT in the ingredient dictionary; the raw
    # string check must still catch it so a dictionary miss cannot hide a rule.
    item = normalize_ingredient("Tretinoin")
    assert item["match_status"] == "unmatched"
    result = screen_ingredients([item])
    assert result["by_country"]["MX"]["grade"] == "blocked_candidate"


def test_screening_restricted_and_clean_grades() -> None:
    restricted = screen_ingredients(normalize_ingredient_list(["Hydroquinone"])["items"])
    assert restricted["by_country"]["PE"]["grade"] == "restricted_candidate"
    clean = screen_ingredients(normalize_ingredient_list(["Water", "Glycerin"])["items"])
    assert all(entry["grade"] == "no_flag" for entry in clean["by_country"].values())
    assert clean["flags"] == []


# ---------------------------------------------------------------------------
# pipeline: completeness scoring + validation
# ---------------------------------------------------------------------------


def test_completeness_full_draft_scores_high_and_empty_scores_low() -> None:
    draft = {
        "product_name": "수분 세럼",
        "brand_name": "파넬",
        "product_category": "calming_serum",
        "size": "50ml",
        "key_claims_allowed": ["진정"],
    }
    normalized = normalize_ingredient_list(["Water", "Glycerin", "Niacinamide"])
    screening = screen_ingredients(normalized["items"])
    full = completeness(draft, normalized, screening, photo_count=2)
    assert full["score"] >= 90
    empty = completeness({}, None, None, photo_count=0)
    assert empty["score"] <= 5


def test_completeness_blocked_regulatory_zeroes_component() -> None:
    normalized = normalize_ingredient_list(["Tretinoin"])
    screening = screen_ingredients(normalized["items"])
    result = completeness({}, normalized, screening, photo_count=0)
    assert result["components"]["regulatory"]["earned"] == 0


def test_validation_blocking_and_advisory() -> None:
    verdict = validate_draft({"brand_name": "파넬"}, None)
    assert verdict["can_submit"] is False
    assert any(issue["field"] == "product_name" for issue in verdict["blocking"])
    ok = validate_draft(
        {"product_name": "세럼", "brand_name": "파넬", "product_category": "essence_unknown"},
        normalize_ingredient_list(["Water"]),
    )
    assert ok["can_submit"] is True
    assert any(issue["field"] == "product_category" for issue in ok["advisory"])


# ---------------------------------------------------------------------------
# pipeline: extraction (dry-run default, gated live)
# ---------------------------------------------------------------------------


def test_extraction_dry_run_is_deterministic_and_labeled() -> None:
    uploads = [{"sha256": "abc", "kind": "photo", "original_filename": "a.jpg"}]
    first = run_extraction(uploads, "파넬")
    second = run_extraction(uploads, "파넬")
    assert first == second
    assert first["ai_meta"]["mode"] == "dry_run"
    assert first["draft"]["brand_name"] == "파넬"
    assert "드라이런" in first["draft"]["notes"]


def test_extraction_dry_run_uses_pdf_filename_hint() -> None:
    uploads = [{"sha256": "x", "kind": "pdf", "original_filename": "moisture_serum_catalog.pdf"}]
    result = run_extraction(uploads, "파넬")
    assert result["draft"]["product_name"] == "moisture serum catalog"


def test_extraction_live_without_key_raises_gate_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        extraction_module,
        "settings",
        SimpleNamespace(
            partner_ai_dry_run=False,
            allow_live_partner_ai_calls=True,
            gemini_api_key="",
        ),
    )
    try:
        run_extraction([], "파넬")
        raise AssertionError("expected PartnerAIGateClosed")
    except PartnerAIGateClosed:
        pass


def test_enrich_draft_bundles_all_pipeline_outputs() -> None:
    draft = _dry_run_draft()
    enriched = enrich_draft(draft, photo_count=1)
    assert set(enriched) == {"ingredients_normalized", "validation", "regulatory", "completeness"}
    assert enriched["regulatory"]["disclaimer"] == REGULATORY_DISCLAIMER


# ---------------------------------------------------------------------------
# operator endpoints: RBAC + DB-off conventions
# ---------------------------------------------------------------------------


def test_create_partner_viewer_forbidden() -> None:
    response = client.post("/partners", headers=VIEWER, json={"company_name": "파넬"})
    assert response.status_code == 403


def test_create_partner_no_role_forbidden() -> None:
    response = client.post("/partners", json={"company_name": "파넬"})
    assert response.status_code == 403


def test_create_partner_without_database_validated_only() -> None:
    response = client.post("/partners", headers=ADMIN, json={"company_name": "파넬"})
    assert response.status_code == 200
    assert response.json()["status"] == "validated_not_persisted"


def test_list_partners_without_database_empty() -> None:
    response = client.get("/partners", headers=OPERATOR)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_issue_partner_token_without_database_validated_only() -> None:
    response = client.post("/partners/tokens", headers=ADMIN, json={"partner_id": PARTNER_ID})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated_not_persisted"
    assert isinstance(body["token"], str) and len(body["token"]) >= 32


def test_issue_partner_token_unknown_partner_404(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository, "get_partner_by_id", lambda partner_id: None
    )
    response = client.post("/partners/tokens", headers=ADMIN, json={"partner_id": PARTNER_ID})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PARTNER_NOT_FOUND"


def test_revoke_partner_tokens_viewer_forbidden() -> None:
    response = client.delete(f"/partners/tokens/{PARTNER_ID}", headers=VIEWER)
    assert response.status_code == 403


def test_review_queue_without_database_empty_with_disclaimer() -> None:
    response = client.get("/partners/review-queue", headers=OPERATOR)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["disclaimer"] == REGULATORY_DISCLAIMER


def test_review_without_database_validated_only() -> None:
    response = client.post(
        f"/partners/review/{DRAFT_ID}", headers=ADMIN, json={"decision": "approved"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "validated_not_persisted"


def test_partner_token_revoke_preflight_allows_delete() -> None:
    response = client.options(
        f"/partners/tokens/{PARTNER_ID}",
        headers={
            "Origin": "http://127.0.0.1:8070",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]


# ---------------------------------------------------------------------------
# operator review flow (DB mocked)
# ---------------------------------------------------------------------------


def _reviewable_row(draft: dict) -> dict:
    return {
        "id": DRAFT_ID,
        "partner_id": PARTNER_ID,
        "draft": draft,
        "status": "partner_confirmed",
    }


def test_review_unknown_draft_404(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(hub_router.partners_repository, "get_draft", lambda draft_id: None)
    response = client.post(
        f"/partners/review/{DRAFT_ID}", headers=ADMIN, json={"decision": "approved"}
    )
    assert response.status_code == 404


def test_review_wrong_status_409(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_draft",
        lambda draft_id: {"id": draft_id, "status": "ai_draft", "draft": {}},
    )
    response = client.post(
        f"/partners/review/{DRAFT_ID}", headers=ADMIN, json={"decision": "approved"}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DRAFT_NOT_REVIEWABLE"


def test_review_unsupported_category_422(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_draft",
        lambda draft_id: _reviewable_row(
            {"product_name": "세럼", "brand_name": "파넬", "product_category": "essence"}
        ),
    )
    response = client.post(
        f"/partners/review/{DRAFT_ID}", headers=ADMIN, json={"decision": "approved"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CATEGORY_UNSUPPORTED"


def test_review_approve_promotes_to_product_catalog(monkeypatch) -> None:
    calls: dict = {}

    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_draft",
        lambda draft_id: _reviewable_row(
            {
                "product_name": "수분 진정 세럼",
                "brand_name": "파넬",
                "product_category": "calming_serum",
                "country_availability": ["MX", "PE", "XX"],
                "key_claims_allowed": ["진정 케어"],
            }
        ),
    )
    def fake_create_product(payload: dict) -> dict:
        calls["product"] = payload
        return {"id": "prod-1", **payload}

    def fake_finalize(draft_id: str, status: str, promoted_product_id: str | None) -> dict:
        calls["finalize"] = (draft_id, status, promoted_product_id)
        return {"id": draft_id, "status": status}

    def fake_decision(payload: dict) -> dict:
        calls["decision"] = payload
        return {"id": "dec-1"}

    monkeypatch.setattr(hub_router.products_repository, "create_product", fake_create_product)
    monkeypatch.setattr(hub_router.partners_repository, "finalize_draft", fake_finalize)
    monkeypatch.setattr(
        hub_router.partners_repository, "record_review_decision", fake_decision
    )

    response = client.post(
        f"/partners/review/{DRAFT_ID}", headers=OPERATOR, json={"decision": "approved"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "approved"
    # Unknown market codes are filtered at promotion time.
    assert calls["product"]["country_availability"] == ["MX", "PE"]
    assert calls["finalize"] == (DRAFT_ID, "approved", "prod-1")
    assert calls["decision"]["decided_by"] == "ops@briwell.test"


def test_review_reject_records_reason(monkeypatch) -> None:
    calls: dict = {}
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_draft",
        lambda draft_id: _reviewable_row({"product_name": "세럼", "brand_name": "파넬"}),
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "finalize_draft",
        lambda draft_id, status, promoted_product_id: {"id": draft_id, "status": status},
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "record_review_decision",
        lambda payload: calls.setdefault("decision", payload) or {"id": "dec-1"},
    )
    response = client.post(
        f"/partners/review/{DRAFT_ID}",
        headers=ADMIN,
        json={"decision": "rejected", "reason": "성분표 재확인 필요"},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "rejected"
    assert calls["decision"]["reason"] == "성분표 재확인 필요"


# ---------------------------------------------------------------------------
# partner-facing surface: honest failure + token gate
# ---------------------------------------------------------------------------


def test_hub_me_without_database_503() -> None:
    response = client.get(f"/partner-hub/me?token={TOKEN}")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "PARTNER_HUB_UNAVAILABLE"


def test_hub_me_short_token_422() -> None:
    response = client.get("/partner-hub/me?token=short")
    assert response.status_code == 422


def test_hub_me_invalid_token_404(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository, "get_active_by_token", lambda token: None
    )
    response = client.get(f"/partner-hub/me?token={TOKEN}")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PARTNER_TOKEN_INVALID"


def test_hub_me_suspended_partner_is_invalid(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_active_by_token",
        lambda token: {"id": "tok-1", "partner_id": PARTNER_ID},
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_partner_by_id",
        lambda partner_id: {"id": partner_id, "company_name": "파넬", "status": "suspended"},
    )
    response = client.get(f"/partner-hub/me?token={TOKEN}")
    assert response.status_code == 404


def test_upload_without_database_503() -> None:
    response = client.post(
        f"/partner-hub/uploads?kind=photo&token={TOKEN}",
        files={"file": ("a.jpg", JPG_BYTES, "image/jpeg")},
    )
    assert response.status_code == 503


def test_extract_without_database_503() -> None:
    response = client.post(
        f"/partner-hub/uploads/extract?token={TOKEN}", json={"upload_ids": [UPLOAD_ID]}
    )
    assert response.status_code == 503


def test_draft_update_without_database_503() -> None:
    response = client.post(
        f"/partner-hub/drafts/{DRAFT_ID}?token={TOKEN}",
        json={"draft": {"product_name": "세럼"}},
    )
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# upload validation: the three separated lanes enforce their file types
# ---------------------------------------------------------------------------


def test_upload_validation_rejects_wrong_lane_and_bad_magic() -> None:
    assert hub_router.validate_upload_file("photo", "malware.exe", b"MZ") is not None
    assert hub_router.validate_upload_file("photo", "catalog.pdf", PDF_BYTES) is not None
    assert hub_router.validate_upload_file("pdf", "photo.jpg", JPG_BYTES) is not None
    # Correct extension but wrong content: a PNG posing as JPG is rejected.
    png_as_jpg = hub_router.validate_upload_file("photo", "fake.jpg", b"\x89PNG\r\n\x1a\n123")
    assert png_as_jpg is not None
    assert hub_router.validate_upload_file("data", "list.csv", b"a,b\x00c") is not None
    assert hub_router.validate_upload_file("photo", "empty.jpg", b"") is not None


def test_upload_validation_accepts_each_lane() -> None:
    assert hub_router.validate_upload_file("photo", "a.jpg", JPG_BYTES) is None
    assert hub_router.validate_upload_file("pdf", "catalog.pdf", PDF_BYTES) is None
    assert hub_router.validate_upload_file("data", "inci.csv", b"name,inci\nserum,Water") is None
    assert (
        hub_router.validate_upload_file("data", "spec.xlsx", b"PK\x03\x04" + b"0" * 32) is None
    )


def test_upload_validation_enforces_size_cap(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        hub_router,
        "settings",
        SimpleNamespace(partner_upload_max_bytes=10, partner_upload_dir=str(tmp_path)),
    )
    message = hub_router.validate_upload_file("photo", "big.jpg", JPG_BYTES)
    assert message is not None and "큽니다" in message


# ---------------------------------------------------------------------------
# partner flows with mocked persistence: isolation + leak prevention
# ---------------------------------------------------------------------------


def _wire_active_partner(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_active_by_token",
        lambda token: {"id": "tok-1", "partner_id": PARTNER_ID},
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_partner_by_id",
        lambda partner_id: {
            "id": partner_id,
            "company_name": "파넬",
            "contact_name": "김담당",
            "contact_email": "internal-contact@vendor.test",
            "internal_memo": "MUST NOT LEAK",
            "status": "active",
        },
    )
    monkeypatch.setattr(
        hub_router.partners_repository, "touch_last_seen", lambda token_id: None
    )


def test_hub_me_whitelists_fields(monkeypatch) -> None:
    _wire_active_partner(monkeypatch)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "list_uploads_for_partner",
        lambda partner_id: [
            {
                "id": UPLOAD_ID,
                "kind": "photo",
                "original_filename": "a.jpg",
                "content_type": "image/jpeg",
                "byte_size": 68,
                "sha256": "deadbeef",
                "status": "uploaded",
                "uploaded_at": "2026-07-12T10:00:00Z",
                "storage_path": "SECRET-PATH",
            }
        ],
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "list_asset_profiles_for_partner",
        lambda partner_id: [
            {
                "upload_id": UPLOAD_ID,
                "doc_type": "photo_asset",
                "status": "done",
                "confidence": 0.91,
                "summary_ko": "흰 배경 제품컷입니다.",
                "products_mentioned": [],
                "updated_at": "2026-07-12T10:05:00Z",
                "model": "SECRET-MODEL2",
                "error": "SECRET-ERROR",
            }
        ],
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "list_drafts_for_partner",
        lambda partner_id: [
            {
                "id": DRAFT_ID,
                "draft": {"product_name": "세럼"},
                "ai_meta": {
                    "mode": "dry_run",
                    "prompt_version": "partner_extract_v1",
                    "model": "SECRET-MODEL",
                    "field_confidence": {"product_name": 0.8},
                },
                "completeness": {"score": 70},
                "regulatory_flags": {"by_country": {}},
                "status": "ai_draft",
                "updated_at": "2026-07-12T10:00:00Z",
            }
        ],
    )
    response = client.get(f"/partner-hub/me?token={TOKEN}")
    assert response.status_code == 200
    body = response.json()
    assert body["hub"]["partner"]["company_name"] == "파넬"
    assert body["hub"]["disclaimer"] == REGULATORY_DISCLAIMER
    # v2: the AI analysis view is attached per upload, whitelisted.
    analysis = body["hub"]["uploads"][0]["analysis"]
    assert analysis["doc_type"] == "photo_asset"
    assert analysis["doc_type_label"] == "제품 사진"
    assert analysis["confidence"] == 0.91
    raw = response.text
    assert "MUST NOT LEAK" not in raw
    assert "SECRET-PATH" not in raw
    assert "SECRET-MODEL" not in raw
    assert "SECRET-ERROR" not in raw
    assert "internal-contact@vendor.test" not in raw
    assert "deadbeef" not in raw


def test_upload_happy_path_stores_and_sanitizes(monkeypatch, tmp_path) -> None:
    _wire_active_partner(monkeypatch)
    monkeypatch.setattr(
        hub_router,
        "settings",
        SimpleNamespace(partner_upload_max_bytes=15_000_000, partner_upload_dir=str(tmp_path)),
    )
    recorded: dict = {}
    enqueued: dict = {}

    def fake_record(payload: dict) -> dict:
        recorded.update(payload)
        return {
            "id": UPLOAD_ID,
            "kind": payload["kind"],
            "original_filename": payload["original_filename"],
            "byte_size": payload["byte_size"],
            "status": "uploaded",
            "uploaded_at": "2026-07-12T10:00:00Z",
        }

    monkeypatch.setattr(hub_router.partners_repository, "record_upload", fake_record)
    monkeypatch.setattr(
        hub_router,
        "_enqueue_ingest",
        lambda upload_id, partner_id: enqueued.update(
            {"upload_id": upload_id, "partner_id": partner_id}
        ),
    )
    response = client.post(
        f"/partner-hub/uploads?kind=photo&token={TOKEN}",
        files={"file": ("product.jpg", JPG_BYTES, "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["upload"]["kind"] == "photo"
    assert "storage_path" not in body["upload"]
    assert "sha256" not in body["upload"]
    # The original file was persisted verbatim under the partner's directory.
    stored = list(tmp_path.glob(f"{PARTNER_ID}/*.jpg"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == JPG_BYTES
    assert recorded["partner_id"] == PARTNER_ID
    # v2: every stored upload is queued for AI ingestion.
    assert enqueued == {"upload_id": UPLOAD_ID, "partner_id": PARTNER_ID}


def test_upload_rejected_lane_mismatch(monkeypatch, tmp_path) -> None:
    _wire_active_partner(monkeypatch)
    monkeypatch.setattr(
        hub_router,
        "settings",
        SimpleNamespace(partner_upload_max_bytes=15_000_000, partner_upload_dir=str(tmp_path)),
    )
    response = client.post(
        f"/partner-hub/uploads?kind=pdf&token={TOKEN}",
        files={"file": ("photo.jpg", JPG_BYTES, "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UPLOAD_REJECTED"


def test_extract_missing_upload_404(monkeypatch) -> None:
    _wire_active_partner(monkeypatch)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_uploads_for_partner",
        lambda partner_id, upload_ids: [],
    )
    response = client.post(
        f"/partner-hub/uploads/extract?token={TOKEN}", json={"upload_ids": [UPLOAD_ID]}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "UPLOAD_NOT_FOUND"


def test_extract_creates_enriched_draft(monkeypatch) -> None:
    _wire_active_partner(monkeypatch)
    created: dict = {}
    marked: dict = {}
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_uploads_for_partner",
        lambda partner_id, upload_ids: [
            {
                "id": UPLOAD_ID,
                "kind": "photo",
                "sha256": "abc",
                "original_filename": "a.jpg",
            }
        ],
    )

    def fake_create(payload: dict) -> dict:
        created.update(payload)
        return {
            "id": DRAFT_ID,
            "draft": payload["draft"],
            "ai_meta": payload["ai_meta"],
            "completeness": payload["completeness"],
            "regulatory_flags": payload["regulatory_flags"],
            "status": "ai_draft",
            "updated_at": "2026-07-12T10:00:00Z",
        }

    monkeypatch.setattr(hub_router.partners_repository, "create_draft", fake_create)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "mark_uploads_status",
        lambda upload_ids, status: marked.setdefault("call", (tuple(upload_ids), status)),
    )
    response = client.post(
        f"/partner-hub/uploads/extract?token={TOKEN}", json={"upload_ids": [UPLOAD_ID]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["draft"]["status"] == "ai_draft"
    assert body["draft"]["ai_meta"]["mode"] == "dry_run"
    assert body["pipeline"]["completeness"]["score"] > 0
    assert body["pipeline"]["regulatory"]["disclaimer"] == REGULATORY_DISCLAIMER
    assert created["draft"]["brand_name"] == "파넬"
    assert marked["call"] == ((UPLOAD_ID,), "extracted")


def _wire_editable_draft(monkeypatch, status: str = "ai_draft") -> dict:
    updates: dict = {}
    _wire_active_partner(monkeypatch)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_draft_for_partner",
        lambda draft_id, partner_id: {
            "id": draft_id,
            "partner_id": partner_id,
            "draft": _dry_run_draft(),
            "source_upload_ids": [UPLOAD_ID],
            "status": status,
        },
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_uploads_for_partner",
        lambda partner_id, upload_ids: [{"id": UPLOAD_ID, "kind": "photo"}],
    )

    def fake_update(**kwargs):
        updates.update(kwargs)
        return {
            "id": kwargs["draft_id"],
            "draft": kwargs["draft"],
            "ai_meta": None,
            "completeness": kwargs["completeness"],
            "regulatory_flags": kwargs["regulatory_flags"],
            "status": kwargs["status"],
            "updated_at": "2026-07-12T10:00:00Z",
        }

    monkeypatch.setattr(
        hub_router.partners_repository, "update_draft_content", fake_update
    )
    return updates


def test_draft_save_merges_only_editable_fields(monkeypatch) -> None:
    updates = _wire_editable_draft(monkeypatch)
    response = client.post(
        f"/partner-hub/drafts/{DRAFT_ID}?token={TOKEN}",
        json={
            "draft": {
                "product_name": "리뉴얼 세럼",
                "internal_hack": "MUST BE DROPPED",
            },
            "action": "save",
        },
    )
    assert response.status_code == 200
    assert updates["draft"]["product_name"] == "리뉴얼 세럼"
    assert "internal_hack" not in updates["draft"]
    assert updates["status"] == "ai_draft"


def test_draft_submit_with_blocking_issue_422(monkeypatch) -> None:
    _wire_editable_draft(monkeypatch)
    response = client.post(
        f"/partner-hub/drafts/{DRAFT_ID}?token={TOKEN}",
        json={"draft": {"product_name": ""}, "action": "submit"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "DRAFT_INCOMPLETE"


def test_draft_submit_sets_partner_confirmed(monkeypatch) -> None:
    updates = _wire_editable_draft(monkeypatch)
    response = client.post(
        f"/partner-hub/drafts/{DRAFT_ID}?token={TOKEN}",
        json={"draft": {}, "action": "submit"},
    )
    assert response.status_code == 200
    assert updates["status"] == "partner_confirmed"
    assert response.json()["draft"]["status"] == "partner_confirmed"


def test_draft_locked_after_approval_409(monkeypatch) -> None:
    _wire_editable_draft(monkeypatch, status="approved")
    response = client.post(
        f"/partner-hub/drafts/{DRAFT_ID}?token={TOKEN}",
        json={"draft": {"product_name": "변경 시도"}},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DRAFT_LOCKED"


# ---------------------------------------------------------------------------
# v2: the 'etc' lane accepts documents only (David 2026-07-12 — video deferred)
# ---------------------------------------------------------------------------

OLE_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 64
ZIP_BYTES = b"PK\x03\x04" + b"0" * 64


def test_etc_lane_accepts_documents() -> None:
    assert hub_router.validate_upload_file("etc", "intro.docx", ZIP_BYTES) is None
    assert hub_router.validate_upload_file("etc", "deck.pptx", ZIP_BYTES) is None
    assert hub_router.validate_upload_file("etc", "소개서.hwp", OLE_BYTES) is None
    assert hub_router.validate_upload_file("etc", "소개서.hwpx", ZIP_BYTES) is None
    assert hub_router.validate_upload_file("etc", "notes.txt", "메모입니다".encode("utf-8")) is None


def test_etc_lane_rejects_video_and_bad_magic() -> None:
    # Video stays out until David opts in (design §2).
    assert hub_router.validate_upload_file("etc", "clip.mp4", b"\x00\x00\x00\x18ftyp") is not None
    assert hub_router.validate_upload_file("etc", "malware.exe", b"MZ") is not None
    # Correct extension, wrong content.
    assert hub_router.validate_upload_file("etc", "fake.docx", b"NOTAZIP0") is not None
    assert hub_router.validate_upload_file("etc", "fake.hwp", b"NOTOLE00") is not None
    assert hub_router.validate_upload_file("etc", "binary.txt", b"a\x00b") is not None


# ---------------------------------------------------------------------------
# v2: AI ingestion — classification, gates, orchestrator
# ---------------------------------------------------------------------------

from app.partners import ingestion  # noqa: E402


def test_classify_dry_run_is_deterministic_and_hint_based() -> None:
    photo = {"kind": "photo", "original_filename": "shot.jpg", "sha256": "aa"}
    assert ingestion.classify_upload(photo)["doc_type"] == "photo_asset"

    catalog = {"kind": "pdf", "original_filename": "2026_Catalog_Spring.pdf", "sha256": "bb"}
    first = ingestion.classify_upload(catalog)
    second = ingestion.classify_upload(catalog)
    assert first == second
    assert first["doc_type"] == "product_catalog"
    assert first["mode"] == "dry_run"
    assert "드라이런" in first["summary_ko"]

    inci = {"kind": "data", "original_filename": "전성분_inci.csv", "sha256": "cc"}
    assert ingestion.classify_upload(inci)["doc_type"] == "ingredient_list"
    price = {"kind": "data", "original_filename": "공급가표.xlsx", "sha256": "dd"}
    assert ingestion.classify_upload(price)["doc_type"] == "price_list"
    other = {"kind": "etc", "original_filename": "zzz.txt", "sha256": "ee"}
    assert ingestion.classify_upload(other)["doc_type"] == "other"


def test_ingestion_live_gates_closed_by_default() -> None:
    assert ingestion.live_gates_open() is False


def test_ingestion_gates_require_provider_key(monkeypatch) -> None:
    monkeypatch.setattr(
        ingestion,
        "settings",
        SimpleNamespace(
            partner_ai_dry_run=False,
            allow_live_partner_ai_calls=True,
            partner_ai_provider="anthropic",
            anthropic_api_key="",
            gemini_api_key="ignored",
        ),
    )
    assert ingestion.live_gates_open() is False


def test_partner_ai_defaults_are_anthropic_opus() -> None:
    from app.core.config import settings as app_settings

    assert app_settings.partner_ai_provider == "anthropic"
    assert app_settings.partner_ai_model == "claude-opus-4-8"
    assert app_settings.partner_ai_escalation_model == ""


def test_job_handler_registered() -> None:
    from app.workers.job_handlers import JOB_HANDLERS

    assert "partner_asset_ingest" in JOB_HANDLERS


def _wire_ingestion_repo(monkeypatch, upload: dict | None) -> list[dict]:
    calls: list[dict] = []

    monkeypatch.setattr("app.repositories.partners.get_upload", lambda upload_id: upload)

    def fake_upsert(upload_id: str, partner_id: str, fields: dict) -> dict:
        calls.append(dict(fields))
        return {"upload_id": upload_id, "partner_id": partner_id, **fields}

    monkeypatch.setattr("app.repositories.partners.upsert_asset_profile", fake_upsert)
    return calls


def test_run_asset_ingestion_happy_path(monkeypatch) -> None:
    upload = {
        "id": UPLOAD_ID,
        "partner_id": PARTNER_ID,
        "kind": "pdf",
        "original_filename": "catalog.pdf",
        "sha256": "abc",
        "storage_path": "missing.pdf",
    }
    calls = _wire_ingestion_repo(monkeypatch, upload)
    profile = ingestion.run_asset_ingestion(UPLOAD_ID)
    assert calls[0] == {"status": "processing"}
    assert calls[-1]["status"] == "done"
    assert calls[-1]["doc_type"] == "product_catalog"
    assert calls[-1]["extracted"]["schema_version"] == 1
    assert calls[-1]["prompt_version"] == ingestion.PROMPT_VERSION
    assert profile["status"] == "done"


def test_run_asset_ingestion_low_confidence_live_needs_review(monkeypatch) -> None:
    upload = {
        "id": UPLOAD_ID,
        "partner_id": PARTNER_ID,
        "kind": "pdf",
        "original_filename": "scan.pdf",
        "sha256": "abc",
    }
    calls = _wire_ingestion_repo(monkeypatch, upload)
    monkeypatch.setattr(
        ingestion,
        "classify_upload",
        lambda u: {
            "doc_type": "ingredient_list",
            "language": "ko",
            "confidence": 0.4,
            "summary_ko": "판독이 어려운 스캔본",
            "products_mentioned": [],
            "mode": "live",
            "model": "claude-opus-4-8",
            "usage": None,
        },
    )
    ingestion.run_asset_ingestion(UPLOAD_ID)
    assert calls[-1]["doc_type"] == "needs_review"
    assert calls[-1]["extracted"] is None


def test_run_asset_ingestion_failure_marks_failed(monkeypatch) -> None:
    upload = {"id": UPLOAD_ID, "partner_id": PARTNER_ID, "kind": "pdf", "sha256": "x"}
    calls = _wire_ingestion_repo(monkeypatch, upload)

    def boom(u):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(ingestion, "classify_upload", boom)
    try:
        ingestion.run_asset_ingestion(UPLOAD_ID)
        raise AssertionError("expected the ingestion error to propagate")
    except RuntimeError:
        pass
    assert calls[-1]["status"] == "failed"
    assert "provider exploded" in calls[-1]["error"]


def test_run_asset_ingestion_unknown_upload(monkeypatch) -> None:
    _wire_ingestion_repo(monkeypatch, None)
    try:
        ingestion.run_asset_ingestion(UPLOAD_ID)
        raise AssertionError("expected ValueError for unknown upload")
    except ValueError:
        pass
