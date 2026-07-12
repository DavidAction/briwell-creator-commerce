"""Brand Partner Hub (briefing 0.0.19 plan, David-approved 2026-07-12).

Two surfaces, mirroring the creator portal split:

* Operator side (RBAC-gated, ``/partners``): register partners, issue/rotate
  and revoke access tokens, review the queue, approve/reject drafts. Approval
  promotes a draft into the existing ``product_catalog`` — the human gate.
* Partner side (token-gated, ``/partner-hub``): a brand client sees only its
  own data (field-whitelisted; ``internal_memo`` and other partners' data are
  structurally excluded), uploads files in four separated lanes
  (photo / pdf / data / etc — David's decisions, 2026-07-12), runs AI
  extraction (dry-run gated), edits and submits drafts. Every stored upload
  is auto-queued for AI ingestion (classify + extract → partner_asset_profile).

DB-off behavior: operator endpoints keep the ``validated_not_persisted``
convention; the partner side is a consumer surface and fails loudly with
503 PARTNER_HUB_UNAVAILABLE (same reasoning as the creator portal).
"""

import hashlib
import io
import logging
import secrets
import zipfile
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.auth import UserContext, require_roles
from app.core.config import settings
from app.core.db import connection, database_enabled
from app.partners import assemble as assemble_module
from app.partners.extraction import PartnerAIGateClosed, run_extraction
from app.partners.ingestion import DOC_TYPE_LABELS_KO
from app.partners.ingredient_data import REGULATORY_DISCLAIMER
from app.partners.pipeline import enrich_draft
from app.partners.validation import SUPPORTED_CATEGORIES
from app.repositories import partners as partners_repository
from app.repositories import products as products_repository
from app.repositories.jobs import enqueue_job

logger = logging.getLogger("briwell")

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
    # v2 'etc' lane (David 2026-07-12): documents only — video deferred.
    "etc": {".docx", ".pptx", ".hwp", ".hwpx", ".txt"},
}

# HWP 5.x is an OLE compound file; HWP 3.0 carries an ASCII signature.
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_HWP3_MAGIC = b"HWP Document File"

# OOXML-family formats are ZIP containers; a macro-enabled document carries
# a vbaProject.bin part. Operators end up opening these files, so macro
# documents are rejected at the door (P2 — macro-free versions re-upload fine).
_ZIP_CONTAINER_SUFFIXES = {".docx", ".pptx", ".xlsx", ".hwpx"}


def _zip_container_rejection(content: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if any(name.lower().endswith("vbaproject.bin") for name in archive.namelist()):
                return (
                    "매크로(vbaProject.bin)가 포함된 문서는 보안상 받을 수 없습니다 — "
                    "매크로를 제거한 버전으로 다시 올려 주세요."
                )
    except (zipfile.BadZipFile, zipfile.LargeZipFile):
        return "문서의 압축 구조를 읽을 수 없습니다 (파일 내용 검사 실패)."
    return None


def validate_upload_file(kind: str, filename: str, content: bytes) -> str | None:
    """Return a Korean rejection message, or None when the file is acceptable."""

    suffix = Path(filename or "").suffix.lower()
    allowed = KIND_EXTENSIONS.get(kind)
    if allowed is None:
        return "kind는 photo/pdf/data/etc 중 하나여야 합니다."
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
    if suffix in _ZIP_CONTAINER_SUFFIXES:
        if not content.startswith(b"PK\x03\x04"):
            return f"{suffix.lstrip('.').upper()} 형식이 아닙니다 (파일 내용 검사 실패)."
        rejection = _zip_container_rejection(content)
        if rejection:
            return rejection
    if suffix == ".hwp" and not (
        content.startswith(_OLE_MAGIC) or content.startswith(_HWP3_MAGIC)
    ):
        return "HWP 형식이 아닙니다 (파일 내용 검사 실패)."
    if suffix in {".csv", ".txt"}:
        head = content[:4096]
        if b"\x00" in head:
            return f"{suffix.lstrip('.').upper()} 형식이 아닙니다 (이진 데이터가 포함됨)."
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
    created = partners_repository.issue_token(
        payload.partner_id, token, settings.partner_token_ttl_days
    )
    return {
        "status": "persisted",
        "token": token,
        "token_id": str(created["id"]),
        "partner_id": payload.partner_id,
        "expires_at": created.get("expires_at"),
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


@operator_router.get("/uploads/{upload_id}/file")
def operator_download_upload(
    upload_id: str,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> Response:
    """Operator views any partner's original during review (P5/P6)."""

    if not database_enabled():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PARTNER_HUB_UNAVAILABLE",
                "message": "File serving requires persistence (USE_DATABASE=true).",
            },
        )
    if not _is_uuid(upload_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "UPLOAD_NOT_FOUND", "message": "upload_id does not exist."},
        )
    row = partners_repository.get_upload(upload_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "UPLOAD_NOT_FOUND", "message": "upload_id does not exist."},
        )
    return _serve_upload(row)


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


@operator_router.get("/drafts/{draft_id}")
def operator_draft_detail(
    draft_id: str,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    """Everything an operator needs to actually review (P5): the full draft,
    the source files with their AI profiles, and the decision history."""

    if not database_enabled():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PARTNER_HUB_UNAVAILABLE",
                "message": "Draft detail requires persistence (USE_DATABASE=true).",
            },
        )
    if not _is_uuid(draft_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "DRAFT_NOT_FOUND", "message": "draft_id does not exist."},
        )
    draft_row = partners_repository.get_draft(draft_id)
    if draft_row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "DRAFT_NOT_FOUND", "message": "draft_id does not exist."},
        )
    partner_id = str(draft_row["partner_id"])
    partner = partners_repository.get_partner_by_id(partner_id)
    upload_ids = [str(uid) for uid in draft_row.get("source_upload_ids") or []]
    uploads = partners_repository.get_uploads_for_partner(partner_id, upload_ids)
    profiles_by_upload = {
        str(profile["upload_id"]): profile
        for profile in partners_repository.get_profiles_for_uploads(upload_ids)
    }
    source_uploads = []
    for row in uploads:
        profile = profiles_by_upload.get(str(row["id"]))
        source_uploads.append(
            {
                "id": str(row["id"]),
                "kind": row["kind"],
                "original_filename": row["original_filename"],
                "byte_size": row["byte_size"],
                "status": row["status"],
                "uploaded_at": row["uploaded_at"],
                "profile": (
                    {
                        "doc_type": profile["doc_type"],
                        "doc_type_label": DOC_TYPE_LABELS_KO.get(
                            str(profile["doc_type"]), str(profile["doc_type"])
                        ),
                        "status": profile["status"],
                        # NUMERIC arrives as Decimal and would serialize as a
                        # string; the UI needs a number (same rule as /me).
                        "confidence": (
                            float(profile["confidence"])
                            if profile["confidence"] is not None
                            else None
                        ),
                        "summary_ko": profile["summary_ko"],
                        "products_mentioned": list(profile["products_mentioned"] or []),
                        "extracted": profile["extracted"],
                        "error": profile["error"],
                        "model": profile["model"],
                        "prompt_version": profile["prompt_version"],
                        "updated_at": profile["updated_at"],
                    }
                    if profile is not None
                    else None
                ),
            }
        )
    return {
        "draft": {
            "id": str(draft_row["id"]),
            "partner_id": partner_id,
            "draft": draft_row["draft"],
            "ai_meta": draft_row["ai_meta"],
            "completeness": draft_row["completeness"],
            "regulatory_flags": draft_row["regulatory_flags"],
            "status": draft_row["status"],
            "promoted_product_id": (
                str(draft_row["promoted_product_id"])
                if draft_row.get("promoted_product_id")
                else None
            ),
            "created_at": draft_row["created_at"],
            "updated_at": draft_row["updated_at"],
        },
        "partner": {
            "id": partner_id,
            "company_name": partner["company_name"] if partner else None,
        },
        "source_uploads": source_uploads,
        "decisions": partners_repository.list_review_decisions(draft_id),
        "disclaimer": REGULATORY_DISCLAIMER,
    }


@operator_router.get("/asset-profiles/attention")
def attention_profiles(
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    """needs_review + failed ingestion profiles across all partners (P5/P10)."""

    if not database_enabled():
        return {"items": []}
    items = []
    for row in partners_repository.list_attention_profiles():
        item = dict(row)
        item["upload_id"] = str(row["upload_id"])
        item["partner_id"] = str(row["partner_id"])
        item["doc_type_label"] = DOC_TYPE_LABELS_KO.get(str(row["doc_type"]), str(row["doc_type"]))
        if item.get("confidence") is not None:
            item["confidence"] = float(item["confidence"])
        items.append(item)
    return {"items": items}


@operator_router.post("/uploads/{upload_id}/reanalyze")
def reanalyze_upload(
    upload_id: str,
    _user: UserContext = Depends(require_roles("admin", "operator", "campaign_manager")),
) -> dict[str, Any]:
    """Manual recovery for failed/needs_review profiles (P10): reset the
    profile to pending and queue a fresh partner_asset_ingest job."""

    if not database_enabled():
        return {"status": "validated_not_persisted", "upload_id": upload_id}
    if not _is_uuid(upload_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "UPLOAD_NOT_FOUND", "message": "upload_id does not exist."},
        )
    row = partners_repository.get_upload(upload_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "UPLOAD_NOT_FOUND", "message": "upload_id does not exist."},
        )
    partners_repository.upsert_asset_profile(
        upload_id=upload_id,
        partner_id=str(row["partner_id"]),
        fields={"status": "pending", "error": None},
    )
    with connection() as conn:
        job_id = enqueue_job(conn, "partner_asset_ingest", {"upload_id": upload_id})
    return {"status": "queued", "upload_id": upload_id, "job_id": job_id}


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


def hub_token(
    token: str | None = Query(default=None, min_length=16, max_length=128),
    authorization: str | None = Header(default=None),
) -> str:
    """Partner hub credential, P1 hardening: the hub page sends the token as
    ``Authorization: Bearer`` (keeps it out of URLs and proxy/server logs);
    the ``?token=`` query form stays accepted so freshly shared links and
    older clients keep working."""

    if authorization:
        scheme, _, value = authorization.partition(" ")
        value = value.strip()
        if scheme.lower() == "bearer" and 16 <= len(value) <= 128:
            return value
    if token:
        return token
    raise HTTPException(
        status_code=422,
        detail={
            "code": "PARTNER_TOKEN_MISSING",
            "message": "Provide the hub token via Authorization: Bearer or ?token=.",
        },
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


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (ValueError, TypeError):
        return False
    return True


# Served content types are whitelisted by suffix — the stored content_type is
# client-supplied and must not drive the response header.
_SERVE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".txt": "text/plain; charset=utf-8",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _serve_upload(row: dict[str, Any]) -> Response:
    """Stream a stored original back to an authenticated caller (P6).

    Always attachment-disposed with nosniff so a malicious upload cannot
    execute in the browser context; previews fetch the bytes and render them
    from an object URL instead of navigating here."""

    storage_path = Path(str(row["storage_path"]))
    if not storage_path.is_file():
        raise HTTPException(
            status_code=404,
            detail={
                "code": "FILE_MISSING",
                "message": "원본 파일이 저장소에 없습니다 — 운영자에게 문의해 주세요.",
            },
        )
    suffix = Path(str(row["original_filename"])).suffix.lower()
    quoted = quote(str(row["original_filename"]))
    return Response(
        content=storage_path.read_bytes(),
        media_type=_SERVE_MIME.get(suffix, "application/octet-stream"),
        headers={
            "Content-Disposition": (
                f'attachment; filename="upload{suffix}"; filename*=UTF-8\'\'{quoted}'
            ),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


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


def _sanitize_analysis(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    """Partner-facing view of the AI ingestion profile. Whitelist only —
    model name, prompt version and raw error text stay internal."""

    if profile is None:
        return None
    doc_type = str(profile.get("doc_type") or "pending")
    return {
        "doc_type": doc_type,
        "doc_type_label": DOC_TYPE_LABELS_KO.get(doc_type, doc_type),
        "status": profile.get("status"),
        "confidence": float(profile["confidence"]) if profile.get("confidence") is not None else None,
        "summary_ko": profile.get("summary_ko"),
        "products_mentioned": list(profile.get("products_mentioned") or []),
        "updated_at": profile.get("updated_at"),
    }


@partner_router.get("/me")
def hub_me(token: str = Depends(hub_token)) -> dict[str, Any]:
    """Partner self-view. Read scope: own company, own uploads, own drafts."""

    partner = _resolve_partner(token)
    partner_id = str(partner["id"])
    uploads = partners_repository.list_uploads_for_partner(partner_id)
    drafts = partners_repository.list_drafts_for_partner(partner_id)
    profiles_by_upload = {
        str(profile["upload_id"]): profile
        for profile in partners_repository.list_asset_profiles_for_partner(partner_id)
    }
    upload_views = []
    for row in uploads:
        view = _sanitize_upload(row)
        view["analysis"] = _sanitize_analysis(profiles_by_upload.get(str(row["id"])))
        upload_views.append(view)
    return {
        "status": "ok",
        "hub": {
            "partner": {
                "company_name": partner["company_name"],
                "contact_name": partner.get("contact_name"),
            },
            "uploads": upload_views,
            "drafts": [_sanitize_draft(row) for row in drafts],
            "disclaimer": REGULATORY_DISCLAIMER,
        },
    }


def _enqueue_ingest(upload_id: str, partner_id: str) -> None:
    """Create the pending profile and queue the ingestion job.

    Failure here must never fail the upload — the original is stored and the
    profile simply stays pending (honest '분석 대기' in the hub) until the
    worker or a re-analysis picks it up."""

    try:
        partners_repository.upsert_asset_profile(
            upload_id=upload_id, partner_id=partner_id, fields={"status": "pending"}
        )
        with connection() as conn:
            enqueue_job(conn, "partner_asset_ingest", {"upload_id": upload_id})
    except Exception:
        logger.exception("partner_asset_ingest enqueue failed for upload %s", upload_id)


@partner_router.post("/uploads")
async def hub_upload(
    file: UploadFile,
    kind: Literal["photo", "pdf", "data", "etc"] = Query(),
    token: str = Depends(hub_token),
) -> dict[str, Any]:
    """One file per call into one of the four separated lanes."""

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
    sha256 = hashlib.sha256(data).hexdigest()

    # P2: same-sha dedup per partner — re-uploading an identical file returns
    # the existing record instead of storing a copy and paying for a second
    # AI analysis. The response says so honestly (status=duplicate).
    existing = partners_repository.get_upload_by_sha(partner_id, sha256)
    if existing is not None:
        return {"status": "duplicate", "upload": _sanitize_upload(existing)}

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
            "sha256": sha256,
            "storage_path": str(storage_path),
        }
    )
    # v2: auto-ingestion — classify/extract in the background (job queue).
    _enqueue_ingest(str(record["id"]), partner_id)
    return {"status": "persisted", "upload": _sanitize_upload(record)}


@partner_router.get("/uploads/{upload_id}/file")
def hub_download_upload(
    upload_id: str,
    token: str = Depends(hub_token),
) -> Response:
    """Partner re-views its own original (photo previews, document download).

    Ownership is enforced by the partner-scoped query — an upload id from a
    different partner behaves exactly like a nonexistent one (404)."""

    partner = _resolve_partner(token)
    if not _is_uuid(upload_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "UPLOAD_NOT_FOUND", "message": "upload_id does not exist."},
        )
    uploads = partners_repository.get_uploads_for_partner(str(partner["id"]), [upload_id])
    if not uploads:
        raise HTTPException(
            status_code=404,
            detail={"code": "UPLOAD_NOT_FOUND", "message": "upload_id does not exist."},
        )
    return _serve_upload(uploads[0])


class ExtractRequest(BaseModel):
    upload_ids: list[str] = Field(min_length=1, max_length=20)


@partner_router.post("/uploads/extract")
def hub_extract(
    payload: ExtractRequest,
    token: str = Depends(hub_token),
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


@partner_router.post("/assemble")
def hub_assemble(token: str = Depends(hub_token)) -> dict[str, Any]:
    """Assemble (P7): one click turns the partner's analyzed profiles into
    N product drafts — catalog products enriched with matching ingredient
    lists, price rows and photo mentions, all through the same pipeline as
    manual extraction. Idempotent: already-drafted product names are skipped."""

    partner = _resolve_partner(token)
    partner_id = str(partner["id"])
    profiles = partners_repository.list_done_profiles_for_partner(partner_id)
    existing_names = [
        str((row.get("draft") or {}).get("product_name") or "")
        for row in partners_repository.list_drafts_for_partner(partner_id)
        if row.get("status") != "rejected"
    ]
    result = assemble_module.assemble_proposals(
        profiles, str(partner["company_name"]), existing_names
    )
    if result["catalog_profile_count"] == 0:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ASSEMBLE_NO_CATALOG",
                "message": (
                    "조립할 카탈로그 분석 프로필이 없습니다 — 카탈로그 업로드의 "
                    "AI 분석이 완료된 뒤 다시 시도해 주세요."
                ),
            },
        )

    created = []
    touched_upload_ids: set[str] = set()
    for proposal in result["proposals"]:
        enriched = enrich_draft(proposal["draft"], proposal["photo_count"])
        row = partners_repository.create_draft(
            {
                "partner_id": partner_id,
                "source_upload_ids": proposal["source_upload_ids"],
                "draft": proposal["draft"],
                "ai_meta": {
                    "mode": "assembled",
                    "prompt_version": assemble_module.PROMPT_VERSION,
                    "upload_count": len(proposal["source_upload_ids"]),
                },
                "completeness": enriched["completeness"],
                "regulatory_flags": enriched["regulatory"],
            }
        )
        created.append(_sanitize_draft(row))
        touched_upload_ids.update(proposal["source_upload_ids"])
    if touched_upload_ids:
        partners_repository.mark_uploads_status(sorted(touched_upload_ids), "extracted")
    return {
        "status": "persisted",
        "created": created,
        "skipped_existing": result["skipped_existing"],
    }


class DraftUpdateRequest(BaseModel):
    draft: dict[str, Any]
    action: Literal["save", "submit"] = "save"


@partner_router.post("/drafts/{draft_id}")
def hub_update_draft(
    draft_id: str,
    payload: DraftUpdateRequest,
    token: str = Depends(hub_token),
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
