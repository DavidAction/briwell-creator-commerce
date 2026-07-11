-- 009: creator portal tokens (roadmap 3 — creator self-serve portal).
-- Unguessable, revocable, read-only personal links: GET /portal/me?token=...
-- shows a creator ONLY their own codes, commission ledger and balances.
-- No login flow by design for the pilot cohort; rotating the token is the
-- kill switch.

CREATE TABLE IF NOT EXISTS creator_portal_token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_id UUID NOT NULL REFERENCES creator(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_creator_portal_token_creator
    ON creator_portal_token (creator_id);

-- Fast active-token lookup; the UNIQUE(token) index already covers the
-- token column itself.
CREATE INDEX IF NOT EXISTS idx_creator_portal_token_active
    ON creator_portal_token (status)
    WHERE status = 'active';
