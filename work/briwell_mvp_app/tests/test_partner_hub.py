import io
import zipfile
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


def _zip_bytes(*names: str) -> bytes:
    """A real (readable) ZIP container, as OOXML validation now parses it."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names or ("[Content_Types].xml",):
            archive.writestr(name, "stub")
    return buffer.getvalue()


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
# P3: CosIng inventory layer under the curated seed
# ---------------------------------------------------------------------------


def test_cosing_seed_ships_the_full_inventory() -> None:
    from app.partners.cosing_data import cosing_entries

    entries = cosing_entries()
    # The official 2020-12 export carries ~28.7k unique INCI names; a sharp
    # drop would mean the repo seed file was truncated.
    assert len(entries) > 25_000
    assert "COCAMIDOPROPYL BETAINE" in entries


def test_cosing_fallback_matches_uncurated_ingredient() -> None:
    # Not in the curated seed; previously unmatched, now resolved by CosIng.
    result = normalize_ingredient("Cocamidopropyl Betaine")
    assert result["match_status"] == "exact"
    assert result["inci_name"] == "COCAMIDOPROPYL BETAINE"
    assert result["functions"]  # CosIng publishes functions for it


def test_curated_seed_wins_over_cosing() -> None:
    # CosIng lists AQUA as its own INCI name, but the curated alias mapping
    # (Aqua -> Water) must keep winning — curated canon is authoritative.
    result = normalize_ingredient("Aqua")
    assert result["match_status"] == "alias"
    assert result["inci_name"] == "Water"
    # And the curated canonical keeps its curated casing/functions.
    assert normalize_ingredient("Niacinamide")["inci_name"] == "Niacinamide"


def test_normalize_list_reports_dictionary_meta() -> None:
    result = normalize_ingredient_list(["Water"])
    meta = result["dictionary"]
    assert meta["curated"] > 50
    assert meta["cosing"] > 25_000
    assert meta["cosing_version"].startswith("cosing-inventory")


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
# P1 token hardening: sha256 at rest, expiry, Authorization header transport
# ---------------------------------------------------------------------------


def test_hash_token_is_sha256_hex() -> None:
    import hashlib

    from app.repositories import partners as partners_repository

    assert partners_repository.hash_token(TOKEN) == hashlib.sha256(
        TOKEN.encode("utf-8")
    ).hexdigest()


def test_get_active_by_token_queries_digest_and_expiry(monkeypatch) -> None:
    from app.repositories import partners as partners_repository

    captured: dict = {}

    def fake_fetch_one(query: str, params: dict) -> None:
        captured["query"] = query
        captured["params"] = params
        return None

    monkeypatch.setattr(partners_repository, "fetch_one", fake_fetch_one)
    partners_repository.get_active_by_token(TOKEN)
    # The plaintext token never reaches SQL — only its digest does.
    assert captured["params"] == {"token_sha256": partners_repository.hash_token(TOKEN)}
    assert TOKEN not in captured["query"]
    assert "token_sha256" in captured["query"]
    assert "expires_at > now()" in captured["query"]


def test_issue_token_passes_ttl_and_returns_expiry(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_partner_by_id",
        lambda partner_id: {"id": partner_id, "company_name": "파넬", "status": "active"},
    )
    captured: dict = {}

    def fake_issue(partner_id: str, token: str, ttl_days: int) -> dict:
        captured.update({"partner_id": partner_id, "token": token, "ttl_days": ttl_days})
        return {"id": "tok-1", "expires_at": "2026-10-10T00:00:00Z"}

    monkeypatch.setattr(hub_router.partners_repository, "issue_token", fake_issue)
    response = client.post("/partners/tokens", headers=ADMIN, json={"partner_id": PARTNER_ID})
    assert response.status_code == 200
    body = response.json()
    assert captured["ttl_days"] == 90
    assert body["expires_at"] == "2026-10-10T00:00:00Z"
    assert body["token"] == captured["token"]


def test_hub_accepts_authorization_header(monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)

    def fake_get_active(token: str) -> dict:
        seen["token"] = token
        return {"id": "tok-1", "partner_id": PARTNER_ID}

    monkeypatch.setattr(hub_router.partners_repository, "get_active_by_token", fake_get_active)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_partner_by_id",
        lambda partner_id: {"id": partner_id, "company_name": "파넬", "status": "active"},
    )
    monkeypatch.setattr(hub_router.partners_repository, "touch_last_seen", lambda token_id: None)
    monkeypatch.setattr(
        hub_router.partners_repository, "list_uploads_for_partner", lambda partner_id: []
    )
    monkeypatch.setattr(
        hub_router.partners_repository, "list_drafts_for_partner", lambda partner_id: []
    )
    monkeypatch.setattr(
        hub_router.partners_repository, "list_asset_profiles_for_partner", lambda partner_id: []
    )
    response = client.get("/partner-hub/me", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert seen["token"] == TOKEN


def test_hub_token_missing_everywhere_422() -> None:
    response = client.get("/partner-hub/me")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PARTNER_TOKEN_MISSING"


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
    assert hub_router.validate_upload_file("data", "spec.xlsx", _zip_bytes()) is None


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

    monkeypatch.setattr(
        hub_router.partners_repository, "get_upload_by_sha", lambda partner_id, sha256: None
    )
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
# P5+P10: operator draft detail, attention queue, re-analyze
# ---------------------------------------------------------------------------


def test_draft_detail_db_off_503_and_viewer_403() -> None:
    assert client.get(f"/partners/drafts/{DRAFT_ID}", headers=VIEWER).status_code == 403
    response = client.get(f"/partners/drafts/{DRAFT_ID}", headers=OPERATOR)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "PARTNER_HUB_UNAVAILABLE"


def test_draft_detail_unknown_and_invalid_id_404(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(hub_router.partners_repository, "get_draft", lambda draft_id: None)
    assert client.get(f"/partners/drafts/{DRAFT_ID}", headers=OPERATOR).status_code == 404
    assert client.get("/partners/drafts/not-a-uuid", headers=OPERATOR).status_code == 404


def test_draft_detail_returns_sources_profiles_and_decisions(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_draft",
        lambda draft_id: {
            "id": draft_id,
            "partner_id": PARTNER_ID,
            "source_upload_ids": [UPLOAD_ID],
            "draft": {"product_name": "수분 세럼"},
            "ai_meta": {"mode": "dry_run"},
            "completeness": {"score": 80},
            "regulatory_flags": {"by_country": {}},
            "status": "partner_confirmed",
            "promoted_product_id": None,
            "created_at": "2026-07-12T10:00:00Z",
            "updated_at": "2026-07-12T10:05:00Z",
        },
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_partner_by_id",
        lambda partner_id: {"id": partner_id, "company_name": "파넬", "status": "active"},
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_uploads_for_partner",
        lambda partner_id, upload_ids: [
            {
                "id": UPLOAD_ID,
                "kind": "pdf",
                "original_filename": "catalog.pdf",
                "byte_size": 100,
                "status": "extracted",
                "uploaded_at": "2026-07-12T09:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_profiles_for_uploads",
        lambda upload_ids: [
            {
                "upload_id": UPLOAD_ID,
                "doc_type": "product_catalog",
                "status": "done",
                "confidence": 0.9,
                "summary_ko": "카탈로그입니다.",
                "products_mentioned": ["수분 세럼"],
                "extracted": {"schema_version": 1},
                "error": None,
                "model": "claude-opus-4-8",
                "prompt_version": "partner_ingest_v1",
                "updated_at": "2026-07-12T09:10:00Z",
            }
        ],
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "list_review_decisions",
        lambda draft_id: [
            {
                "decision": "rejected",
                "reason": "성분 재확인",
                "decided_by": "ops@briwell.test",
                "decided_at": "2026-07-11T10:00:00Z",
            }
        ],
    )
    response = client.get(f"/partners/drafts/{DRAFT_ID}", headers=OPERATOR)
    assert response.status_code == 200
    body = response.json()
    assert body["draft"]["draft"]["product_name"] == "수분 세럼"
    assert body["partner"]["company_name"] == "파넬"
    assert body["source_uploads"][0]["profile"]["doc_type_label"] == "제품 카탈로그"
    assert body["decisions"][0]["decision"] == "rejected"
    assert body["disclaimer"] == REGULATORY_DISCLAIMER


def test_attention_queue_db_off_empty_and_labels(monkeypatch) -> None:
    response = client.get("/partners/asset-profiles/attention", headers=OPERATOR)
    assert response.status_code == 200
    assert response.json()["items"] == []

    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "list_attention_profiles",
        lambda: [
            {
                "upload_id": UPLOAD_ID,
                "partner_id": PARTNER_ID,
                "doc_type": "needs_review",
                "status": "done",
                "confidence": 0.4,
                "summary_ko": "판독 어려움",
                "error": None,
                "model": None,
                "updated_at": "2026-07-12T09:00:00Z",
                "original_filename": "scan.pdf",
                "kind": "pdf",
                "uploaded_at": "2026-07-12T08:00:00Z",
                "company_name": "파넬",
            }
        ],
    )
    response = client.get("/partners/asset-profiles/attention", headers=OPERATOR)
    items = response.json()["items"]
    assert items[0]["doc_type_label"] == "확인 필요"
    assert items[0]["company_name"] == "파넬"


def test_reanalyze_db_off_validated_only() -> None:
    response = client.post(f"/partners/uploads/{UPLOAD_ID}/reanalyze", headers=OPERATOR)
    assert response.status_code == 200
    assert response.json()["status"] == "validated_not_persisted"


def test_reanalyze_resets_profile_and_enqueues(monkeypatch) -> None:
    from contextlib import contextmanager

    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_upload",
        lambda upload_id: {"id": upload_id, "partner_id": PARTNER_ID},
    )
    calls: dict = {}

    def fake_upsert(upload_id: str, partner_id: str, fields: dict) -> dict:
        calls["upsert"] = (upload_id, partner_id, fields)
        return {"upload_id": upload_id}

    monkeypatch.setattr(hub_router.partners_repository, "upsert_asset_profile", fake_upsert)

    @contextmanager
    def fake_connection():
        yield "conn"

    monkeypatch.setattr(hub_router, "connection", fake_connection)
    monkeypatch.setattr(
        hub_router,
        "enqueue_job",
        lambda conn, job_type, payload: calls.setdefault("job", (job_type, payload)) or 7,
    )
    response = client.post(f"/partners/uploads/{UPLOAD_ID}/reanalyze", headers=OPERATOR)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert calls["upsert"] == (UPLOAD_ID, PARTNER_ID, {"status": "pending", "error": None})
    assert calls["job"] == ("partner_asset_ingest", {"upload_id": UPLOAD_ID})


def test_reanalyze_unknown_upload_404(monkeypatch) -> None:
    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    monkeypatch.setattr(hub_router.partners_repository, "get_upload", lambda upload_id: None)
    response = client.post(f"/partners/uploads/{UPLOAD_ID}/reanalyze", headers=OPERATOR)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# v2: the 'etc' lane accepts documents only (David 2026-07-12 — video deferred)
# ---------------------------------------------------------------------------

OLE_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 64


def test_etc_lane_accepts_documents() -> None:
    assert hub_router.validate_upload_file("etc", "intro.docx", _zip_bytes()) is None
    assert hub_router.validate_upload_file("etc", "deck.pptx", _zip_bytes()) is None
    assert hub_router.validate_upload_file("etc", "소개서.hwp", OLE_BYTES) is None
    assert hub_router.validate_upload_file("etc", "소개서.hwpx", _zip_bytes()) is None
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
# P2: macro rejection + unreadable containers + per-partner dedup
# ---------------------------------------------------------------------------


def test_ooxml_with_macro_rejected_in_every_zip_lane() -> None:
    macro_doc = _zip_bytes("word/document.xml", "word/vbaProject.bin")
    for kind, filename in (
        ("etc", "quote.docx"),
        ("etc", "deck.pptx"),
        ("etc", "intro.hwpx"),
        ("data", "spec.xlsx"),
    ):
        message = hub_router.validate_upload_file(kind, filename, macro_doc)
        assert message is not None and "매크로" in message


def test_ooxml_macro_detection_is_case_insensitive() -> None:
    macro_doc = _zip_bytes("xl/VBAProject.BIN")
    assert hub_router.validate_upload_file("data", "spec.xlsx", macro_doc) is not None


def test_ooxml_unreadable_zip_rejected() -> None:
    # PK magic but not a parseable archive: claimed OOXML, fails inspection.
    message = hub_router.validate_upload_file("etc", "broken.docx", b"PK\x03\x04" + b"0" * 64)
    assert message is not None and "압축" in message


def test_ooxml_without_macro_accepted() -> None:
    clean = _zip_bytes("word/document.xml")
    assert hub_router.validate_upload_file("etc", "quote.docx", clean) is None


def test_upload_same_sha_deduplicated(monkeypatch, tmp_path) -> None:
    _wire_active_partner(monkeypatch)
    monkeypatch.setattr(
        hub_router,
        "settings",
        SimpleNamespace(partner_upload_max_bytes=15_000_000, partner_upload_dir=str(tmp_path)),
    )
    existing = {
        "id": UPLOAD_ID,
        "kind": "photo",
        "original_filename": "product.jpg",
        "byte_size": len(JPG_BYTES),
        "status": "uploaded",
        "uploaded_at": "2026-07-12T10:00:00Z",
    }
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_upload_by_sha",
        lambda partner_id, sha256: existing,
    )

    def must_not_record(payload: dict) -> dict:
        raise AssertionError("duplicate upload must not create a new record")

    monkeypatch.setattr(hub_router.partners_repository, "record_upload", must_not_record)
    monkeypatch.setattr(
        hub_router,
        "_enqueue_ingest",
        lambda upload_id, partner_id: (_ for _ in ()).throw(
            AssertionError("duplicate upload must not re-enqueue ingestion")
        ),
    )
    response = client.post(
        f"/partner-hub/uploads?kind=photo&token={TOKEN}",
        files={"file": ("product_again.jpg", JPG_BYTES, "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "duplicate"
    assert body["upload"]["id"] == UPLOAD_ID
    # No new file lands on disk for a duplicate.
    assert list(tmp_path.glob("**/*.jpg")) == []


# ---------------------------------------------------------------------------
# P6: authenticated file serving (partner ownership + operator RBAC)
# ---------------------------------------------------------------------------


def _stored_upload_row(tmp_path, filename: str = "제품사진.jpg") -> dict:
    stored = tmp_path / "stored.jpg"
    stored.write_bytes(JPG_BYTES)
    return {
        "id": UPLOAD_ID,
        "partner_id": PARTNER_ID,
        "kind": "photo",
        "original_filename": filename,
        "storage_path": str(stored),
    }


def test_partner_file_serving_happy_path(monkeypatch, tmp_path) -> None:
    _wire_active_partner(monkeypatch)
    row = _stored_upload_row(tmp_path)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_uploads_for_partner",
        lambda partner_id, upload_ids: [row] if upload_ids == [UPLOAD_ID] else [],
    )
    response = client.get(
        f"/partner-hub/uploads/{UPLOAD_ID}/file",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 200
    assert response.content == JPG_BYTES
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "private, no-store"


def test_partner_file_serving_other_partners_upload_404(monkeypatch) -> None:
    _wire_active_partner(monkeypatch)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_uploads_for_partner",
        lambda partner_id, upload_ids: [],
    )
    response = client.get(f"/partner-hub/uploads/{UPLOAD_ID}/file?token={TOKEN}")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "UPLOAD_NOT_FOUND"


def test_partner_file_serving_invalid_uuid_404(monkeypatch) -> None:
    _wire_active_partner(monkeypatch)
    response = client.get(f"/partner-hub/uploads/not-a-uuid/file?token={TOKEN}")
    assert response.status_code == 404


def test_partner_file_serving_missing_file_404(monkeypatch, tmp_path) -> None:
    _wire_active_partner(monkeypatch)
    row = _stored_upload_row(tmp_path)
    row["storage_path"] = str(tmp_path / "gone.jpg")
    monkeypatch.setattr(
        hub_router.partners_repository,
        "get_uploads_for_partner",
        lambda partner_id, upload_ids: [row],
    )
    response = client.get(f"/partner-hub/uploads/{UPLOAD_ID}/file?token={TOKEN}")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "FILE_MISSING"


def test_operator_file_serving_rbac_and_happy_path(monkeypatch, tmp_path) -> None:
    response = client.get(f"/partners/uploads/{UPLOAD_ID}/file", headers=VIEWER)
    assert response.status_code == 403

    # DB off: honest 503 rather than pretending the file store works.
    response = client.get(f"/partners/uploads/{UPLOAD_ID}/file", headers=OPERATOR)
    assert response.status_code == 503

    monkeypatch.setattr(hub_router, "database_enabled", lambda: True)
    row = _stored_upload_row(tmp_path)
    monkeypatch.setattr(hub_router.partners_repository, "get_upload", lambda upload_id: row)
    response = client.get(f"/partners/uploads/{UPLOAD_ID}/file", headers=OPERATOR)
    assert response.status_code == 200
    assert response.content == JPG_BYTES


# ---------------------------------------------------------------------------
# P12: server-side text extraction for ZIP-based documents
# ---------------------------------------------------------------------------

from app.partners.text_extraction import extract_document_text  # noqa: E402


def _zip_with_parts(parts: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _write(tmp_path, name: str, data: bytes):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_extract_docx_text(tmp_path) -> None:
    data = _zip_with_parts(
        {
            "word/document.xml": (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>시카마니드 수분 진정 세럼</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>전성분: Water, Niacinamide</w:t></w:r></w:p></w:body></w:document>"
            )
        }
    )
    result = extract_document_text(_write(tmp_path, "intro.docx", data), "intro.docx")
    assert result is not None
    assert "시카마니드 수분 진정 세럼" in result["text"]
    assert "Niacinamide" in result["text"]
    assert result["truncated"] is False


def test_extract_pptx_slides_in_order(tmp_path) -> None:
    slide = (
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<a:t>{text}</a:t></p:sld>"
    )
    data = _zip_with_parts(
        {
            "ppt/slides/slide2.xml": slide.replace("{text}", "두번째 슬라이드"),
            "ppt/slides/slide1.xml": slide.replace("{text}", "회사 소개"),
        }
    )
    result = extract_document_text(_write(tmp_path, "deck.pptx", data), "deck.pptx")
    assert result is not None
    assert result["text"].index("회사 소개") < result["text"].index("두번째 슬라이드")


def test_extract_hwpx_and_xlsx(tmp_path) -> None:
    hwpx = _zip_with_parts(
        {
            "Contents/section0.xml": (
                '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
                'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">'
                "<hp:p><hp:run><hp:t>한글 소개서 본문입니다</hp:t></hp:run></hp:p></hs:sec>"
            )
        }
    )
    result = extract_document_text(_write(tmp_path, "소개서.hwpx", hwpx), "소개서.hwpx")
    assert result is not None and "한글 소개서 본문입니다" in result["text"]

    xlsx = _zip_with_parts(
        {
            "xl/sharedStrings.xml": (
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                "<si><t>제품명</t></si><si><t>수분 진정 세럼</t></si>"
                "<si><t>공급가</t></si></sst>"
            )
        }
    )
    result = extract_document_text(_write(tmp_path, "가격표.xlsx", xlsx), "가격표.xlsx")
    assert result is not None and "수분 진정 세럼" in result["text"]


def test_extract_out_of_scope_and_broken_inputs_return_none(tmp_path) -> None:
    # .hwp (OLE) is deliberately out of scope — metadata-only path stays.
    assert extract_document_text(_write(tmp_path, "doc.hwp", OLE_BYTES), "doc.hwp") is None
    # Corrupt zip: honest None, never an exception.
    broken = _write(tmp_path, "broken.docx", b"PK\x03\x04" + b"0" * 32)
    assert extract_document_text(broken, "broken.docx") is None
    # Valid zip without text parts.
    empty = _write(tmp_path, "empty.docx", _zip_with_parts({"word/styles.xml": "<a/>"}))
    assert extract_document_text(empty, "empty.docx") is None
    # Missing file.
    assert extract_document_text(tmp_path / "gone.docx", "gone.docx") is None


def test_extract_skips_dtd_carrying_parts(tmp_path) -> None:
    # Office XML never ships DTDs; entity expansion is a hostile pattern.
    hostile = _zip_with_parts(
        {
            "word/document.xml": (
                '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]>'
                '<w:document xmlns:w="http://x"><w:t>&a;</w:t></w:document>'
            )
        }
    )
    assert extract_document_text(_write(tmp_path, "evil.docx", hostile), "evil.docx") is None


def test_extract_truncates_huge_text(tmp_path) -> None:
    big = "가" * 60_000
    data = _zip_with_parts(
        {
            "word/document.xml": (
                '<w:document xmlns:w="http://x"><w:t>' + big + "</w:t></w:document>"
            )
        }
    )
    result = extract_document_text(_write(tmp_path, "big.docx", data), "big.docx")
    assert result is not None
    assert result["truncated"] is True
    assert len(result["text"]) == 40_000


def test_gemini_upload_part_inlines_extracted_xlsx(tmp_path) -> None:
    xlsx = _zip_with_parts(
        {
            "xl/sharedStrings.xml": (
                "<sst><si><t>수분 진정 세럼</t></si><si><t>12500</t></si></sst>"
            )
        }
    )
    path = _write(tmp_path, "가격표.xlsx", xlsx)
    upload = {
        "kind": "data",
        "original_filename": "가격표.xlsx",
        "storage_path": str(path),
    }
    part, skip_reason = extraction_module._upload_part(upload)
    assert skip_reason is None
    assert part is not None and "수분 진정 세럼" in part["text"]
    assert "서버 추출 텍스트" in part["text"]


def test_anthropic_parts_inline_extracted_docx_with_caveat(tmp_path) -> None:
    docx = _zip_with_parts(
        {
            "word/document.xml": '<w:document xmlns:w="http://x"><w:t>브랜드 소개 본문</w:t></w:document>'
        }
    )
    path = _write(tmp_path, "intro.docx", docx)
    upload = {
        "kind": "etc",
        "original_filename": "intro.docx",
        "storage_path": str(path),
    }
    parts, caveat = ingestion._anthropic_content_parts(upload)
    assert any("브랜드 소개 본문" in str(part.get("text", "")) for part in parts)
    assert caveat is not None and "서버 추출 텍스트" in caveat


def test_anthropic_parts_hwp_stays_metadata_only(tmp_path) -> None:
    path = _write(tmp_path, "doc.hwp", OLE_BYTES)
    upload = {"kind": "etc", "original_filename": "doc.hwp", "storage_path": str(path)}
    parts, caveat = ingestion._anthropic_content_parts(upload)
    assert len(parts) == 1  # header only, no content part
    assert caveat is not None and "추출하지 못해" in caveat


# ---------------------------------------------------------------------------
# P7: assemble — catalog/ingredient/price profiles -> N drafts
# ---------------------------------------------------------------------------

from app.partners.assemble import assemble_proposals  # noqa: E402


def _profile(upload_id: str, doc_type: str, extracted: dict | None, mentioned=()) -> dict:
    return {
        "upload_id": upload_id,
        "doc_type": doc_type,
        "status": "done",
        "extracted": extracted,
        "products_mentioned": list(mentioned),
    }


def _assemble_fixture_profiles() -> list[dict]:
    return [
        _profile(
            "u-cat",
            "product_catalog",
            {
                "schema_version": 1,
                "products": [
                    {"product_name": "수분 진정 세럼", "size": "50ml"},
                    {"product_name": "데일리 선스크린 SPF50+", "size": ""},
                ],
            },
        ),
        _profile(
            "u-inci",
            "ingredient_list",
            {
                "schema_version": 1,
                "products": [
                    {
                        "product_name": "수분 진정 세럼",
                        "ingredients_raw": ["Water", "Glycerin", "Niacinamide"],
                    }
                ],
            },
        ),
        _profile(
            "u-price",
            "price_list",
            {
                "schema_version": 1,
                "rows": [{"product_name": "데일리 선스크린 SPF50+", "size": "50ml"}],
            },
        ),
        _profile("u-photo", "photo_asset", {"schema_version": 1}, mentioned=["수분 진정 세럼"]),
    ]


def test_assemble_merges_profiles_by_product_name() -> None:
    result = assemble_proposals(_assemble_fixture_profiles(), "파넬", existing_draft_names=[])
    assert result["catalog_profile_count"] == 1
    assert result["skipped_existing"] == []
    proposals = {p["draft"]["product_name"]: p for p in result["proposals"]}
    assert set(proposals) == {"수분 진정 세럼", "데일리 선스크린 SPF50+"}

    serum = proposals["수분 진정 세럼"]
    assert serum["draft"]["ingredients_raw"] == ["Water", "Glycerin", "Niacinamide"]
    assert serum["draft"]["size"] == "50ml"
    assert serum["photo_count"] == 1
    assert set(serum["source_upload_ids"]) == {"u-cat", "u-inci", "u-photo"}
    assert serum["draft"]["brand_name"] == "파넬"
    # Honesty: assemble never guesses the category.
    assert serum["draft"]["product_category"] == ""
    assert "자동 조립" in serum["draft"]["notes"]

    sunscreen = proposals["데일리 선스크린 SPF50+"]
    assert sunscreen["draft"]["size"] == "50ml"  # filled from the price list
    assert sunscreen["photo_count"] == 0
    assert set(sunscreen["source_upload_ids"]) == {"u-cat", "u-price"}


def test_assemble_skips_existing_drafts_and_ignores_non_catalog_products() -> None:
    result = assemble_proposals(
        _assemble_fixture_profiles(), "파넬", existing_draft_names=["수분 진정 세럼"]
    )
    names = [p["draft"]["product_name"] for p in result["proposals"]]
    assert names == ["데일리 선스크린 SPF50+"]
    assert result["skipped_existing"] == ["수분 진정 세럼"]

    # An ingredient list alone must not invent a product draft.
    only_inci = [
        _profile(
            "u-inci",
            "ingredient_list",
            {"schema_version": 1, "products": [{"product_name": "유령 제품", "ingredients_raw": ["Water"]}]},
        )
    ]
    result = assemble_proposals(only_inci, "파넬", existing_draft_names=[])
    assert result["proposals"] == []
    assert result["catalog_profile_count"] == 0


def test_hub_assemble_endpoint_creates_enriched_drafts(monkeypatch) -> None:
    _wire_active_partner(monkeypatch)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "list_done_profiles_for_partner",
        lambda partner_id: _assemble_fixture_profiles(),
    )
    monkeypatch.setattr(
        hub_router.partners_repository,
        "list_drafts_for_partner",
        lambda partner_id: [
            {"draft": {"product_name": "데일리 선스크린 SPF50+"}, "status": "ai_draft"}
        ],
    )
    created: list = []
    marked: dict = {}

    def fake_create(payload: dict) -> dict:
        created.append(payload)
        return {
            "id": f"draft-{len(created)}",
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
    response = client.post(f"/partner-hub/assemble?token={TOKEN}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["created"]) == 1
    assert body["created"][0]["draft"]["product_name"] == "수분 진정 세럼"
    assert body["created"][0]["ai_meta"]["mode"] == "assembled"
    assert body["skipped_existing"] == ["데일리 선스크린 SPF50+"]
    assert created[0]["completeness"]["score"] > 0
    assert marked["call"] == (("u-cat", "u-inci", "u-photo"), "extracted")


def test_hub_assemble_without_catalog_profiles_422(monkeypatch) -> None:
    _wire_active_partner(monkeypatch)
    monkeypatch.setattr(
        hub_router.partners_repository,
        "list_done_profiles_for_partner",
        lambda partner_id: [],
    )
    monkeypatch.setattr(
        hub_router.partners_repository, "list_drafts_for_partner", lambda partner_id: []
    )
    response = client.post(f"/partner-hub/assemble?token={TOKEN}")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ASSEMBLE_NO_CATALOG"


def test_hub_assemble_without_database_503() -> None:
    response = client.post(f"/partner-hub/assemble?token={TOKEN}")
    assert response.status_code == 503


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
