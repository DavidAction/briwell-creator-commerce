-- Briwell Influencer Intelligence MVP v0.1
-- PostgreSQL schema draft
-- Created: 2026-06-17
-- Rule: MVP v0.1 only allows Low / Low to Medium / Medium Risk sources.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Optional for production vector search if pgvector is installed:
-- CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE country_code AS ENUM ('MX', 'PE', 'EC');
CREATE TYPE source_risk_level AS ENUM ('low', 'low_medium', 'medium', 'high', 'not_allowed');
CREATE TYPE creator_status AS ENUM ('active', 'reviewing', 'approved', 'avoided', 'quarantined', 'do_not_contact', 'removed', 'paused');
CREATE TYPE campaign_status AS ENUM ('draft', 'active', 'paused', 'completed', 'cancelled');
CREATE TYPE outreach_status AS ENUM (
  'discovered',
  'reviewing',
  'approved',
  'contact_found',
  'dm_drafted',
  'dm_sent',
  'replied',
  'negotiating',
  'accepted',
  'sample_sent',
  'content_posted',
  'completed',
  'rejected',
  'paused'
);
CREATE TYPE claims_check_status AS ENUM ('not_checked', 'passed', 'failed', 'needs_review');
CREATE TYPE job_status AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled');
CREATE TYPE user_role AS ENUM ('admin', 'operator', 'campaign_manager', 'viewer');

CREATE TABLE app_user (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL UNIQUE,
  full_name TEXT,
  role user_role NOT NULL DEFAULT 'viewer',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE product_catalog (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_name TEXT NOT NULL,
  product_name TEXT NOT NULL,
  product_category TEXT NOT NULL CHECK (product_category IN (
    'sunscreen',
    'calming_serum',
    'cleanser',
    'sheet_mask',
    'cushion_foundation'
  )),
  country_availability country_code[] NOT NULL DEFAULT '{}',
  key_claims_allowed TEXT[] NOT NULL DEFAULT '{}',
  claims_disallowed TEXT[] NOT NULL DEFAULT '{}',
  target_skin_concerns TEXT[] NOT NULL DEFAULT '{}',
  price_range TEXT,
  sample_available BOOLEAN NOT NULL DEFAULT FALSE,
  landing_url TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'draft')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE keyword_seed (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  country country_code NOT NULL,
  language TEXT NOT NULL DEFAULT 'es',
  keyword TEXT,
  hashtag TEXT,
  product_category TEXT NOT NULL CHECK (product_category IN (
    'sunscreen',
    'calming_serum',
    'cleanser',
    'sheet_mask',
    'cushion_foundation'
  )),
  intent_type TEXT NOT NULL CHECK (intent_type IN ('discovery', 'concern', 'format', 'commerce')),
  priority INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 5),
  notes TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (keyword IS NOT NULL OR hashtag IS NOT NULL)
);

CREATE TABLE scoring_rule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_version TEXT NOT NULL,
  score_dimension TEXT NOT NULL CHECK (score_dimension IN (
    'beauty_fit',
    'engagement_quality',
    'audience_locality',
    'commerce_intent',
    'content_quality',
    'collaboration_probability',
    'cost_efficiency',
    'risk_penalty'
  )),
  weight NUMERIC(5,4) NOT NULL CHECK (weight >= 0 AND weight <= 1),
  min_value NUMERIC(6,2) NOT NULL DEFAULT 0,
  max_value NUMERIC(6,2) NOT NULL DEFAULT 100,
  calculation_notes TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (rule_version, score_dimension)
);

CREATE TABLE ai_model_config (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider TEXT NOT NULL CHECK (provider IN ('google', 'openai', 'anthropic')),
  model_alias TEXT NOT NULL,
  model_id TEXT NOT NULL,
  task_type TEXT NOT NULL,
  default_for_task BOOLEAN NOT NULL DEFAULT FALSE,
  fallback_model_id TEXT,
  input_price_per_mtok NUMERIC(12,6),
  output_price_per_mtok NUMERIC(12,6),
  batch_supported BOOLEAN NOT NULL DEFAULT FALSE,
  flex_supported BOOLEAN NOT NULL DEFAULT FALSE,
  context_window INTEGER,
  last_price_verified_at DATE,
  last_capability_verified_at DATE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'deprecated')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_alias, task_type)
);

CREATE TABLE creator (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  platform TEXT NOT NULL DEFAULT 'tiktok',
  platform_creator_id TEXT,
  country country_code NOT NULL,
  username TEXT NOT NULL,
  display_name TEXT,
  profile_url TEXT NOT NULL,
  bio TEXT,
  language TEXT NOT NULL DEFAULT 'es',
  follower_count INTEGER CHECK (follower_count IS NULL OR follower_count >= 0),
  following_count INTEGER CHECK (following_count IS NULL OR following_count >= 0),
  total_likes INTEGER CHECK (total_likes IS NULL OR total_likes >= 0),
  contact_email TEXT,
  instagram_url TEXT,
  whatsapp TEXT,
  external_links JSONB NOT NULL DEFAULT '[]'::jsonb,
  category_tags TEXT[] NOT NULL DEFAULT '{}',
  source_type TEXT NOT NULL,
  source_url TEXT,
  source_risk_level source_risk_level NOT NULL,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_synced_at TIMESTAMPTZ,
  last_verified_at TIMESTAMPTZ,
  do_not_contact BOOLEAN NOT NULL DEFAULT FALSE,
  removal_requested_at TIMESTAMPTZ,
  status creator_status NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (platform, username),
  CHECK (
    source_risk_level IN ('low', 'low_medium', 'medium')
    OR status = 'quarantined'
  )
);

CREATE TABLE video (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id UUID NOT NULL REFERENCES creator(id) ON DELETE CASCADE,
  platform_video_id TEXT,
  url TEXT NOT NULL,
  caption TEXT,
  hashtags TEXT[] NOT NULL DEFAULT '{}',
  posted_at TIMESTAMPTZ,
  view_count INTEGER CHECK (view_count IS NULL OR view_count >= 0),
  like_count INTEGER CHECK (like_count IS NULL OR like_count >= 0),
  comment_count INTEGER CHECK (comment_count IS NULL OR comment_count >= 0),
  share_count INTEGER CHECK (share_count IS NULL OR share_count >= 0),
  save_count INTEGER CHECK (save_count IS NULL OR save_count >= 0),
  duration_seconds INTEGER CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
  thumbnail_url TEXT,
  transcript TEXT,
  raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_type TEXT NOT NULL,
  source_url TEXT,
  source_risk_level source_risk_level NOT NULL,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_available BOOLEAN NOT NULL DEFAULT TRUE,
  deletion_detected_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (creator_id, platform_video_id),
  CHECK (source_risk_level IN ('low', 'low_medium', 'medium'))
);

CREATE TABLE comment_sample (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID NOT NULL REFERENCES video(id) ON DELETE CASCADE,
  comment_text TEXT NOT NULL,
  comment_language TEXT NOT NULL DEFAULT 'es',
  like_count INTEGER CHECK (like_count IS NULL OR like_count >= 0),
  reply_count INTEGER CHECK (reply_count IS NULL OR reply_count >= 0),
  sentiment TEXT CHECK (sentiment IN ('positive', 'neutral', 'negative', 'mixed')),
  purchase_intent BOOLEAN,
  question_type TEXT CHECK (question_type IN ('where_to_buy', 'price', 'skin_concern', 'usage', 'other')),
  sample_method TEXT NOT NULL CHECK (sample_method IN ('manual', 'official_api', 'approved_provider', 'creator_provided')),
  source_risk_level source_risk_level NOT NULL CHECK (source_risk_level IN ('low', 'low_medium', 'medium')),
  contains_sensitive_data BOOLEAN NOT NULL DEFAULT FALSE,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  sampled_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE creator_analysis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id UUID NOT NULL REFERENCES creator(id) ON DELETE CASCADE,
  analysis_version TEXT NOT NULL,
  beauty_fit_score NUMERIC(5,2) NOT NULL CHECK (beauty_fit_score BETWEEN 0 AND 100),
  engagement_quality_score NUMERIC(5,2) NOT NULL CHECK (engagement_quality_score BETWEEN 0 AND 100),
  audience_locality_score NUMERIC(5,2) NOT NULL CHECK (audience_locality_score BETWEEN 0 AND 100),
  commerce_intent_score NUMERIC(5,2) NOT NULL CHECK (commerce_intent_score BETWEEN 0 AND 100),
  content_quality_score NUMERIC(5,2) NOT NULL CHECK (content_quality_score BETWEEN 0 AND 100),
  collaboration_probability_score NUMERIC(5,2) NOT NULL CHECK (collaboration_probability_score BETWEEN 0 AND 100),
  cost_efficiency_score NUMERIC(5,2) NOT NULL CHECK (cost_efficiency_score BETWEEN 0 AND 100),
  risk_score NUMERIC(5,2) NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
  risk_penalty NUMERIC(5,2) NOT NULL CHECK (risk_penalty BETWEEN 0 AND 30),
  final_score NUMERIC(5,2) NOT NULL CHECK (final_score BETWEEN 0 AND 100),
  segment TEXT NOT NULL CHECK (segment IN (
    'viral_micro',
    'beauty_educator',
    'review_creator',
    'commerce_creator',
    'brand_builder',
    'ugc_creator',
    'avoid'
  )),
  recommended_products TEXT[] NOT NULL DEFAULT '{}',
  recommended_campaign_angle TEXT,
  ai_summary TEXT,
  ai_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  score_confidence NUMERIC(4,3) NOT NULL CHECK (score_confidence BETWEEN 0 AND 1),
  review_required_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (creator_id, analysis_version)
);

CREATE TABLE video_analysis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id UUID NOT NULL REFERENCES video(id) ON DELETE CASCADE,
  analysis_version TEXT NOT NULL,
  content_format TEXT NOT NULL CHECK (content_format IN (
    'review',
    'tutorial',
    'routine',
    'unboxing',
    'before_after',
    'live_clip',
    'meme',
    'educational',
    'other'
  )),
  product_categories TEXT[] NOT NULL DEFAULT '{}',
  visual_quality_score NUMERIC(5,2) CHECK (visual_quality_score BETWEEN 0 AND 100),
  product_demo_quality_score NUMERIC(5,2) CHECK (product_demo_quality_score BETWEEN 0 AND 100),
  trust_signal_score NUMERIC(5,2) CHECK (trust_signal_score BETWEEN 0 AND 100),
  commerce_signal_score NUMERIC(5,2) CHECK (commerce_signal_score BETWEEN 0 AND 100),
  kbeauty_fit_score NUMERIC(5,2) CHECK (kbeauty_fit_score BETWEEN 0 AND 100),
  frame_analysis JSONB NOT NULL DEFAULT '[]'::jsonb,
  notable_scenes JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (video_id, analysis_version)
);

CREATE TABLE campaign (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  product_id UUID REFERENCES product_catalog(id),
  country country_code NOT NULL,
  product_category TEXT NOT NULL,
  campaign_goal TEXT NOT NULL,
  budget NUMERIC(12,2),
  sales_channel TEXT CHECK (sales_channel IN ('tiktok_shop', 'shopify', 'mercado_libre', 'instagram_dm', 'whatsapp', 'reseller_link', 'other')),
  tracking_url TEXT,
  coupon_code_prefix TEXT,
  target_creator_count INTEGER CHECK (target_creator_count IS NULL OR target_creator_count >= 0),
  target_post_count INTEGER CHECK (target_post_count IS NULL OR target_post_count >= 0),
  start_date DATE,
  end_date DATE,
  status campaign_status NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE TABLE outreach (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id UUID NOT NULL REFERENCES creator(id) ON DELETE CASCADE,
  campaign_id UUID REFERENCES campaign(id) ON DELETE SET NULL,
  status outreach_status NOT NULL DEFAULT 'discovered',
  dm_variant TEXT CHECK (dm_variant IN ('soft_intro', 'product_review', 'ugc_collaboration', 'commerce_collaboration')),
  dm_message TEXT,
  claims_check_status claims_check_status NOT NULL DEFAULT 'not_checked',
  generated_model_config_id UUID REFERENCES ai_model_config(id),
  approved_by_user_id UUID REFERENCES app_user(id),
  channel TEXT CHECK (channel IN ('tiktok', 'instagram', 'email', 'whatsapp', 'other')),
  sent_at TIMESTAMPTZ,
  last_contacted_at TIMESTAMPTZ,
  do_not_contact_checked_at TIMESTAMPTZ,
  response_received_at TIMESTAMPTZ,
  response_summary TEXT,
  proposed_terms JSONB NOT NULL DEFAULT '{}'::jsonb,
  operator_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE analysis_job (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_type TEXT NOT NULL CHECK (job_type IN (
    'profile_analysis',
    'comment_analysis',
    'transcription',
    'multimodal_analysis',
    'final_review',
    'dm_generation',
    'claims_check',
    'keyword_import',
    'csv_import'
  )),
  status job_status NOT NULL DEFAULT 'queued',
  source_risk_level source_risk_level NOT NULL CHECK (source_risk_level IN ('low', 'low_medium', 'medium')),
  approval_required BOOLEAN NOT NULL DEFAULT FALSE,
  approved_by_user_id UUID REFERENCES app_user(id),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  error_message TEXT,
  input_count INTEGER NOT NULL DEFAULT 0 CHECK (input_count >= 0),
  success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count >= 0),
  failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
  estimated_cost_usd NUMERIC(12,6),
  actual_cost_usd NUMERIC(12,6),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (
    source_risk_level = 'low'
    OR approval_required = TRUE
  ),
  CHECK (
    approval_required = FALSE
    OR status = 'queued'
    OR approved_by_user_id IS NOT NULL
  )
);

CREATE TABLE ai_invocation_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_job_id UUID REFERENCES analysis_job(id) ON DELETE SET NULL,
  model_config_id UUID REFERENCES ai_model_config(id),
  target_entity_type TEXT NOT NULL CHECK (target_entity_type IN ('creator', 'video', 'comment_sample', 'outreach', 'campaign', 'other')),
  target_entity_id UUID,
  prompt_version TEXT NOT NULL,
  input_token_count INTEGER CHECK (input_token_count IS NULL OR input_token_count >= 0),
  output_token_count INTEGER CHECK (output_token_count IS NULL OR output_token_count >= 0),
  cost_usd NUMERIC(12,6),
  latency_ms INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
  status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'skipped')),
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE operator_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id UUID REFERENCES creator(id) ON DELETE CASCADE,
  analysis_id UUID REFERENCES creator_analysis(id) ON DELETE SET NULL,
  user_id UUID REFERENCES app_user(id),
  feedback_type TEXT NOT NULL CHECK (feedback_type IN ('score_adjustment', 'segment_change', 'dm_edit', 'risk_flag', 'product_match_change', 'other')),
  original_value JSONB,
  corrected_value JSONB,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES app_user(id),
  action_type TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  before_value JSONB,
  after_value JSONB,
  ip_address INET,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_app_user
BEFORE UPDATE ON app_user
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_updated_at_product_catalog
BEFORE UPDATE ON product_catalog
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_updated_at_keyword_seed
BEFORE UPDATE ON keyword_seed
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_updated_at_scoring_rule
BEFORE UPDATE ON scoring_rule
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_updated_at_ai_model_config
BEFORE UPDATE ON ai_model_config
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_updated_at_creator
BEFORE UPDATE ON creator
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_updated_at_video
BEFORE UPDATE ON video
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_updated_at_campaign
BEFORE UPDATE ON campaign
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_updated_at_outreach
BEFORE UPDATE ON outreach
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER set_updated_at_analysis_job
BEFORE UPDATE ON analysis_job
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION prevent_outreach_for_blocked_creator()
RETURNS TRIGGER AS $$
DECLARE
  creator_record creator%ROWTYPE;
BEGIN
  SELECT * INTO creator_record FROM creator WHERE id = NEW.creator_id;

  IF creator_record.do_not_contact THEN
    RAISE EXCEPTION 'Cannot create outreach for do_not_contact creator %', NEW.creator_id;
  END IF;

  IF creator_record.removal_requested_at IS NOT NULL THEN
    RAISE EXCEPTION 'Cannot create outreach for creator with removal request %', NEW.creator_id;
  END IF;

  IF creator_record.source_risk_level IN ('high', 'not_allowed') THEN
    RAISE EXCEPTION 'Cannot create outreach for high or not_allowed source risk creator %', NEW.creator_id;
  END IF;

  IF NEW.status IN ('dm_sent', 'replied', 'negotiating', 'accepted', 'sample_sent', 'content_posted', 'completed') THEN
    IF NEW.claims_check_status <> 'passed' THEN
      RAISE EXCEPTION 'Cannot advance outreach without passed claims check %', NEW.id;
    END IF;

    IF NEW.do_not_contact_checked_at IS NULL THEN
      RAISE EXCEPTION 'Cannot advance outreach without do_not_contact check %', NEW.id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_outreach_for_blocked_creator
BEFORE INSERT OR UPDATE ON outreach
FOR EACH ROW EXECUTE FUNCTION prevent_outreach_for_blocked_creator();

CREATE INDEX idx_creator_country_score ON creator(country, status);
CREATE INDEX idx_creator_source_risk ON creator(source_risk_level);
CREATE INDEX idx_creator_username ON creator(username);
CREATE UNIQUE INDEX idx_keyword_seed_unique
ON keyword_seed (
  country,
  product_category,
  intent_type,
  COALESCE(keyword, ''),
  COALESCE(hashtag, '')
);
CREATE INDEX idx_video_creator_posted ON video(creator_id, posted_at DESC);
CREATE INDEX idx_comment_sample_video ON comment_sample(video_id);
CREATE INDEX idx_creator_analysis_creator_score ON creator_analysis(creator_id, final_score DESC);
CREATE INDEX idx_creator_analysis_segment ON creator_analysis(segment);
CREATE INDEX idx_campaign_country_status ON campaign(country, status);
CREATE INDEX idx_outreach_creator_status ON outreach(creator_id, status);
CREATE INDEX idx_outreach_campaign_status ON outreach(campaign_id, status);
CREATE INDEX idx_analysis_job_status ON analysis_job(status, job_type);
CREATE INDEX idx_ai_invocation_job ON ai_invocation_log(analysis_job_id);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);

CREATE VIEW eligible_creator_for_outreach AS
SELECT
  c.*
FROM creator c
WHERE c.source_risk_level IN ('low', 'low_medium', 'medium')
  AND c.status NOT IN ('quarantined', 'do_not_contact', 'removed', 'avoided')
  AND c.do_not_contact = FALSE
  AND c.removal_requested_at IS NULL;

CREATE VIEW latest_creator_analysis AS
SELECT DISTINCT ON (ca.creator_id)
  ca.*
FROM creator_analysis ca
ORDER BY ca.creator_id, ca.created_at DESC;

-- QA notes:
-- Pass 1: All PRD data model entities are represented.
-- Pass 2: High Risk creation is blocked for jobs/videos/comments and quarantined for imported creators.
-- Pass 3: Outreach has DB-level protection for do_not_contact, removal requests, source risk, claims check, and approved source-risk jobs.
