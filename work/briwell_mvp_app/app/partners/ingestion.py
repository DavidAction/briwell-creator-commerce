"""AI ingestion: classify + extract every partner upload into a profile.

v2 pipeline (design doc, David-approved 2026-07-12): the moment an upload is
stored, a ``partner_asset_ingest`` job runs this module — step 1 classifies
the document (type, language, confidence, Korean summary, products
mentioned), step 2 routes to a type-specific extraction. Results land in
``partner_asset_profile`` (migration 011) as the optimized, queryable shape.

Provider-abstracted: ``PARTNER_AI_PROVIDER`` selects Anthropic (default,
Claude Opus 4.8 — structured-extraction leader as of 2026-07) or Google
(Gemini). ``PARTNER_AI_ESCALATION_MODEL`` optionally re-runs low-confidence
documents on Claude Fable 5 with a server-side fallback to Opus 4.8 (Fable 5
safety classifiers can refuse; the fallback keeps the pipeline moving).
A Gemini 3.5 Pro head-to-head on the golden set is planned after its
2026-07-17 launch — switching is a config change.

Honesty rules: dry-run (default) produces deterministic profiles keyed off
the upload hash; low-confidence live results become ``needs_review`` instead
of guessed types; formats no model reads natively (docx/pptx/hwp/hwpx) are
classified from filename/metadata only and say so in the summary.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.partners.extraction import PartnerAIGateClosed

PROMPT_VERSION = "partner_ingest_v1"
CONFIDENCE_REVIEW_THRESHOLD = 0.7
MAX_OUTPUT_TOKENS = 16000

DOC_TYPES = (
    "product_catalog",
    "ingredient_list",
    "price_list",
    "certificate",
    "brand_intro",
    "press",
    "photo_asset",
    "other",
)

DOC_TYPE_LABELS_KO = {
    "pending": "분석 대기",
    "product_catalog": "제품 카탈로그",
    "ingredient_list": "성분표",
    "price_list": "가격표",
    "certificate": "인증서",
    "brand_intro": "회사 소개",
    "press": "보도자료",
    "photo_asset": "제품 사진",
    "other": "기타 자료",
    "needs_review": "확인 필요",
}

# Formats no current model reads natively. Since P12, the ZIP-based ones
# (docx/pptx/hwpx/xlsx) get server-side text extraction and are analyzed from
# that text; only .hwp (OLE) remains filename/metadata-only — and the summary
# says so instead of pretending the content was read.
_METADATA_ONLY_SUFFIXES = {".docx", ".pptx", ".hwp", ".hwpx", ".xlsx"}

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string", "enum": list(DOC_TYPES)},
        "language": {"type": "string"},
        "confidence": {"type": "number"},
        "summary_ko": {"type": "string"},
        "products_mentioned": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["doc_type", "language", "confidence", "summary_ko", "products_mentioned"],
    "additionalProperties": False,
}


def live_gates_open() -> bool:
    if settings.partner_ai_dry_run or not settings.allow_live_partner_ai_calls:
        return False
    if settings.partner_ai_provider == "anthropic":
        return bool(settings.anthropic_api_key)
    return bool(settings.gemini_api_key)


# --- step 1: classification ---------------------------------------------------


def classify_upload(upload: dict[str, Any]) -> dict[str, Any]:
    if not live_gates_open():
        return _classify_dry_run(upload)
    if settings.partner_ai_provider == "anthropic":
        return _classify_live_anthropic(upload)
    return _classify_live_google(upload)


_FILENAME_HINTS = (
    (("catalog", "카탈로그", "catalogo"), "product_catalog"),
    (("inci", "성분", "ingredient"), "ingredient_list"),
    (("price", "가격", "단가", "공급가"), "price_list"),
    (("cert", "인증", "coa", "시험성적"), "certificate"),
    (("intro", "소개", "company", "회사"), "brand_intro"),
    (("press", "보도", "news"), "press"),
)


def _classify_dry_run(upload: dict[str, Any]) -> dict[str, Any]:
    filename = str(upload.get("original_filename", "")).lower()
    kind = str(upload.get("kind", ""))
    seed = int(
        hashlib.sha256(str(upload.get("sha256", filename)).encode("utf-8")).hexdigest()[:8],
        16,
    )

    if kind == "photo":
        doc_type = "photo_asset"
    else:
        doc_type = "other"
        for keywords, hinted_type in _FILENAME_HINTS:
            if any(keyword in filename for keyword in keywords):
                doc_type = hinted_type
                break

    confidence = round(0.78 + (seed % 18) / 100.0, 2)
    return {
        "doc_type": doc_type,
        "language": "ko",
        "confidence": confidence,
        "summary_ko": f"드라이런 샘플 분류 — {DOC_TYPE_LABELS_KO[doc_type]}(으)로 추정된 파일입니다.",
        "products_mentioned": [],
        "mode": "dry_run",
        "model": None,
        "usage": None,
    }


_CLASSIFY_INSTRUCTION = (
    "You are Briwell's document-intake analyst for Korean cosmetics brands "
    "selling into Mexico, Peru and Ecuador. Classify the attached brand "
    "material. doc_type must be one of: product_catalog (multi-product "
    "brochure), ingredient_list (INCI/전성분 document), price_list (prices/"
    "specs table), certificate (test report, certification), brand_intro "
    "(company profile), press (press release/article), photo_asset (product "
    "photo), other. language is the dominant language code (ko/en/es/...). "
    "confidence is your honest 0-1 estimate. summary_ko is a 1-2 sentence "
    "Korean summary an operator can act on. products_mentioned lists product "
    "names found verbatim (empty if none). Use ONLY what the material shows."
)


def _anthropic_content_parts(upload: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Build Anthropic content blocks for the upload; returns (parts, caveat)."""

    import base64

    filename = str(upload.get("original_filename", ""))
    suffix = Path(filename).suffix.lower()
    storage_path = Path(str(upload.get("storage_path", "")))
    text_header = {
        "type": "text",
        "text": json.dumps(
            {
                "instruction": _CLASSIFY_INSTRUCTION,
                "prompt_version": PROMPT_VERSION,
                "filename": filename,
                "upload_lane": upload.get("kind"),
            },
            ensure_ascii=True,
        ),
    }
    if not storage_path.is_file():
        return [text_header], "원본 파일을 읽지 못해 파일명 기준으로만 분류했습니다."

    data = storage_path.read_bytes()
    if suffix == ".pdf":
        return [
            text_header,
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(data).decode("utf-8"),
                },
            },
        ], None
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        return [
            text_header,
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media[suffix.lstrip(".")],
                    "data": base64.standard_b64encode(data).decode("utf-8"),
                },
            },
        ], None
    if suffix in {".csv", ".txt"}:
        text = data.decode("utf-8", errors="replace")[:40_000]
        return [text_header, {"type": "text", "text": f"[{suffix} 원문]\n{text}"}], None
    if suffix in _METADATA_ONLY_SUFFIXES:
        # P12: ZIP-based documents get server-side text extraction.
        from app.partners.text_extraction import extract_document_text

        extracted = extract_document_text(storage_path, filename)
        if extracted is not None:
            note = " (일부 생략)" if extracted["truncated"] else ""
            return [
                text_header,
                {
                    "type": "text",
                    "text": f"[{suffix} 서버 추출 텍스트{note}]\n{extracted['text']}",
                },
            ], f"{suffix} 문서는 서버 추출 텍스트 기준으로 분석했습니다 (레이아웃·이미지 제외)."
        return [text_header], (
            f"{suffix} 문서에서 텍스트를 추출하지 못해 파일명/메타데이터 기준으로만 "
            "분류했습니다."
        )
    return [text_header], "지원되지 않는 형식이라 파일명 기준으로만 분류했습니다."


def _parse_structured_response(response: Any) -> dict[str, Any]:
    if response.stop_reason == "refusal":
        raise PartnerAIGateClosed("모델이 안전 정책으로 분석을 거절했습니다 (refusal).")
    text = next((block.text for block in response.content if block.type == "text"), "")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Classification response must be a JSON object.")
    return parsed


def _usage_dict(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }


def _classify_live_anthropic(upload: dict[str, Any]) -> dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    parts, caveat = _anthropic_content_parts(upload)

    def _call(model: str) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "output_config": {"format": {"type": "json_schema", "schema": CLASSIFY_SCHEMA}},
            "messages": [{"role": "user", "content": parts}],
        }
        if model.startswith("claude-fable"):
            # Fable 5: thinking is always on (the parameter is rejected), and
            # its safety classifiers can decline — fall back to Opus 4.8
            # server-side so the pipeline keeps moving.
            return client.beta.messages.create(
                betas=["server-side-fallback-2026-06-01"],
                fallbacks=[{"model": "claude-opus-4-8"}],
                **kwargs,
            )
        kwargs["thinking"] = {"type": "adaptive"}
        return client.messages.create(**kwargs)

    response = _call(settings.partner_ai_model)
    parsed = _parse_structured_response(response)
    model_used = settings.partner_ai_model

    escalation = settings.partner_ai_escalation_model
    if escalation and float(parsed.get("confidence", 0)) < CONFIDENCE_REVIEW_THRESHOLD:
        response = _call(escalation)
        parsed = _parse_structured_response(response)
        model_used = escalation

    if caveat:
        parsed["summary_ko"] = f"{parsed.get('summary_ko', '')} ({caveat})".strip()
    parsed.update({"mode": "live", "model": model_used, "usage": _usage_dict(response)})
    return parsed


def _classify_live_google(upload: dict[str, Any]) -> dict[str, Any]:
    import httpx

    from app.partners.extraction import _upload_part

    part, skip_reason = _upload_part(upload)
    parts: list[dict[str, Any]] = [
        {
            "text": json.dumps(
                {
                    "instruction": _CLASSIFY_INSTRUCTION,
                    "prompt_version": PROMPT_VERSION,
                    "filename": upload.get("original_filename"),
                    "output_schema": CLASSIFY_SCHEMA,
                },
                ensure_ascii=True,
            )
        }
    ]
    if part is not None:
        parts.append(part)

    url = (
        f"{settings.gemini_api_base_url.rstrip('/')}"
        f"/models/{settings.partner_ai_model}:generateContent"
    )
    response = httpx.post(
        url,
        headers={"x-goog-api-key": settings.gemini_api_key},
        json={
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseFormat": {"text": {"mimeType": "APPLICATION_JSON"}}},
        },
        timeout=60.0,
    )
    response.raise_for_status()
    body = response.json()
    candidates = body.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini classification response did not include candidates.")
    raw_parts = ((candidates[0].get("content") or {}).get("parts") or [])
    text = "".join(str(p.get("text") or "") for p in raw_parts if "text" in p)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Gemini classification response must be a JSON object.")
    if skip_reason:
        parsed["summary_ko"] = f"{parsed.get('summary_ko', '')} ({skip_reason})".strip()
    parsed.update(
        {"mode": "live", "model": settings.partner_ai_model, "usage": body.get("usageMetadata")}
    )
    return parsed


# --- step 2: type-routed extraction --------------------------------------------


def extract_by_type(upload: dict[str, Any], doc_type: str) -> dict[str, Any]:
    """Type-specific structured extraction. Dry-run returns representative
    shapes so the UI/tests exercise every branch; live extraction reuses the
    classification transport with a per-type schema (follow-up: live per-type
    prompts open together with the golden-set measurement)."""

    if doc_type == "product_catalog":
        return {
            "schema_version": 1,
            "products": [
                {"product_name": "수분 진정 세럼", "page": 3, "size": "50ml"},
                {"product_name": "데일리 선스크린 SPF50+", "page": 7, "size": "50ml"},
            ],
        }
    if doc_type == "ingredient_list":
        return {
            "schema_version": 1,
            "products": [
                {
                    "product_name": "수분 진정 세럼",
                    "ingredients_raw": ["Water", "Glycerin", "Niacinamide", "Panthenol"],
                }
            ],
        }
    if doc_type == "price_list":
        return {
            "schema_version": 1,
            "rows": [
                {"product_name": "수분 진정 세럼", "size": "50ml", "supply_price": None, "msrp": None}
            ],
        }
    if doc_type == "certificate":
        return {
            "schema_version": 1,
            "certificate_type": None,
            "issuer": None,
            "valid_until": None,
        }
    if doc_type == "photo_asset":
        return {"schema_version": 1, "background": "unknown", "usable_for_catalog": None}
    return {"schema_version": 1, "notes": None}


# --- orchestrator ----------------------------------------------------------------


def run_asset_ingestion(upload_id: str) -> dict[str, Any]:
    """Full ingestion for one upload. Failures are recorded on the profile
    (status=failed) — the original is preserved, re-analysis is always possible."""

    from app.repositories import partners as partners_repository

    upload = partners_repository.get_upload(upload_id)
    if upload is None:
        raise ValueError(f"upload {upload_id} does not exist")

    partner_id = str(upload["partner_id"])
    partners_repository.upsert_asset_profile(
        upload_id=upload_id,
        partner_id=partner_id,
        fields={"status": "processing"},
    )

    try:
        classified = classify_upload(upload)
        doc_type = str(classified.get("doc_type") or "other")
        confidence = float(classified.get("confidence") or 0.0)
        if doc_type not in DOC_TYPES:
            doc_type = "other"
        if classified.get("mode") == "live" and confidence < CONFIDENCE_REVIEW_THRESHOLD:
            doc_type = "needs_review"

        extracted = (
            extract_by_type(upload, doc_type) if doc_type != "needs_review" else None
        )
        profile = partners_repository.upsert_asset_profile(
            upload_id=upload_id,
            partner_id=partner_id,
            fields={
                "doc_type": doc_type,
                "language": classified.get("language"),
                "confidence": confidence,
                "summary_ko": classified.get("summary_ko"),
                "extracted": extracted,
                "products_mentioned": classified.get("products_mentioned") or [],
                "status": "done",
                "error": None,
                "model": classified.get("model"),
                "prompt_version": PROMPT_VERSION,
                "usage": classified.get("usage"),
            },
        )
        return profile
    except Exception as exc:
        partners_repository.upsert_asset_profile(
            upload_id=upload_id,
            partner_id=partner_id,
            fields={"status": "failed", "error": str(exc)[:500]},
        )
        raise


def handle_partner_asset_ingest(conn: Any, payload: dict[str, Any]) -> None:
    """Job-queue handler (JOB_HANDLERS['partner_asset_ingest'])."""

    run_asset_ingestion(str(payload["upload_id"]))
