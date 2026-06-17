-- Briwell Influencer Intelligence MVP v0.1
-- Seed data for scoring rules and AI model registry.
-- Created: 2026-06-17
-- Note: Prices must be re-verified before production deployment.

INSERT INTO scoring_rule (
  rule_version,
  score_dimension,
  weight,
  min_value,
  max_value,
  calculation_notes,
  active
) VALUES
  ('v0.1', 'beauty_fit', 0.2500, 0, 100, 'K-beauty, skincare, makeup, and product-category fit.', TRUE),
  ('v0.1', 'engagement_quality', 0.2000, 0, 100, 'Comment quality, question ratio, purchase intent, views relative to followers.', TRUE),
  ('v0.1', 'audience_locality', 0.1500, 0, 100, 'Mexico, Peru, or Ecuador audience fit based on profile, language, hashtags, comments.', TRUE),
  ('v0.1', 'commerce_intent', 0.1500, 0, 100, 'Coupon, link, live, product review, and where-to-buy signals.', TRUE),
  ('v0.1', 'content_quality', 0.1000, 0, 100, 'Video clarity, product demonstration, explanation quality, reusable UGC quality.', TRUE),
  ('v0.1', 'collaboration_probability', 0.1000, 0, 100, 'Contact availability, sponsorship experience, recent activity, response likelihood.', TRUE),
  ('v0.1', 'cost_efficiency', 0.0500, 0, 100, 'Expected cost versus likely reach, content value, and conversion potential.', TRUE),
  ('v0.1', 'risk_penalty', 0.0000, 0, 30, 'Separate 0-30 point deduction. Not included in Base Score weights.', TRUE)
ON CONFLICT (rule_version, score_dimension) DO UPDATE SET
  weight = EXCLUDED.weight,
  min_value = EXCLUDED.min_value,
  max_value = EXCLUDED.max_value,
  calculation_notes = EXCLUDED.calculation_notes,
  active = EXCLUDED.active,
  updated_at = now();

INSERT INTO ai_model_config (
  provider,
  model_alias,
  model_id,
  task_type,
  default_for_task,
  fallback_model_id,
  input_price_per_mtok,
  output_price_per_mtok,
  batch_supported,
  flex_supported,
  context_window,
  last_price_verified_at,
  last_capability_verified_at,
  status
) VALUES
  ('google', 'low_cost_text', 'gemini-3.1-flash-lite', 'profile_analysis', TRUE, 'gemini-3-flash', NULL, NULL, TRUE, TRUE, NULL, '2026-06-17', '2026-06-17', 'active'),
  ('google', 'low_cost_text', 'gemini-3.1-flash-lite', 'comment_analysis', TRUE, 'gemini-3-flash', NULL, NULL, TRUE, TRUE, NULL, '2026-06-17', '2026-06-17', 'active'),
  ('google', 'multimodal_default', 'gemini-3-flash', 'multimodal_analysis', TRUE, 'gemini-3.5-flash', NULL, NULL, TRUE, TRUE, NULL, '2026-06-17', '2026-06-17', 'active'),
  ('google', 'final_review', 'gemini-3.5-flash', 'final_review', TRUE, 'gemini-3-flash', NULL, NULL, TRUE, FALSE, NULL, '2026-06-17', '2026-06-17', 'active'),
  ('openai', 'transcription_default', 'gpt-4o-mini-transcribe', 'transcription', TRUE, NULL, NULL, NULL, FALSE, FALSE, NULL, '2026-06-17', '2026-06-17', 'active'),
  ('openai', 'moderation_default', 'omni-moderation-latest', 'claims_check', TRUE, 'gemini-3.1-flash-lite', NULL, NULL, FALSE, FALSE, NULL, '2026-06-17', '2026-06-17', 'active'),
  ('openai', 'text_embedding', 'text-embedding-3-small', 'text_embedding', TRUE, NULL, NULL, NULL, FALSE, FALSE, NULL, '2026-06-17', '2026-06-17', 'active'),
  ('google', 'multimodal_embedding', 'gemini-embedding-2', 'multimodal_embedding', TRUE, NULL, NULL, NULL, TRUE, FALSE, NULL, '2026-06-17', '2026-06-17', 'active'),
  ('google', 'dm_generation', 'gemini-3-flash', 'dm_generation', TRUE, 'gemini-3.5-flash', NULL, NULL, TRUE, TRUE, NULL, '2026-06-17', '2026-06-17', 'active'),
  ('google', 'response_summary', 'gemini-3.1-flash-lite', 'response_summary', TRUE, 'gemini-3-flash', NULL, NULL, TRUE, TRUE, NULL, '2026-06-17', '2026-06-17', 'active')
ON CONFLICT (model_alias, task_type) DO UPDATE SET
  provider = EXCLUDED.provider,
  model_id = EXCLUDED.model_id,
  default_for_task = EXCLUDED.default_for_task,
  fallback_model_id = EXCLUDED.fallback_model_id,
  input_price_per_mtok = EXCLUDED.input_price_per_mtok,
  output_price_per_mtok = EXCLUDED.output_price_per_mtok,
  batch_supported = EXCLUDED.batch_supported,
  flex_supported = EXCLUDED.flex_supported,
  context_window = EXCLUDED.context_window,
  last_price_verified_at = EXCLUDED.last_price_verified_at,
  last_capability_verified_at = EXCLUDED.last_capability_verified_at,
  status = EXCLUDED.status,
  updated_at = now();

-- Keyword seeds are maintained as CSV:
-- outputs/briwell_keyword_seed_v0.csv
-- Import mapping:
-- country, language, product_category, intent_type, keyword, hashtag, priority, notes

-- QA notes:
-- Pass 1: Scoring weights sum to 1.0 excluding risk_penalty.
-- Pass 2: Model registry uses aliases rather than hardcoding models in application code.
-- Pass 3: Prices are intentionally nullable and must be re-verified before deployment.
