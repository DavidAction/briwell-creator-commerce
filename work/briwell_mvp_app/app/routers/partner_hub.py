"""Brand Partner Hub (briefing 0.0.19 plan, David-approved 2026-07-12).

Two surfaces, mirroring the creator portal split:

* Operator side (RBAC-gated, ``/partners``): register partners, issue/rotate
  and revoke access tokens, review the queue, approve/reject drafts. Approval
  promotes a draft into the existing ``product_catalog`` — the human gate.
* Partner side (token-gated, ``/partner-hub``): a brand client sees only its
  own data (field-whitelisted; ``internal_memo`` and other partners' data are
  structurally excluded), uploads files in three separated lanes
  (photo / pdf / data — David's decision), runs AI extraction (dry-run gated),
  edits and submits drafts.

DB-off behavior: operator endpoints keep the ``validated_not_persisted``
convention; the partner side is a consumer surface and fails loudly with
503 PARTNER_HUB_UNAVAILABLE (same reasoning as the creator portal).
"""

import hashlib
import secrets
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import UserContext, require_roles
from app.core.config import settings
from app.core.db import database_enabled
from app.partners.extraction import PartnerAIGateClosed, run_extraction
from app.partners.ingredient_data import REGULATORY_DISCLAIMER
from app.partners.pipeline import enrich_draft
from app.partners.validation import SUPPORTED_CATEGORIES
from app.repositories import partners as partners_repository
from app.repositories import products as products_repository

operator_router = APIRouter(prefix="/partners", tags=["partner-hub"])
partner_router = APIRouter(prefix="/partner-hub", tags=["partner-hub"])

TOKEN_BYTES = 24
UPLOAD_CHUNK_BYTES = 1024 * 1024

# Which product fields a partner may set on a draft. Anything else in the
# request body is dropped, so a partner cannot inject internal keys.
EDITABLE_DRAFT_FIELDS = (
    "product_name",
    "brand_name",
    "product_category",
    "size",
    "ingredients_raw",
    "key_claims_allowed",
    "claims_candidates",
    "country_availability",
    "notes",
)

_LAUNCH_COUNTRIES = {"MX", "PE", "EC"}


# --- upload validation (exposed for tests) -------------------------------------

KIND_EXTENSIONS = {
    "photo": {".jpg", ".jpeg", ".png", ".webp"},
    "pdf": {".pdf"},
    "data": {".csv", ".xlsx"},
}


def validate_upload_file(kind: str, filename: str, content: bytes) -> str | None:
    """Return a Korean rejection message, or None when the file is acceptable."""

    suffix = Path(filename or "").suffix.lower()
    allowed = KIND_EXTENSIONS.get(kind)
    if allowed is None:
        return "kind는 photo/pdf/data 중 하나여야 합니다."
    if suffix not in allowed:
        expected = ", ".join(sorted(allowed))
        return f"'{kind}' 레인은 {expected} 파일만 받습니다."
    if not content:
        return "빈 파일입니다."
    if len(content) > settings.partner_upload_max_bytes:
        limit_mb = settings.partner_upload_max_bytes / 1_000_000
        return f"파일이 너무 큽니다 (최대 {limit_mb:.0f}MB)."

    if suffix in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        return "JPG 형식이 아닙니다 (파일 내용 검사 실패)."
    if suffix == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG 형식이 아닙니다 (파일 내용 검사 실패)."
    if suffix == ".webp" and not (content[:4] == b"RIFF" and content[8:12] == b"WEBP"):
        return "WEBP 형식이 아닙니다 (파일 내용 검사 실패)."
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        return "PDF 형식이 아닙니다 (파일 내용 검사 실패)."
    if suffix == ".xlsx" and not content.startswith(b"PK\x03\x04"):
        return "XLSX 형식이 아닙니다 (파일 내용 검사 실패)."
    if suffix == ".csv":
        head = content[:4096]
        if b"\x00" in head:
            return "CSV 형식이 아닙니다 (이진 데이터가 포함됨)."
    return None


# --- operator side --------------------------------------------------------------

class PartnerCreateRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    contact_name: str | None = None
    contact_email: str | None = None
    internal_memo: str | None = None


class PartnerTokenRequest(BaseModel):
    partner_id: str = Field(min_length=1)


class ReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = None


@operator_router.post("")
def create_partner(
    payload: PartnerCreateRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    if not database_enabled():
        return {"status": "validated_not_persisted", "partner": payload.model_dump()}
    created = partners_repository.create_partner(payload.model_dump())
    return {"status": "persisted", "partner": created}


@operator_router.get("")
def list_partners(
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    if not database_enabled():
        return {"items": []}
    return {"items": partners_repository.list_partners()}


@operator_router.post("/tokens")
def issue_partner_token(
    payload: PartnerTokenRequest,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    """Issue (or rotate) the hub access token for a partner company."""

    token = secrets.token_urlsafe(TOKEN_BYTES)
    if not database_enabled():
        return {
            "status": "validated_not_persisted",
            "token": token,
            "partner_id": payload.partner_id,
        }
    partner = partners_repository.get_partner_by_id(payload.partner_id)
    if partner is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PARTNER_NOT_FOUND", "message": "partner_id does not exist."},
        )
    created = partners_repository.issue_token(payload.partner_id, token)
    return {
        "status": "persisted",
        "token": token,
        "token_id": str(created["id"]),
        "partner_id": payload.partner_id,
    }


@operator_router.delete("/tokens/{partner_id}")
def revoke_partner_tokens(
    partner_id: str,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    if not database_enabled():
        return {"status": "validated_not_persisted", "revoked": 0}
    revoked = partners_repository.revoke_for_partner(partner_id)
    return {"status": "persisted", "revoked": revoked}


@operator_router.get("/review-queue")
def review_queue(
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    if not database_enabled():
        return {"items": [], "disclaimer": REGULATORY_DISCLAIMER}
    items = [
        {
            "draft_id": str(row["id"]),
            "partner_id": str(row["partner_id"]),
            "company_name": row["company_name"],
            "draft": row["draft"],
            "ai_meta": row["ai_meta"],
            "completeness": row["completeness"],
            "regulatory_flags": row["regulatory_flags"],
            "updated_at": row["updated_at"],
        }
        for row in partners_repository.list_review_queue()
    ]
    return {"items": items, "disclaimer": REGULATORY_DISCLAIMER}


@operator_router.post("/review/{draft_id}")
def review_draft(
    draft_id: str,
    payload: ReviewRequest,
    user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    """Approve (promote into product_catalog) or reject a submitted draft."""

    if not database_enabled():
        return {
            "status": "validated_not_persisted",
            "draft_id": draft_id,
            "decision": payload.decision,
        }

    draft_row = partners_repository.get_draft(draft_id)
    if draft_row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DRAFT_NOT_FOUND", "message": "draft_id does not exist."},
        )
    if draft_row["status"] != "partner_confirmed":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DRAFT_NOT_REVIEWABLE",
                "message": f"Draft status is '{draft_row['status']}', expected 'partner_confirmed'.",
            },
        )

    if payload.decision == "rejected":
        finalized = partners_repository.finalize_draft(draft_id, "rejected", None)
        partners_repository.record_review_decision(
            {
                "draft_id": draft_id,
                "decision": "rejected",
                "reason": payload.reason,
                "decided_by": user.email,
            }
        )
        return {"status": "persisted", "decision": "rejected", "draft": finalized}

    draft = dict(draft_row["draft"])
    category = str(draft.get("product_category") or "").strip()
    if category not in SUPPORTED_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CATEGORY_UNSUPPORTED",
                "message": (
                    f"'{category}' is not a supported product_category; adjust the draft "
                    f"to one of {list(SUPPORTED_CATEGORIES)} before approval."
                ),
            },
        )
    product_payload = {
        "brand_name": str(draft.get("brand_name") or "").strip(),
        "product_name": str(draft.get("product_name") or "").strip(),
        "product_category": category,
        "country_availability": [
            country
            for country in (draft.get("country_availability") or [])
            if country in _LAUNCH_COUNTRIES
        ],
        "key_claims_allowed": [str(claim) for claim in draft.get("key_claims_allowed") or []],
        "claims_disallowed": [],
    }
    if not product_payload["brand_name"] or not product_payload["product_name"]:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "DRAFT_INCOMPLETE",
                "message": "brand_name and product_name are required for approval.",
            },
        )

    product = products_repository.create_product(product_payload)
    finalized = partners_repository.finalize_draft(draft_id, "approved", str(product["id"]))
    partners_repository.record_review_decision(
        {
            "draft_id": draft_id,
            "decision": "approved",
            "reason": payload.reason,
            "decided_by": user.email,
        }
    )
    return {
        "status": "persisted",
        "decision": "approved",
        "draft": finalized,
        "product": product,
    }


# --- partner side ----------------------------------------------------------------

def _hub_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "PARTNER_HUB_UNAVAILABLE", "message": "Partner hub requires persistence."},
    )


def _token_invalid() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "PARTNER_TOKEN_INVALID", "message": "Unknown or revoked hub link."},
    )


def _resolve_partner(token: str) -> dict[str, Any]:
    """Token -> active partner, failing loudly. Suspension acts as a kill switch."""

    if not database_enabled():
        raise _hub_unavailable()
    token_row = partners_repository.get_active_by_token(token)
    if token_row is None:
        raise _token_invalid()
    partner = partners_repository.get_partner_by_id(str(token_row["partner_id"]))
    if partner is None or partner["status"] != "active":
        raise _token_invalid()
    partners_repository.touch_last_seen(str(token_row["id"]))
    return partner


def _sanitize_upload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "kind": row["kind"],
        "original_filename": row["original_filename"],
        "byte_size": row["byte_size"],
        "status": row["status"],
        "uploaded_at": row["uploaded_at"],
    }


def _sanitize_ai_meta(ai_meta: Any) -> dict[str, Any] | None:
    if not isinstance(ai_meta, dict):
        return None
    return {
        "mode": ai_meta.get("mode"),
        "prompt_version": ai_meta.get("prompt_version"),
        "field_confidence": ai_meta.get("field_confidence"),
    }


def _sanitize_draft(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "draft": row["draft"],
        "ai_meta": _sanitize_ai_meta(row.get("ai_meta")),
        "completeness": row.get("completeness"),
        "regulatory_flags": row.get("regulatory_flags"),
        "status": row["status"],
        "updated_at": row["updated_at"],
    }


@partner_router.get("/me")
def hub_me(token: str = Query(min_length=16, max_length=128)) -> dict[str, Any]:
    """Partner self-view. Read scope: own company, own uploads, own drafts."""

    partner = _resolve_partner(token)
    partner_id = str(partner["id"])
    uploads = partners_repository.list_uploads_for_partner(partner_id)
    drafts = partners_repository.list_drafts_for_partner(partner_id)
    return {
        "status": "ok",
        "hub": {
            "partner": {
                "company_name": partner["company_name"],
                "contact_name": partner.get("contact_name"),
            },
            "uploads": [_sanitize_upload(row) for row in uploads],
            "drafts": [_sanitize_draft(row) for row in drafts],
            "disclaimer": REGULATORY_DISCLAIMER,
        },
    }


@partner_router.post("/uploads")
async def hub_upload(
    file: UploadFile,
    kind: Literal["photo", "pdf", "data"] = Query(),
    token: str = Query(min_length=16, max_length=128),
) -> dict[str, Any]:
    """One file per call into one of the three separated lanes."""

    partner = _resolve_partner(token)

    content = bytearray()
    while True:
        chunk = await file.read(UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > settings.partner_upload_max_bytes:
            break
    data = bytes(content)
    filename = file.filename or "upload"
    rejection = validate_upload_file(kind, filename, data)
    if rejection:
        raise HTTPException(
            status_code=422,
            detail={"code": "UPLOAD_REJECTED", "message": rejection},
        )

    partner_id = str(partner["id"])
    suffix = Path(filename).suffix.lower()
    storage_dir = Path(settings.partner_upload_dir) / partner_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{uuid4().hex}{suffix}"
    storage_path.write_bytes(data)

    record = partners_repository.record_upload(
        {
            "partner_id": partner_id,
            "kind": kind,
            "original_filename": filename,
            "content_type": file.content_type or "application/octet-stream",
            "byte_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "storage_path": str(storage_path),
        }
    )
    return {"status": "persisted", "upload": _sanitize_upload(record)}


class ExtractRequest(BaseModel):
    upload_ids: list[str] = Field(min_length=1, max_length=20)


@partner_router.post("/uploads/extract")
def hub_extract(
    payload: ExtractRequest,
    token: str = Query(min_length=16, max_length=128),
) -> dict[str, Any]:
    """Run the AI pipeline over selected uploads and create a draft."""

    partner = _resolve_partner(token)
    partner_id = str(partner["id"])
    uploads = partners_repository.get_uploads_for_partner(partner_id, payload.upload_ids)
    if len(uploads) != len(set(payload.upload_ids)):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "UPLOAD_NOT_FOUND",
                "message": "One or more upload_ids do not exist for this partner.",
            },
        )

    try:
        extraction = run_extraction(uploads, str(partner["company_name"]))
    except PartnerAIGateClosed as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "PARTNER_AI_GATE_CLOSED", "message": str(exc)},
        ) from exc

    draft = extraction["draft"]
    photo_count = sum(1 for upload in uploads if upload["kind"] == "photo")
    enriched = enrich_draft(draft, photo_count)

    created = partners_repository.create_draft(
        {
            "partner_id": partner_id,
            "source_upload_ids": [str(upload["id"]) for upload in uploads],
            "draft": draft,
            "ai_meta": extraction["ai_meta"],
            "completeness": enriched["completeness"],
            "regulatory_flags": enriched["regulatory"],
        }
    )
    partners_repository.mark_uploads_status(
        [str(upload["id"]) for upload in uploads], "extracted"
    )
    return {
        "status": "persisted",
        "draft": _sanitize_draft(created),
        "pipeline": enriched,
    }


class DraftUpdateRequest(BaseModel):
    draft: dict[str, Any]
    action: Literal["save", "submit"] = "save"


@partner_router.post("/drafts/{draft_id}")
def hub_update_draft(
    draft_id: str,
    payload: DraftUpdateRequest,
    token: str = Query(min_length=16, max_length=128),
) -> dict[str, Any]:
    """Partner edits or submits a draft. Submission requires no blocking issues."""

    partner = _resolve_partner(token)
    partner_id = str(partner["id"])
    existing = partners_repository.get_draft_for_partner(draft_id, partner_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DRAFT_NOT_FOUND", "message": "draft_id does not exist."},
        )
    if existing["status"] not in {"ai_draft", "partner_confirmed"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DRAFT_LOCKED",
                "message": f"Draft status is '{existing['status']}' and can no longer be edited.",
            },
        )

    merged = dict(existing["draft"])
    for field in EDITABLE_DRAFT_FIELDS:
        if field in payload.draft:
            merged[field] = payload.draft[field]

    photo_count = sum(
        1
        for upload in partners_repository.get_uploads_for_partner(
            partner_id, [str(uid) for uid in existing["source_upload_ids"]]
        )
        if upload["kind"] == "photo"
    )
    enriched = enrich_draft(merged, photo_count)

    if payload.action == "submit" and not enriched["validation"]["can_submit"]:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "DRAFT_INCOMPLETE",
                "message": "Blocking issues must be fixed before submission.",
                "issues": enriched["validation"]["blocking"],
            },
        )

    status = "partner_confirmed" if payload.action == "submit" else "ai_draft"
    updated = partners_repository.update_draft_content(
        draft_id=draft_id,
        partner_id=partner_id,
        draft=merged,
        completeness=enriched["completeness"],
        regulatory_flags=enriched["regulatory"],
        status=status,
    )
    if updated is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "DRAFT_LOCKED", "message": "Draft could not be updated."},
        )
    return {
        "status": "persisted",
        "draft": _sanitize_draft(updated),
        "pipeline": enriched,
    }
