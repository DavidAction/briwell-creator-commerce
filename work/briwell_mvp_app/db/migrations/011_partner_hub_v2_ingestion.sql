-- 011: Partner Hub v2 (design doc outputs/briwell_partner_hub_v2_design.md,
-- David-approved 2026-07-12): a fourth 'etc' upload lane (documents only:
-- docx/pptx/hwp/hwpx/txt) and AI ingestion profiles — every upload is
-- auto-classified and extracted into an optimized, queryable shape.

-- The inline CHECK from migration 010 was auto-named by Postgres.
ALTER TABLE partner_upload DROP CONSTRAINT IF EXISTS partner_upload_kind_check;
ALTER TABLE partner_upload ADD CONSTRAINT partner_upload_kind_check
    CHECK (kind IN ('photo', 'pdf', 'data', 'etc'));

-- One profile per upload (re-analysis replaces in place; history lives in
-- ai_invocation_log). doc_type 'needs_review' is the honest low-confidence
-- bucket that routes to the operator instead of guessing.
CREATE TABLE IF NOT EXISTS partner_asset_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id UUID NOT NULL UNIQUE REFERENCES partner_upload(id) ON DELETE CASCADE,
    partner_id UUID NOT NULL REFERENCES brand_partner(id) ON DELETE CASCADE,
    doc_type TEXT NOT NULL DEFAULT 'pending' CHECK (doc_type IN (
        'pending', 'product_catalog', 'ingredient_list', 'price_list',
        'certificate', 'brand_intro', 'press', 'photo_asset', 'other',
        'needs_review')),
    language TEXT,
    confidence NUMERIC,
    summary_ko TEXT,
    extracted JSONB,
    products_mentioned TEXT[] NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    error TEXT,
    model TEXT,
    prompt_version TEXT,
    usage JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_partner_asset_profile_partner
    ON partner_asset_profile (partner_id, doc_type);

CREATE INDEX IF NOT EXISTS idx_partner_asset_profile_status
    ON partner_asset_profile (status);
