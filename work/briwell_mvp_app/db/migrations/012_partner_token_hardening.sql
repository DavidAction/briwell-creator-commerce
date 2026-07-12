-- 012: Partner token hardening (critical review v0, P1 — David-approved
-- work order 2026-07-12). Two changes:
--
-- 1. SHA-256 at rest: the API stores only the digest of a hub token; the
--    plaintext is shown once at issue time and never persisted. A database
--    leak therefore does not leak usable links.
-- 2. Expiry: every token now carries expires_at (default 90 days, set by
--    the application at issue time). Lookup treats a NULL or past
--    expires_at as invalid — fail closed.
--
-- Plaintext-era tokens cannot be hashed retroactively (the digest is
-- one-way), so any still-active rows are revoked here. Reissuing a link is
-- a one-click operator action and rotation was already the documented
-- response to a stale link.

UPDATE brand_partner_token
SET status = 'revoked', revoked_at = now()
WHERE status = 'active';

ALTER TABLE brand_partner_token RENAME COLUMN token TO token_sha256;

ALTER TABLE brand_partner_token ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
