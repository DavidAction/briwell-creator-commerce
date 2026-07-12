"""Real-database round-trip verification for the Brand Partner Hub (P9).

Drives the actual FastAPI app against the live PostgreSQL configured in
DATABASE_URL (USE_DATABASE=true required): partner -> token -> uploads ->
ingest worker -> extract draft -> submit -> operator approve ->
product_catalog. Every step asserts on real persisted state, so this catches
what mock-path tests cannot (migration drift, SQL typos, jsonb casts).

Run (PowerShell):
    $env:DATABASE_URL = "postgresql://briwell:<pw>@127.0.0.1:55432/briwell"
    $env:USE_DATABASE = "true"
    .venv/Scripts/python.exe -m scripts.verify_partner_hub_roundtrip

The script writes throwaway rows prefixed with a timestamp; it is meant for
local/dev databases, not production.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def fail(step: str, detail: str) -> None:
    print(f"FAIL [{step}] {detail}")
    raise SystemExit(1)


def main() -> int:
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.core.db import connection
    from app.main import app
    from app.workers.job_handlers import JOB_HANDLERS
    from app.workers.job_queue import process_one

    if not settings.use_database:
        fail("precondition", "USE_DATABASE=true is required for the round trip.")

    client = TestClient(app)
    operator = {"X-User-Role": "operator", "X-User-Email": "roundtrip@briwell.test"}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    company = f"왕복검증 파트너 {stamp}"

    # 1. partner ------------------------------------------------------------
    response = client.post("/partners", headers=operator, json={"company_name": company})
    if response.status_code != 200 or response.json().get("status") != "persisted":
        fail("partner", f"{response.status_code} {response.text}")
    partner_id = response.json()["partner"]["id"]
    print(f"ok  partner persisted: {partner_id}")

    # 2. token (P1: sha256 at rest + expiry) ---------------------------------
    response = client.post("/partners/tokens", headers=operator, json={"partner_id": partner_id})
    body = response.json()
    if response.status_code != 200 or body.get("status") != "persisted":
        fail("token", f"{response.status_code} {response.text}")
    token = body["token"]
    if not body.get("expires_at"):
        fail("token", "expires_at missing from issue response")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT token_sha256, expires_at FROM brand_partner_token WHERE id = %s",
                (body["token_id"],),
            )
            row = cur.fetchone()
    if row is None or row["token_sha256"] == token:
        fail("token", "token stored in plaintext (or row missing)")
    if row["expires_at"] is None:
        fail("token", "expires_at not persisted")
    print(f"ok  token issued (digest at rest, expires {row['expires_at']:%Y-%m-%d})")

    auth = {"Authorization": f"Bearer {token}"}

    # 3. hub self-view via Authorization header (P1) --------------------------
    response = client.get("/partner-hub/me", headers=auth)
    if response.status_code != 200:
        fail("hub_me", f"{response.status_code} {response.text}")
    if response.json()["hub"]["partner"]["company_name"] != company:
        fail("hub_me", "company mismatch")
    print("ok  hub /me via Authorization header")

    # 4. uploads (photo + pdf) ------------------------------------------------
    jpg = b"\xff\xd8\xff\xe0" + b"roundtrip-jpg" * 8
    pdf = b"%PDF-1.7\n" + b"roundtrip-catalog" * 8
    upload_ids: list[str] = []
    for kind, name, payload, mime in (
        ("photo", "roundtrip_white_bg.jpg", jpg, "image/jpeg"),
        ("pdf", "roundtrip_catalog_2026.pdf", pdf, "application/pdf"),
    ):
        response = client.post(
            f"/partner-hub/uploads?kind={kind}",
            headers=auth,
            files={"file": (name, payload, mime)},
        )
        if response.status_code != 200:
            fail("upload", f"{kind}: {response.status_code} {response.text}")
        upload_ids.append(response.json()["upload"]["id"])
    print(f"ok  uploads stored: {len(upload_ids)}")

    # 5. ingest worker drains the queued partner_asset_ingest jobs ------------
    processed = 0
    with connection() as conn:
        while process_one(conn, JOB_HANDLERS):
            processed += 1
            if processed > 50:
                fail("worker", "job queue did not drain (>50 jobs)")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, doc_type FROM partner_asset_profile
                WHERE partner_id = %s
                """,
                (partner_id,),
            )
            profiles = cur.fetchall()
    if len(profiles) != len(upload_ids):
        fail("worker", f"expected {len(upload_ids)} profiles, found {len(profiles)}")
    bad = [p for p in profiles if p["status"] != "done"]
    if bad:
        fail("worker", f"profiles not done: {bad}")
    print(f"ok  ingest worker processed {processed} job(s); profiles done: "
          f"{sorted(p['doc_type'] for p in profiles)}")

    # 5b. P2 dedup: re-uploading identical bytes returns the existing record --
    response = client.post(
        "/partner-hub/uploads?kind=photo",
        headers=auth,
        files={"file": ("roundtrip_white_bg_copy.jpg", jpg, "image/jpeg")},
    )
    if response.status_code != 200 or response.json().get("status") != "duplicate":
        fail("dedup", f"{response.status_code} {response.text}")
    if response.json()["upload"]["id"] != upload_ids[0]:
        fail("dedup", "duplicate did not resolve to the original upload record")
    print("ok  same-sha re-upload deduplicated to the original record")

    # 5c. P6 file serving: partner + operator get the original back -----------
    response = client.get(f"/partner-hub/uploads/{upload_ids[0]}/file", headers=auth)
    if response.status_code != 200 or response.content != jpg:
        fail("file", f"partner file fetch: {response.status_code}")
    if response.headers.get("x-content-type-options") != "nosniff":
        fail("file", "nosniff header missing")
    if not response.headers.get("content-disposition", "").startswith("attachment"):
        fail("file", "attachment disposition missing")
    response = client.get(f"/partners/uploads/{upload_ids[1]}/file", headers=operator)
    if response.status_code != 200 or response.content != pdf:
        fail("file", f"operator file fetch: {response.status_code}")
    print("ok  authenticated file serving (partner + operator, nosniff/attachment)")

    # 5d. P7 assemble: catalog profile -> drafts through the enrich pipeline ---
    response = client.post("/partner-hub/assemble", headers=auth)
    if response.status_code != 200:
        fail("assemble", f"{response.status_code} {response.text}")
    assembled = response.json()["created"]
    if not assembled:
        fail("assemble", "no drafts assembled from the catalog profile")
    if assembled[0]["ai_meta"]["mode"] != "assembled":
        fail("assemble", "assembled draft missing assembled ai_meta mode")
    print(f"ok  assemble created {len(assembled)} draft(s) from analyzed profiles")

    # 6. extract -> draft ------------------------------------------------------
    response = client.post(
        "/partner-hub/uploads/extract", headers=auth, json={"upload_ids": upload_ids}
    )
    if response.status_code != 200:
        fail("extract", f"{response.status_code} {response.text}")
    draft = response.json()["draft"]
    draft_id = draft["id"]
    print(f"ok  draft created: {draft_id} ({draft['draft'].get('product_name')})")

    # 7. partner submits -------------------------------------------------------
    response = client.post(
        f"/partner-hub/drafts/{draft_id}",
        headers=auth,
        json={
            "draft": {"product_category": "calming_serum", "key_claims_allowed": ["수분 보습"]},
            "action": "submit",
        },
    )
    if response.status_code != 200 or response.json()["draft"]["status"] != "partner_confirmed":
        fail("submit", f"{response.status_code} {response.text}")
    print("ok  draft submitted (partner_confirmed)")

    # 8. operator queue + approval ---------------------------------------------
    response = client.get("/partners/review-queue", headers=operator)
    queue_ids = {item["draft_id"] for item in response.json().get("items", [])}
    if draft_id not in queue_ids:
        fail("queue", "submitted draft missing from review queue")
    response = client.post(
        f"/partners/review/{draft_id}", headers=operator, json={"decision": "approved"}
    )
    if response.status_code != 200 or response.json().get("decision") != "approved":
        fail("approve", f"{response.status_code} {response.text}")
    product_id = response.json()["product"]["id"]
    print(f"ok  approved -> product_catalog {product_id}")

    # 9. the promoted product really exists in product_catalog ------------------
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT product_name, brand_name FROM product_catalog WHERE id = %s",
                (product_id,),
            )
            product = cur.fetchone()
            cur.execute(
                "SELECT decision, decided_by FROM partner_review_decision WHERE draft_id = %s",
                (draft_id,),
            )
            decision = cur.fetchone()
    if product is None:
        fail("catalog", "promoted product not found in product_catalog")
    if decision is None or decision["decision"] != "approved":
        fail("catalog", "review decision not recorded")
    print(f"ok  product_catalog row: {product['product_name']} / decision by "
          f"{decision['decided_by']}")

    print("ROUND TRIP PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
