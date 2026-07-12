-- 010: Brand Partner Hub (briefing 0.0.19 plan -> 0.0.20 implementation).
-- Brand clients (Korean cosmetics companies) upload catalogs, photos and
-- spec/ingredient data through a tokenized partner surface; the AI pipeline
-- structures uploads into product drafts; an operator approves drafts into
-- the existing product_catalog. Originals are preserved verbatim (audit
-- trail) and are never deleted by application code.
--
-- The INCI dictionary and regulatory rules are code-seeded in
-- app/partners/ingredient_data.py for Phase 1 (works without a database,
-- no seed drift); promoting them to tables is a Phase 2+ decision.

CREATE TABLE IF NOT EXISTS brand_partner (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT NOT NULL UNIQUE,
    contact_name TEXT,
    contact_email TEXT,
    -- Operator-only field: excluded from every partner-facing response by
    -- the router's field whitelist (same discipline as the creator portal).
    internal_memo TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Same shape as creator_portal_token (migration 009): one active token per
-- partner, rotation revokes every previously shared link (kill switch).
CREATE TABLE IF NOT EXISTS brand_partner_token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID NOT NULL REFERENCES brand_partner(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_brand_partner_token_partner
    ON brand_partner_token (partner_id);

CREATE INDEX IF NOT EXISTS idx_brand_partner_token_active
    ON brand_partner_token (status)
    WHERE status = 'active';

-- Uploads arrive in three separated lanes by David's decision: photos,
-- PDF catalogs, and spec/ingredient data files. kind gates which file
-- types/magic bytes are accepted at the API boundary.
CREATE TABLE IF NOT EXISTS partner_upload (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID NOT NULL REFERENCES brand_partner(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('photo', 'pdf', 'data')),
    original_filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    byte_size BIGINT NOT NULL,
    sha256 TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'extracted', 'failed')),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_partner_upload_partner
    ON partner_upload (partner_id, uploaded_at DESC);

-- AI drafts + partner edits. draft/ai_meta/completeness/regulatory_flags are
-- JSONB because the draft shape evolves with the extraction prompt version;
-- the approved shape is fixed at promotion time by ProductCreateRequest.
CREATE TABLE IF NOT EXISTS partner_product_draft (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID NOT NULL REFERENCES brand_partner(id) ON DELETE CASCADE,
    source_upload_ids UUID[] NOT NULL DEFAULT '{}',
    draft JSONB NOT NULL,
    ai_meta JSONB,
    completeness JSONB,
    regulatory_flags JSONB,
    status TEXT NOT NULL DEFAULT 'ai_draft'
        CHECK (status IN ('ai_draft', 'partner_confirmed', 'approved', 'rejected')),
    promoted_product_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_partner_product_draft_partner
    ON partner_product_draft (partner_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_partner_product_draft_status
    ON partner_product_draft (status);

-- Human-gate record: every approve/reject is attributable (who, when, why).
CREATE TABLE IF NOT EXISTS partner_review_decision (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id UUID NOT NULL REFERENCES partner_product_draft(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    reason TEXT,
    decided_by TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_partner_review_decision_draft
    ON partner_review_decision (draft_id, decided_at DESC);
