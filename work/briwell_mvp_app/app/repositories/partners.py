"""Repository functions for the Brand Partner Hub (migration 010).

Pure SQL following the app/repositories/*.py convention. Partner-scoped
readers always require partner_id so ownership is enforced at the query
level, not just in the router.
"""

import json
from typing import Any

from app.core.db import connection, fetch_all, fetch_one


# --- partners -----------------------------------------------------------------

def create_partner(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO brand_partner (company_name, contact_name, contact_email, internal_memo)
        VALUES (%(company_name)s, %(contact_name)s, %(contact_email)s, %(internal_memo)s)
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("brand_partner insert did not return a row.")
    return created


def get_partner_by_id(partner_id: str) -> dict[str, Any] | None:
    return fetch_one(
        "SELECT * FROM brand_partner WHERE id = %(partner_id)s",
        {"partner_id": partner_id},
    )


def list_partners() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT id, company_name, contact_name, contact_email, internal_memo,
               status, created_at
        FROM brand_partner
        ORDER BY created_at DESC
        LIMIT 200
        """,
        {},
    )


# --- tokens (mirrors app/repositories/portal.py) --------------------------------

def issue_token(partner_id: str, token: str) -> dict[str, Any]:
    """Revoke any active tokens for the partner, then persist the new one."""

    revoke_query = """
        UPDATE brand_partner_token
        SET status = 'revoked', revoked_at = now()
        WHERE partner_id = %(partner_id)s AND status = 'active'
    """
    insert_query = """
        INSERT INTO brand_partner_token (partner_id, token)
        VALUES (%(partner_id)s, %(token)s)
        RETURNING *
    """
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(revoke_query, {"partner_id": partner_id})
            cur.execute(insert_query, {"partner_id": partner_id, "token": token})
            row = cur.fetchone()
        conn.commit()
    if row is None:
        raise RuntimeError("brand_partner_token insert did not return a row.")
    return dict(row)


def get_active_by_token(token: str) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT * FROM brand_partner_token
        WHERE token = %(token)s AND status = 'active'
        LIMIT 1
        """,
        {"token": token},
    )


def touch_last_seen(token_id: str) -> None:
    query = """
        UPDATE brand_partner_token
        SET last_seen_at = now()
        WHERE id = %(token_id)s
    """
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, {"token_id": token_id})
        conn.commit()


def revoke_for_partner(partner_id: str) -> int:
    rows = fetch_all(
        """
        UPDATE brand_partner_token
        SET status = 'revoked', revoked_at = now()
        WHERE partner_id = %(partner_id)s AND status = 'active'
        RETURNING id
        """,
        {"partner_id": partner_id},
    )
    return len(rows)


# --- uploads --------------------------------------------------------------------

def record_upload(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO partner_upload (
            partner_id, kind, original_filename, content_type,
            byte_size, sha256, storage_path
        ) VALUES (
            %(partner_id)s, %(kind)s, %(original_filename)s, %(content_type)s,
            %(byte_size)s, %(sha256)s, %(storage_path)s
        )
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("partner_upload insert did not return a row.")
    return created


def list_uploads_for_partner(partner_id: str) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT id, kind, original_filename, content_type, byte_size,
               sha256, status, uploaded_at
        FROM partner_upload
        WHERE partner_id = %(partner_id)s
        ORDER BY uploaded_at DESC
        LIMIT 200
        """,
        {"partner_id": partner_id},
    )


def get_uploads_for_partner(partner_id: str, upload_ids: list[str]) -> list[dict[str, Any]]:
    if not upload_ids:
        return []
    return fetch_all(
        """
        SELECT * FROM partner_upload
        WHERE partner_id = %(partner_id)s AND id = ANY(%(upload_ids)s::uuid[])
        """,
        {"partner_id": partner_id, "upload_ids": upload_ids},
    )


def get_upload(upload_id: str) -> dict[str, Any] | None:
    """Unscoped fetch for the ingestion worker (job payload carries the id)."""

    return fetch_one(
        "SELECT * FROM partner_upload WHERE id = %(upload_id)s",
        {"upload_id": upload_id},
    )


def mark_uploads_status(upload_ids: list[str], status: str) -> None:
    if not upload_ids:
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE partner_upload SET status = %(status)s
                WHERE id = ANY(%(upload_ids)s::uuid[])
                """,
                {"upload_ids": upload_ids, "status": status},
            )
        conn.commit()


# --- asset profiles (migration 011, one per upload) -------------------------------

_PROFILE_COLUMNS = (
    "doc_type",
    "language",
    "confidence",
    "summary_ko",
    "extracted",
    "products_mentioned",
    "status",
    "error",
    "model",
    "prompt_version",
    "usage",
)
_PROFILE_JSONB_COLUMNS = {"extracted", "usage"}


def upsert_asset_profile(
    upload_id: str,
    partner_id: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    """Insert-or-update the single profile for an upload.

    Only allowlisted columns are written; keys absent from ``fields`` keep
    their current value on update (re-analysis replaces in place)."""

    columns = [column for column in _PROFILE_COLUMNS if column in fields]
    params: dict[str, Any] = {"upload_id": upload_id, "partner_id": partner_id}
    placeholders: list[str] = []
    for column in columns:
        value = fields[column]
        if column in _PROFILE_JSONB_COLUMNS and value is not None:
            value = json.dumps(value)
        params[column] = value
        placeholders.append(
            f"%({column})s::jsonb" if column in _PROFILE_JSONB_COLUMNS else f"%({column})s"
        )

    insert_columns = ", ".join(["upload_id", "partner_id", *columns])
    insert_values = ", ".join(["%(upload_id)s", "%(partner_id)s", *placeholders])
    update_clause = ", ".join(
        [f'"{column}" = EXCLUDED."{column}"' for column in columns] + ["updated_at = now()"]
    )
    query = f"""
        INSERT INTO partner_asset_profile ({insert_columns})
        VALUES ({insert_values})
        ON CONFLICT (upload_id) DO UPDATE SET {update_clause}
        RETURNING *
    """
    created = fetch_one(query, params)
    if created is None:
        raise RuntimeError("partner_asset_profile upsert did not return a row.")
    return created


def list_asset_profiles_for_partner(partner_id: str) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT upload_id, doc_type, status, confidence, summary_ko,
               products_mentioned, updated_at
        FROM partner_asset_profile
        WHERE partner_id = %(partner_id)s
        """,
        {"partner_id": partner_id},
    )


# --- drafts ---------------------------------------------------------------------

def create_draft(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO partner_product_draft (
            partner_id, source_upload_ids, draft, ai_meta, completeness, regulatory_flags
        ) VALUES (
            %(partner_id)s, %(source_upload_ids)s::uuid[], %(draft)s::jsonb,
            %(ai_meta)s::jsonb, %(completeness)s::jsonb, %(regulatory_flags)s::jsonb
        )
        RETURNING *
    """
    created = fetch_one(
        query,
        {
            "partner_id": payload["partner_id"],
            "source_upload_ids": payload.get("source_upload_ids") or [],
            "draft": json.dumps(payload["draft"]),
            "ai_meta": json.dumps(payload.get("ai_meta")),
            "completeness": json.dumps(payload.get("completeness")),
            "regulatory_flags": json.dumps(payload.get("regulatory_flags")),
        },
    )
    if created is None:
        raise RuntimeError("partner_product_draft insert did not return a row.")
    return created


def get_draft_for_partner(draft_id: str, partner_id: str) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT * FROM partner_product_draft
        WHERE id = %(draft_id)s AND partner_id = %(partner_id)s
        """,
        {"draft_id": draft_id, "partner_id": partner_id},
    )


def get_draft(draft_id: str) -> dict[str, Any] | None:
    return fetch_one(
        "SELECT * FROM partner_product_draft WHERE id = %(draft_id)s",
        {"draft_id": draft_id},
    )


def list_drafts_for_partner(partner_id: str) -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT id, draft, ai_meta, completeness, regulatory_flags, status,
               promoted_product_id, created_at, updated_at
        FROM partner_product_draft
        WHERE partner_id = %(partner_id)s
        ORDER BY updated_at DESC
        LIMIT 200
        """,
        {"partner_id": partner_id},
    )


def update_draft_content(
    draft_id: str,
    partner_id: str,
    draft: dict[str, Any],
    completeness: dict[str, Any],
    regulatory_flags: dict[str, Any],
    status: str,
) -> dict[str, Any] | None:
    return fetch_one(
        """
        UPDATE partner_product_draft
        SET draft = %(draft)s::jsonb,
            completeness = %(completeness)s::jsonb,
            regulatory_flags = %(regulatory_flags)s::jsonb,
            status = %(status)s,
            updated_at = now()
        WHERE id = %(draft_id)s AND partner_id = %(partner_id)s
          AND status IN ('ai_draft', 'partner_confirmed')
        RETURNING *
        """,
        {
            "draft_id": draft_id,
            "partner_id": partner_id,
            "draft": json.dumps(draft),
            "completeness": json.dumps(completeness),
            "regulatory_flags": json.dumps(regulatory_flags),
            "status": status,
        },
    )


def list_review_queue() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT d.id, d.partner_id, p.company_name, d.draft, d.ai_meta,
               d.completeness, d.regulatory_flags, d.status, d.updated_at
        FROM partner_product_draft d
        JOIN brand_partner p ON p.id = d.partner_id
        WHERE d.status = 'partner_confirmed'
        ORDER BY d.updated_at ASC
        LIMIT 100
        """,
        {},
    )


def finalize_draft(
    draft_id: str,
    status: str,
    promoted_product_id: str | None,
) -> dict[str, Any] | None:
    return fetch_one(
        """
        UPDATE partner_product_draft
        SET status = %(status)s,
            promoted_product_id = %(promoted_product_id)s,
            updated_at = now()
        WHERE id = %(draft_id)s AND status = 'partner_confirmed'
        RETURNING *
        """,
        {
            "draft_id": draft_id,
            "status": status,
            "promoted_product_id": promoted_product_id,
        },
    )


def record_review_decision(payload: dict[str, Any]) -> dict[str, Any]:
    query = """
        INSERT INTO partner_review_decision (draft_id, decision, reason, decided_by)
        VALUES (%(draft_id)s, %(decision)s, %(reason)s, %(decided_by)s)
        RETURNING *
    """
    created = fetch_one(query, payload)
    if created is None:
        raise RuntimeError("partner_review_decision insert did not return a row.")
    return created
