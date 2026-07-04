-- Align comment_sample.sample_method and campaign_performance_snapshot.source_type
-- CHECK constraints with app.core.policy.ALLOWED_COLLECTION_SOURCE_TYPES.
--
-- Audit finding: both constraints were created (migrations 001/002) allowing only
-- 'manual', 'official_api', 'approved_provider', 'creator_provided' -- excluding
-- 'provider_scrape', which the policy allowlist already treats as an allowed
-- (but honestly-labeled, elevated-review) source type for the existing managed
-- third-party scraping lane (e.g. Apify). This migration brings both constraints
-- in line so provider_scrape-sourced comment samples and performance snapshots
-- are not silently rejected by the database while the application layer allows
-- them. This does NOT loosen policy: provider_scrape stays default-OFF at the
-- provider layer and still goes through app.core.policy gating end-to-end.
--
-- Idempotent-safe: uses a DO block to look up whichever auto-generated (or
-- previously-applied) constraint name is currently attached to each column and
-- drops it before (re)adding the explicitly-named constraint below, so this
-- migration can be re-run safely and does not depend on guessing Postgres's
-- default constraint-naming convention.

DO $$
DECLARE
  constraint_name TEXT;
BEGIN
  SELECT con.conname INTO constraint_name
  FROM pg_constraint con
  JOIN pg_class rel ON rel.oid = con.conrelid
  JOIN pg_attribute att ON att.attrelid = rel.oid
  WHERE rel.relname = 'comment_sample'
    AND con.contype = 'c'
    AND att.attname = 'sample_method'
    AND att.attnum = ANY (con.conkey)
  LIMIT 1;

  IF constraint_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE comment_sample DROP CONSTRAINT %I', constraint_name);
  END IF;
END $$;

ALTER TABLE comment_sample
  ADD CONSTRAINT comment_sample_sample_method_check
  CHECK (sample_method IN ('manual', 'official_api', 'approved_provider', 'creator_provided', 'provider_scrape'));

DO $$
DECLARE
  constraint_name TEXT;
BEGIN
  SELECT con.conname INTO constraint_name
  FROM pg_constraint con
  JOIN pg_class rel ON rel.oid = con.conrelid
  JOIN pg_attribute att ON att.attrelid = rel.oid
  WHERE rel.relname = 'campaign_performance_snapshot'
    AND con.contype = 'c'
    AND att.attname = 'source_type'
    AND att.attnum = ANY (con.conkey)
  LIMIT 1;

  IF constraint_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE campaign_performance_snapshot DROP CONSTRAINT %I', constraint_name);
  END IF;
END $$;

ALTER TABLE campaign_performance_snapshot
  ADD CONSTRAINT campaign_performance_snapshot_source_type_check
  CHECK (source_type IN ('manual', 'official_api', 'approved_provider', 'creator_provided', 'provider_scrape'));
