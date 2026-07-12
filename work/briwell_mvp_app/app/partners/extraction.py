"""AI extraction: partner uploads -> one structured product draft.

House dual live-gate shape (same as AI/TikTok/Shopify/news lanes): dry-run by
default returns a deterministic draft derived from the uploads' hashes, so the
partner hub UI and tests work offline and repeat runs are reproducible. Live
extraction requires BOTH ``PARTNER_AI_DRY_RUN=false`` and
``ALLOW_LIVE_PARTNER_AI_CALLS=true`` plus a Gemini key.

Live mode sends photos and PDF catalogs as inlineData (Gemini reads them
natively) and inlines CSV text. ZIP-based documents (docx/pptx/hwpx/xlsx)
are inlined as server-extracted text (P12, app/partners/text_extraction.py);
a failed extraction is surfaced honestly in the draft notes rather than
silently skipped.
"""

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

PROMPT_VERSION = "partner_extract_v1"
EXTRACTION_MODEL_ID = "gemini-2.5-flash"
REQUEST_TIMEOUT_SECONDS = 60.0
MAX_INLINE_FILES = 8
MAX_INLINE_CSV_CHARS = 40_000

_MIME_BY_KIND_EXT = {
    ("photo", ".jpg"): "image/jpeg",
    ("photo", ".jpeg"): "image/jpeg",
    ("photo", ".png"): "image/png",
    ("photo", ".webp"): "image/webp",
    ("pdf", ".pdf"): "application/pdf",
}


class PartnerAIGateClosed(Exception):
    """Raised when a live extraction is requested but the gates are closed."""


def gates_open() -> bool:
    return (
        not settings.partner_ai_dry_run
        and settings.allow_live_partner_ai_calls
        and bool(settings.gemini_api_key)
    )


def run_extraction(uploads: list[dict[str, Any]], partner_name: str) -> dict[str, Any]:
    """Extract a product draft from uploads. Returns {draft, ai_meta}."""

    if settings.partner_ai_dry_run or not settings.allow_live_partner_ai_calls:
        return _dry_run_extraction(uploads, partner_name)
    if not settings.gemini_api_key:
        raise PartnerAIGateClosed("GEMINI_API_KEY is required for live partner extraction.")
    return _live_extraction(uploads, partner_name)


# --- dry run -----------------------------------------------------------------

_SAMPLE_PRODUCTS = [
    {
        "product_name": "수분 진정 세럼",
        "product_category": "calming_serum",
        "size": "50ml",
        "ingredients_raw": [
            "Water", "Butylene Glycol", "Glycerin", "Niacinamide",
            "Centella Asiatica Extract", "Madecassoside", "Panthenol",
            "Sodium Hyaluronate", "Carbomer", "Phenoxyethanol",
        ],
        "claims_candidates": ["진정 케어", "수분 보습", "저자극 테스트 완료"],
    },
    {
        "product_name": "데일리 선스크린 SPF50+",
        "product_category": "sunscreen",
        "size": "50ml",
        "ingredients_raw": [
            "Water", "Ethylhexyl Methoxycinnamate", "Titanium Dioxide",
            "Homosalate", "Ethylhexyl Salicylate", "Butylene Glycol",
            "Niacinamide", "Glycerin", "1,2-Hexanediol", "Tocopherol",
        ],
        "claims_candidates": ["SPF50+ PA++++", "백탁 최소화", "가벼운 발림성"],
    },
    {
        "product_name": "약산성 젤 클렌저",
        "product_category": "cleanser",
        "size": "150ml",
        "ingredients_raw": [
            "Water", "Glycerin", "Cocamidopropyl Betaine",
            "Sodium Cocoyl Isethionate", "Butylene Glycol", "Panthenol",
            "Allantoin", "Citric Acid", "1,2-Hexanediol",
        ],
        "claims_candidates": ["약산성 pH 5.5", "순한 세정", "촉촉한 마무리"],
    },
]


def _dry_run_extraction(uploads: list[dict[str, Any]], partner_name: str) -> dict[str, Any]:
    digest_source = "|".join(sorted(str(upload.get("sha256", "")) for upload in uploads))
    seed = int(hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:8], 16)
    sample = _SAMPLE_PRODUCTS[seed % len(_SAMPLE_PRODUCTS)]

    name_hint = _filename_hint(uploads)
    draft = {
        "product_name": name_hint or sample["product_name"],
        "brand_name": partner_name,
        "product_category": sample["product_category"],
        "size": sample["size"],
        "ingredients_raw": list(sample["ingredients_raw"]),
        "key_claims_allowed": [],
        "claims_candidates": list(sample["claims_candidates"]),
        "country_availability": ["MX", "PE", "EC"],
        "notes": "드라이런 샘플 초안 — 라이브 AI 추출 전 파이프라인 검증용입니다.",
    }
    confidence_base = 0.62 + (seed % 30) / 100.0
    ai_meta = {
        "mode": "dry_run",
        "model": None,
        "prompt_version": PROMPT_VERSION,
        "upload_count": len(uploads),
        "field_confidence": {
            "product_name": round(min(confidence_base + 0.10, 0.95), 2),
            "product_category": round(min(confidence_base + 0.05, 0.92), 2),
            "size": round(confidence_base, 2),
            "ingredients_raw": round(min(confidence_base + 0.15, 0.93), 2),
        },
    }
    return {"draft": draft, "ai_meta": ai_meta}


def _filename_hint(uploads: list[dict[str, Any]]) -> str | None:
    for kind in ("pdf", "data", "photo"):
        for upload in uploads:
            if upload.get("kind") == kind:
                stem = Path(str(upload.get("original_filename", ""))).stem.strip()
                if len(stem) >= 4:
                    return stem.replace("_", " ").replace("-", " ")
    return None


# --- live --------------------------------------------------------------------

_EXTRACTION_INSTRUCTION = (
    "You are Briwell's product-onboarding analyst for Korean cosmetics sold "
    "into Mexico, Peru and Ecuador. From the attached brand materials, "
    "extract the PRIMARY product as JSON with keys: product_name (keep the "
    "original Korean if present), brand_name, product_category (one of "
    "sunscreen|calming_serum|cleanser|sheet_mask|cushion_foundation, or a "
    "short free-text if none fits), size, ingredients_raw (full INCI list in "
    "declared order, English INCI where printed), claims_candidates (marketing "
    "claims found verbatim), notes (anything ambiguous). Use ONLY what the "
    "materials show. Never invent ingredients; if the INCI list is illegible "
    "return an empty ingredients_raw and say so in notes. Return valid JSON only."
)


def _live_extraction(uploads: list[dict[str, Any]], partner_name: str) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [
        {
            "text": json.dumps(
                {
                    "instruction": _EXTRACTION_INSTRUCTION,
                    "prompt_version": PROMPT_VERSION,
                    "partner_company": partner_name,
                },
                ensure_ascii=True,
            )
        }
    ]
    skipped: list[str] = []
    inlined = 0
    for upload in uploads:
        if inlined >= MAX_INLINE_FILES:
            skipped.append(str(upload.get("original_filename")))
            continue
        part, skip_reason = _upload_part(upload)
        if part is not None:
            parts.append(part)
            inlined += 1
        elif skip_reason:
            skipped.append(skip_reason)

    url = f"{settings.gemini_api_base_url.rstrip('/')}/models/{EXTRACTION_MODEL_ID}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseFormat": {"text": {"mimeType": "APPLICATION_JSON"}}},
    }
    response = httpx.post(
        url,
        headers={"x-goog-api-key": settings.gemini_api_key},
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    candidates = body.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini extraction response did not include candidates.")
    raw_parts = ((candidates[0].get("content") or {}).get("parts") or [])
    text = "".join(str(part.get("text") or "") for part in raw_parts if "text" in part)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Gemini extraction response JSON must be an object.")

    draft = {
        "product_name": str(parsed.get("product_name") or "").strip(),
        "brand_name": str(parsed.get("brand_name") or partner_name).strip(),
        "product_category": str(parsed.get("product_category") or "").strip(),
        "size": str(parsed.get("size") or "").strip(),
        "ingredients_raw": [str(item) for item in parsed.get("ingredients_raw") or []],
        "key_claims_allowed": [],
        "claims_candidates": [str(item) for item in parsed.get("claims_candidates") or []],
        "country_availability": ["MX", "PE", "EC"],
        "notes": str(parsed.get("notes") or "").strip(),
    }
    if skipped:
        note = f"미처리 파일(수동 확인 필요): {', '.join(skipped)}"
        draft["notes"] = f"{draft['notes']} / {note}".strip(" /")
    ai_meta = {
        "mode": "live",
        "model": EXTRACTION_MODEL_ID,
        "prompt_version": PROMPT_VERSION,
        "upload_count": len(uploads),
        "usage": body.get("usageMetadata"),
    }
    return {"draft": draft, "ai_meta": ai_meta}


def _upload_part(upload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    kind = str(upload.get("kind"))
    filename = str(upload.get("original_filename", ""))
    suffix = Path(filename).suffix.lower()
    storage_path = Path(str(upload.get("storage_path", "")))
    if not storage_path.is_file():
        return None, f"{filename} (원본 파일 없음)"

    mime = _MIME_BY_KIND_EXT.get((kind, suffix))
    if mime:
        data = base64.b64encode(storage_path.read_bytes()).decode("ascii")
        return {"inlineData": {"mimeType": mime, "data": data}}, None

    if suffix in {".csv", ".txt"}:
        text = storage_path.read_text(encoding="utf-8", errors="replace")[:MAX_INLINE_CSV_CHARS]
        return {"text": f"[{suffix} {filename}]\n{text}"}, None

    # P12: ZIP-based documents (docx/pptx/hwpx/xlsx) get server-side text
    # extraction; a failed extraction stays an honest skip, never a guess.
    from app.partners.text_extraction import EXTRACTABLE_SUFFIXES, extract_document_text

    if suffix in EXTRACTABLE_SUFFIXES:
        extracted = extract_document_text(storage_path, filename)
        if extracted is not None:
            note = " — 일부 생략" if extracted["truncated"] else ""
            return {
                "text": f"[{suffix} {filename} 서버 추출 텍스트{note}]\n{extracted['text']}"
            }, None
        return None, f"{filename} (텍스트 추출 실패 — 수동 확인 필요)"
    return None, f"{filename} (지원되지 않는 형식)"
