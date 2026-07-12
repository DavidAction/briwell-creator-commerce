"""Assemble: combine done asset profiles into N product draft proposals (P7).

v2 design step 4 (the "카탈로그 → 제품 N개 등록" scenario): once a partner's
uploads are classified and extracted into ``partner_asset_profile`` rows,

* ``product_catalog`` profiles enumerate products (name, size, page),
* ``ingredient_list`` profiles carry INCI lists per product,
* ``price_list`` profiles carry size/spec rows per product,
* ``photo_asset`` profiles may mention the products they show.

``assemble_proposals`` joins these by normalized product name and proposes
one draft per **catalog** product — catalogs are the authoritative product
enumeration; ingredient/price/photo data enriches but never invents a
product. Proposals whose name already has a non-rejected draft are skipped
(repeat clicks stay idempotent). The router then runs each proposal through
the same ``enrich_draft`` pipeline as manual extraction.
"""

from typing import Any

PROMPT_VERSION = "partner_assemble_v1"

_LAUNCH_COUNTRIES = ["MX", "PE", "EC"]


def _name_key(name: Any) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


def _iter_products(profile: dict[str, Any]) -> list[dict[str, Any]]:
    extracted = profile.get("extracted")
    if not isinstance(extracted, dict):
        return []
    items = extracted.get("products") or extracted.get("rows") or []
    return [item for item in items if isinstance(item, dict) and item.get("product_name")]


def assemble_proposals(
    profiles: list[dict[str, Any]],
    partner_name: str,
    existing_draft_names: list[str],
) -> dict[str, Any]:
    """Build draft proposals from done profiles.

    Returns {"proposals": [{draft, source_upload_ids, photo_count}],
             "skipped_existing": [names], "catalog_profile_count": int}."""

    done = [profile for profile in profiles if profile.get("status") == "done"]
    catalogs = [p for p in done if p.get("doc_type") == "product_catalog"]
    ingredients = [p for p in done if p.get("doc_type") == "ingredient_list"]
    prices = [p for p in done if p.get("doc_type") == "price_list"]
    photos = [p for p in done if p.get("doc_type") == "photo_asset"]

    existing_keys = {_name_key(name) for name in existing_draft_names}

    # Catalogs own the product enumeration (insertion-ordered, deduped).
    products: dict[str, dict[str, Any]] = {}
    for profile in catalogs:
        for item in _iter_products(profile):
            key = _name_key(item["product_name"])
            if not key or key in products:
                continue
            products[key] = {
                "product_name": str(item["product_name"]).strip(),
                "size": str(item.get("size") or "").strip(),
                "ingredients_raw": [],
                "source_upload_ids": [str(profile["upload_id"])],
                "source_names": {"catalog"},
                "photo_count": 0,
            }

    skipped_existing: list[str] = []
    for key in list(products):
        if key in existing_keys:
            skipped_existing.append(products.pop(key)["product_name"])

    for profile in ingredients:
        for item in _iter_products(profile):
            entry = products.get(_name_key(item["product_name"]))
            if entry is None:
                continue
            raw = [str(name) for name in item.get("ingredients_raw") or [] if str(name).strip()]
            if raw and not entry["ingredients_raw"]:
                entry["ingredients_raw"] = raw
                entry["source_upload_ids"].append(str(profile["upload_id"]))
                entry["source_names"].add("ingredient_list")

    for profile in prices:
        for item in _iter_products(profile):
            entry = products.get(_name_key(item["product_name"]))
            if entry is None:
                continue
            if not entry["size"] and str(item.get("size") or "").strip():
                entry["size"] = str(item["size"]).strip()
            if str(profile["upload_id"]) not in entry["source_upload_ids"]:
                entry["source_upload_ids"].append(str(profile["upload_id"]))
                entry["source_names"].add("price_list")

    for profile in photos:
        mentioned_keys = {_name_key(name) for name in profile.get("products_mentioned") or []}
        for key, entry in products.items():
            if key in mentioned_keys:
                entry["photo_count"] += 1
                if str(profile["upload_id"]) not in entry["source_upload_ids"]:
                    entry["source_upload_ids"].append(str(profile["upload_id"]))
                    entry["source_names"].add("photo")

    proposals = []
    for entry in products.values():
        sources_ko = ", ".join(sorted(entry["source_names"]))
        draft = {
            "product_name": entry["product_name"],
            "brand_name": partner_name,
            # Honesty: assemble knows the name, not the category — the
            # partner (or operator) picks it; validation flags it advisory.
            "product_category": "",
            "size": entry["size"],
            "ingredients_raw": entry["ingredients_raw"],
            "key_claims_allowed": [],
            "claims_candidates": [],
            "country_availability": list(_LAUNCH_COUNTRIES),
            "notes": f"자동 조립 초안 (프로필 출처: {sources_ko}) — 제출 전 내용을 확인해 주세요.",
        }
        proposals.append(
            {
                "draft": draft,
                "source_upload_ids": entry["source_upload_ids"],
                "photo_count": entry["photo_count"],
            }
        )

    return {
        "proposals": proposals,
        "skipped_existing": skipped_existing,
        "catalog_profile_count": len(catalogs),
    }
