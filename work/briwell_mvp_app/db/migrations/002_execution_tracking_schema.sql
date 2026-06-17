-- Briwell campaign execution, tracking, settlement, and compliance schema.
-- Created: 2026-06-17

CREATE TYPE contract_status AS ENUM ('draft', 'sent', 'accepted', 'cancelled', 'completed');
CREATE TYPE payout_status AS ENUM ('pending', 'approved', 'paid', 'blocked', 'cancelled');

CREATE TABLE campaign_performance_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id UUID REFERENCES campaign(id) ON DELETE SET NULL,
  outreach_id UUID REFERENCES outreach(id) ON DELETE SET NULL,
  creator_id UUID REFERENCES creator(id) ON DELETE SET NULL,
  post_url TEXT,
  platform TEXT NOT NULL DEFAULT 'tiktok' CHECK (platform IN ('tiktok', 'instagram', 'other')),
  tracking_url TEXT,
  coupon_code TEXT,
  view_count INTEGER CHECK (view_count IS NULL OR view_count >= 0),
  like_count INTEGER CHECK (like_count IS NULL OR like_count >= 0),
  comment_count INTEGER CHECK (comment_count IS NULL OR comment_count >= 0),
  share_count INTEGER CHECK (share_count IS NULL OR share_count >= 0),
  click_count INTEGER CHECK (click_count IS NULL OR click_count >= 0),
  conversion_count INTEGER CHECK (conversion_count IS NULL OR conversion_count >= 0),
  revenue_usd NUMERIC(12,2) CHECK (revenue_usd IS NULL OR revenue_usd >= 0),
  source_type TEXT NOT NULL CHECK (source_type IN ('manual', 'official_api', 'approved_provider', 'creator_provided')),
  source_risk_level source_risk_level NOT NULL CHECK (source_risk_level IN ('low', 'low_medium', 'medium')),
  measured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE creator_contract (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  outreach_id UUID REFERENCES outreach(id) ON DELETE SET NULL,
  creator_id UUID REFERENCES creator(id) ON DELETE CASCADE,
  campaign_id UUID REFERENCES campaign(id) ON DELETE SET NULL,
  deliverables JSONB NOT NULL DEFAULT '{}'::jsonb,
  compensation_terms JSONB NOT NULL DEFAULT '{}'::jsonb,
  due_date DATE,
  status contract_status NOT NULL DEFAULT 'draft',
  contract_url TEXT,
  operator_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE creator_payout (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID REFERENCES creator_contract(id) ON DELETE SET NULL,
  creator_id UUID REFERENCES creator(id) ON DELETE CASCADE,
  campaign_id UUID REFERENCES campaign(id) ON DELETE SET NULL,
  amount_usd NUMERIC(12,2) NOT NULL CHECK (amount_usd >= 0),
  payout_status payout_status NOT NULL DEFAULT 'pending',
  payout_method TEXT CHECK (payout_method IN ('bank_transfer', 'paypal', 'payoneer', 'mercado_pago', 'other')),
  invoice_url TEXT,
  tax_document_url TEXT,
  blocker_reason TEXT,
  approved_at TIMESTAMPTZ,
  paid_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE compliance_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  country country_code NOT NULL,
  product_category TEXT NOT NULL CHECK (product_category IN (
    'sunscreen',
    'calming_serum',
    'cleanser',
    'sheet_mask',
    'cushion_foundation'
  )),
  rule_type TEXT NOT NULL CHECK (rule_type IN ('allowed_claim', 'review_claim', 'blocked_claim', 'disclosure')),
  phrase TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
  notes TEXT,
  source_reference TEXT,
  legal_review_required BOOLEAN NOT NULL DEFAULT TRUE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'draft')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (country, product_category, rule_type, phrase)
);

CREATE INDEX idx_performance_campaign_measured ON campaign_performance_snapshot(campaign_id, measured_at DESC);
CREATE INDEX idx_contract_campaign_status ON creator_contract(campaign_id, status);
CREATE INDEX idx_payout_campaign_status ON creator_payout(campaign_id, payout_status);
CREATE INDEX idx_compliance_country_category ON compliance_rule(country, product_category, status);
