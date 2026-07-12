"""Draft validation with Korean, partner-facing issue reports.

``blocking`` issues stop partner submission (a draft without a product name
is not reviewable); ``advisory`` issues inform but never block — the operator
is the gate, not the validator (human-approval house rule).
"""

from typing import Any

SUPPORTED_CATEGORIES = (
    "sunscreen",
    "calming_serum",
    "cleanser",
    "sheet_mask",
    "cushion_foundation",
)

CATEGORY_LABELS_KO = {
    "sunscreen": "선스크린",
    "calming_serum": "카밍 세럼",
    "cleanser": "클렌저",
    "sheet_mask": "시트 마스크",
    "cushion_foundation": "쿠션 파운데이션",
}


def validate_draft(draft: dict[str, Any], normalized: dict[str, Any] | None) -> dict[str, Any]:
    blocking: list[dict[str, str]] = []
    advisory: list[dict[str, str]] = []

    if not str(draft.get("product_name") or "").strip():
        blocking.append({"field": "product_name", "message": "제품명이 비어 있습니다."})
    if not str(draft.get("brand_name") or "").strip():
        blocking.append({"field": "brand_name", "message": "브랜드명이 비어 있습니다."})

    category = str(draft.get("product_category") or "").strip()
    if not category:
        advisory.append({"field": "product_category", "message": "카테고리가 지정되지 않았습니다."})
    elif category not in SUPPORTED_CATEGORIES:
        advisory.append(
            {
                "field": "product_category",
                "message": (
                    f"'{category}'는 현재 지원 카테고리가 아닙니다 — 승인 시 운영자가 "
                    "지원 카테고리로 조정하거나 협의합니다."
                ),
            }
        )

    if normalized is None or not normalized.get("total"):
        advisory.append({"field": "ingredients", "message": "전성분(INCI) 리스트가 없습니다."})
    elif normalized.get("unmatched"):
        advisory.append(
            {
                "field": "ingredients",
                "message": (
                    f"성분 {normalized['unmatched']}개가 사전에 매칭되지 않았습니다 — "
                    "표기 확인이 필요합니다."
                ),
            }
        )

    if not str(draft.get("size") or "").strip():
        advisory.append({"field": "size", "message": "용량/규격 정보가 없습니다."})

    return {
        "blocking": blocking,
        "advisory": advisory,
        "can_submit": not blocking,
    }
