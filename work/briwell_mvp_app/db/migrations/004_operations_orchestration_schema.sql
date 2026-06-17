-- Briwell operations orchestration schema.
-- Captures import QA, profile enrichment, recent-post screening, and CRM events.

CREATE TABLE import_quality_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  upload_name TEXT,
  dataset_type TEXT NOT NULL CHECK (dataset_type IN ('creator_candidates', 'recent_posts', 'mixed')),
  source_type TEXT NOT NULL CHECK (source_type IN ('manual', 'official_api', 'approved_provider', 'creator_provided')),
  source_risk_level source_risk_level NOT NULL CHECK (source_risk_level IN ('low', 'low_medium', 'medium')),
  creator_count INTEGER NOT NULL DEFAULT 0 CHECK (creator_count >= 0),
  post_count INTEGER NOT NULL DEFAULT 0 CHECK (post_count >= 0),
  quality_status TEXT NOT NULL CHECK (quality_status IN ('ready', 'needs_review', 'blocked')),
  blocker_count INTEGER NOT NULL DEFAULT 0 CHECK (blocker_count >= 0),
  warning_count INTEGER NOT NULL DEFAULT 0 CHECK (warning_count >= 0),
  quality_gate JSONB NOT NULL DEFAULT '{}'::jsonb,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by_email TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE creator_profile_enrichment (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id UUID REFERENCES creator(id) ON DELETE CASCADE,
  username TEXT,
  source_risk_level source_risk_level NOT NULL CHECK (source_risk_level IN ('low', 'low_medium', 'medium')),
  primary_country TEXT NOT NULL,
  country_confidence NUMERIC(4,3) NOT NULL CHECK (country_confidence BETWEEN 0 AND 1),
  language TEXT NOT NULL DEFAULT 'es',
  platforms TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  contact_channels TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  normalized_categories TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  commerce_readiness TEXT NOT NULL CHECK (commerce_readiness IN ('commerce_ready', 'audience_ready', 'needs_validation')),
  duplicate_key TEXT,
  missing_data TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  enrichment_status TEXT NOT NULL CHECK (enrichment_status IN ('ready', 'needs_review', 'blocked')),
  next_action TEXT NOT NULL,
  enrichment_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (creator_id)
);

CREATE TABLE recent_posts_screen_result (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id UUID REFERENCES creator(id) ON DELETE CASCADE,
  source_risk_level source_risk_level NOT NULL CHECK (source_risk_level IN ('low', 'low_medium', 'medium')),
  post_count_analyzed INTEGER NOT NULL DEFAULT 0 CHECK (post_count_analyzed >= 0),
  suitability_decision TEXT NOT NULL CHECK (
    suitability_decision IN ('pass_to_full_analysis', 'human_review', 'recheck_later', 'avoid')
  ),
  suitability_score NUMERIC(5,2) NOT NULL CHECK (suitability_score BETWEEN 0 AND 100),
  matched_product_categories TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  coverage_gaps TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  risk_notes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  next_step TEXT,
  result_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE outreach_crm_event (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  outreach_id UUID REFERENCES outreach(id) ON DELETE SET NULL,
  creator_id UUID REFERENCES creator(id) ON DELETE SET NULL,
  campaign_id UUID REFERENCES campaign(id) ON DELETE SET NULL,
  from_status TEXT,
  to_status TEXT,
  event_type TEXT NOT NULL DEFAULT 'crm_board_snapshot',
  event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  operator_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_import_quality_created ON import_quality_log(created_at DESC);
CREATE INDEX idx_creator_enrichment_status ON creator_profile_enrichment(enrichment_status, primary_country);
CREATE INDEX idx_recent_screen_creator_created ON recent_posts_screen_result(creator_id, created_at DESC);
CREATE INDEX idx_recent_screen_decision ON recent_posts_screen_result(suitability_decision, suitability_score DESC);
CREATE INDEX idx_outreach_crm_event_campaign ON outreach_crm_event(campaign_id, created_at DESC);
