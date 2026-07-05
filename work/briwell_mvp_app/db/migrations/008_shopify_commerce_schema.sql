-- Briwell Shopify commerce integrity schema.
-- Created: 2026-07-06
-- Resolves audit findings #5 (refund-safe append-only commission ledger),
-- #6 (currency-explicit money), #7 (dual discount-code + UTM attribution),
-- #8 (Shopify order mirror entity).
--
-- Conventions: UUID PKs (001), TIMESTAMPTZ, TEXT + CHECK for statuses (006+),
-- set_updated_at() trigger reuse (001), idempotent-safe IF NOT EXISTS (006).
--
-- Money policy: amounts are NUMERIC(14,2) in the order's presentment currency
-- (MXN / PEN / USD -- all ISO 4217 two-decimal currencies). fx_rate_usd is the
-- USD value of ONE unit of that currency, captured at ingestion time and never
-- updated afterwards. USD figures are STORED GENERATED columns -- derived only,
-- never hand-entered.

-- ---------------------------------------------------------------------------
-- 1. Shopify order mirror (#8, #6)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS shop_order (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shopify_order_id TEXT NOT NULL UNIQUE,          -- Shopify numeric id as text
  order_number TEXT,                              -- human-facing "#1001"
  shop_domain TEXT,                               -- e.g. briwell-mx.myshopify.com
  country country_code,                           -- MX / PE / EC (buyer market), NULL if unknown
  currency CHAR(3) NOT NULL CHECK (currency IN ('MXN', 'PEN', 'USD')),
  subtotal_amount NUMERIC(14,2) NOT NULL CHECK (subtotal_amount >= 0),   -- pre-discount merchandise
  discount_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
  shipping_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (shipping_amount >= 0),
  tax_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
  total_amount NUMERIC(14,2) NOT NULL CHECK (total_amount >= 0),
  fx_rate_usd NUMERIC(18,8) NOT NULL CHECK (fx_rate_usd > 0),
  total_usd NUMERIC(14,2) GENERATED ALWAYS AS (ROUND(total_amount * fx_rate_usd, 2)) STORED,
  CHECK (currency <> 'USD' OR fx_rate_usd = 1),
  financial_status TEXT NOT NULL DEFAULT 'pending' CHECK (financial_status IN (
    'pending', 'authorized', 'paid', 'partially_paid',
    'partially_refunded', 'refunded', 'voided', 'cancelled'
  )),
  discount_codes JSONB NOT NULL DEFAULT '[]'::jsonb,  -- raw Shopify discount_codes array
  landing_site TEXT,                                   -- raw landing URL (UTM source of truth)
  utm_params JSONB NOT NULL DEFAULT '{}'::jsonb,       -- parsed {source, medium, campaign, content, term}
  customer_ref TEXT,                                   -- hashed/pseudonymous customer key, NO raw PII
  ordered_at TIMESTAMPTZ NOT NULL,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,      -- full webhook body for replay/debug
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_shop_order_ordered_at ON shop_order (ordered_at DESC);
CREATE INDEX IF NOT EXISTS idx_shop_order_financial_status ON shop_order (financial_status);

DROP TRIGGER IF EXISTS set_updated_at_shop_order ON shop_order;
CREATE TRIGGER set_updated_at_shop_order
BEFORE UPDATE ON shop_order
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS shop_order_line_item (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES shop_order(id) ON DELETE CASCADE,
  shopify_line_item_id TEXT,
  title TEXT NOT NULL,
  sku TEXT,
  product_id UUID REFERENCES product_catalog(id),      -- optional internal mapping
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC(14,2) NOT NULL CHECK (unit_price >= 0),
  total_discount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (total_discount >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (order_id, shopify_line_item_id)
);

CREATE INDEX IF NOT EXISTS idx_line_item_order ON shop_order_line_item (order_id);

-- ---------------------------------------------------------------------------
-- 2. Refund mirror (#5, #8)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS order_refund (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES shop_order(id) ON DELETE RESTRICT,
  shopify_refund_id TEXT NOT NULL UNIQUE,
  currency CHAR(3) NOT NULL CHECK (currency IN ('MXN', 'PEN', 'USD')),
  -- commissionable portion of the refund: merchandise net of discounts,
  -- EXCLUDING shipping and tax (mirrors the accrual base).
  commissionable_refund_amount NUMERIC(14,2) NOT NULL CHECK (commissionable_refund_amount >= 0),
  total_refund_amount NUMERIC(14,2) NOT NULL CHECK (total_refund_amount >= 0),
  refund_line_items JSONB NOT NULL DEFAULT '[]'::jsonb,  -- raw Shopify refund_line_items
  reason TEXT,
  processed_at TIMESTAMPTZ NOT NULL,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_refund_order ON order_refund (order_id);

-- Refund currency must match the order currency (cross-row money integrity).
CREATE OR REPLACE FUNCTION enforce_refund_currency_matches_order()
RETURNS TRIGGER AS $$
DECLARE
  order_currency CHAR(3);
BEGIN
  SELECT currency INTO order_currency FROM shop_order WHERE id = NEW.order_id;
  IF order_currency IS NULL THEN
    RAISE EXCEPTION 'order_refund references missing shop_order %', NEW.order_id;
  END IF;
  IF NEW.currency <> order_currency THEN
    RAISE EXCEPTION 'order_refund currency % does not match order currency %',
      NEW.currency, order_currency;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_refund_currency_matches_order ON order_refund;
CREATE TRIGGER enforce_refund_currency_matches_order
BEFORE INSERT OR UPDATE ON order_refund
FOR EACH ROW EXECUTE FUNCTION enforce_refund_currency_matches_order();

-- ---------------------------------------------------------------------------
-- 3. Creator discount codes + UTM links (#7 attribution inputs)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS creator_discount_code (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id UUID NOT NULL REFERENCES creator(id) ON DELETE RESTRICT,
  campaign_id UUID REFERENCES campaign(id) ON DELETE SET NULL,
  code TEXT NOT NULL UNIQUE CHECK (code = upper(code) AND length(code) BETWEEN 3 AND 64),
  commission_rate NUMERIC(5,4) NOT NULL CHECK (commission_rate >= 0 AND commission_rate <= 0.5),
  shopify_price_rule_id TEXT,       -- NULL until real Shopify API integration (deferred)
  shopify_discount_code_id TEXT,    -- NULL until real Shopify API integration (deferred)
  valid_from TIMESTAMPTZ,
  valid_until TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'expired', 'revoked')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from)
);

CREATE INDEX IF NOT EXISTS idx_discount_code_creator ON creator_discount_code (creator_id, status);

DROP TRIGGER IF EXISTS set_updated_at_creator_discount_code ON creator_discount_code;
CREATE TRIGGER set_updated_at_creator_discount_code
BEFORE UPDATE ON creator_discount_code
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS creator_utm_link (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id UUID NOT NULL REFERENCES creator(id) ON DELETE RESTRICT,
  campaign_id UUID REFERENCES campaign(id) ON DELETE SET NULL,
  -- ref_token is what we match against utm_content on incoming orders.
  -- Convention: utm_source=tiktok, utm_medium=creator_bio,
  -- utm_campaign=<campaign slug>, utm_content=<ref_token>.
  ref_token TEXT NOT NULL UNIQUE CHECK (ref_token = lower(ref_token) AND length(ref_token) BETWEEN 4 AND 64),
  destination_url TEXT NOT NULL,
  utm_source TEXT NOT NULL DEFAULT 'tiktok',
  utm_medium TEXT NOT NULL DEFAULT 'creator_bio',
  utm_campaign TEXT,
  commission_rate NUMERIC(5,4) NOT NULL CHECK (commission_rate >= 0 AND commission_rate <= 0.5),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'revoked')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_utm_link_creator ON creator_utm_link (creator_id, status);

DROP TRIGGER IF EXISTS set_updated_at_creator_utm_link ON creator_utm_link;
CREATE TRIGGER set_updated_at_creator_utm_link
BEFORE UPDATE ON creator_utm_link
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- 4. Order attribution (#7) -- one ACTIVE attribution per order
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS order_attribution (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID NOT NULL REFERENCES shop_order(id) ON DELETE RESTRICT,
  creator_id UUID NOT NULL REFERENCES creator(id) ON DELETE RESTRICT,
  method TEXT NOT NULL CHECK (method IN ('discount_code', 'utm_link', 'manual')),
  confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'needs_review', 'superseded', 'rejected')),
  conflict_kind TEXT CHECK (conflict_kind IN ('code_vs_utm', 'multi_code', 'manual_override')),
  matched_discount_code_id UUID REFERENCES creator_discount_code(id),
  matched_utm_link_id UUID REFERENCES creator_utm_link(id),
  -- what the losing signal pointed at, for operator review UI
  competing_creator_id UUID REFERENCES creator(id),
  decision_notes TEXT,
  decided_by TEXT NOT NULL DEFAULT 'rules_v1',   -- 'rules_v1' | operator email
  resolved_by_email TEXT,                        -- set when operator resolves/overrides
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (method <> 'discount_code' OR matched_discount_code_id IS NOT NULL),
  CHECK (method <> 'utm_link' OR matched_utm_link_id IS NOT NULL),
  CHECK (method <> 'manual' OR resolved_by_email IS NOT NULL)
);

-- exactly one live (active or pending-review) attribution per order
CREATE UNIQUE INDEX IF NOT EXISTS idx_order_attribution_one_live
ON order_attribution (order_id)
WHERE status IN ('active', 'needs_review');

CREATE INDEX IF NOT EXISTS idx_order_attribution_creator ON order_attribution (creator_id, status);
CREATE INDEX IF NOT EXISTS idx_order_attribution_review ON order_attribution (status) WHERE status = 'needs_review';

DROP TRIGGER IF EXISTS set_updated_at_order_attribution ON order_attribution;
CREATE TRIGGER set_updated_at_order_attribution
BEFORE UPDATE ON order_attribution
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- 5. Append-only commission ledger (#5, #6)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS commission_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id UUID NOT NULL REFERENCES creator(id) ON DELETE RESTRICT,
  campaign_id UUID REFERENCES campaign(id) ON DELETE SET NULL,
  order_id UUID NOT NULL REFERENCES shop_order(id) ON DELETE RESTRICT,
  attribution_id UUID NOT NULL REFERENCES order_attribution(id) ON DELETE RESTRICT,
  refund_id UUID REFERENCES order_refund(id) ON DELETE RESTRICT,
  entry_type TEXT NOT NULL CHECK (entry_type IN ('accrual', 'reversal', 'adjustment')),
  -- Sign convention: accrual > 0, reversal < 0, adjustment != 0.
  amount NUMERIC(14,2) NOT NULL,
  currency CHAR(3) NOT NULL CHECK (currency IN ('MXN', 'PEN', 'USD')),
  -- FX frozen at the ORIGINAL accrual moment; reversals reuse the accrual's
  -- fx_rate_usd so a full refund nets USD to exactly zero.
  fx_rate_usd NUMERIC(18,8) NOT NULL CHECK (fx_rate_usd > 0),
  amount_usd NUMERIC(14,2) GENERATED ALWAYS AS (ROUND(amount * fx_rate_usd, 2)) STORED,
  CHECK (currency <> 'USD' OR fx_rate_usd = 1),
  reverses_entry_id UUID REFERENCES commission_ledger(id),
  commission_rate NUMERIC(5,4),      -- rate used for accrual rows (traceability)
  memo TEXT,
  created_by_email TEXT,             -- required for adjustments (app-enforced too)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (
    (entry_type = 'accrual'    AND amount > 0 AND reverses_entry_id IS NULL AND commission_rate IS NOT NULL)
    OR (entry_type = 'reversal'   AND amount < 0 AND reverses_entry_id IS NOT NULL AND refund_id IS NOT NULL)
    OR (entry_type = 'adjustment' AND amount <> 0 AND memo IS NOT NULL AND created_by_email IS NOT NULL)
  )
);

-- one accrual per attribution (re-attribution => new attribution row => new accrual)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_one_accrual_per_attribution
ON commission_ledger (attribution_id)
WHERE entry_type = 'accrual';

-- a given refund reverses a given accrual at most once (webhook idempotency)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_one_reversal_per_refund
ON commission_ledger (refund_id, reverses_entry_id)
WHERE entry_type = 'reversal';

CREATE INDEX IF NOT EXISTS idx_ledger_creator ON commission_ledger (creator_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_order ON commission_ledger (order_id);
CREATE INDEX IF NOT EXISTS idx_ledger_campaign ON commission_ledger (campaign_id);

-- Immutability: ledger rows can never be updated or deleted. Chosen over
-- convention-only (audit_events style) because this ledger drives real
-- creator payouts; DB-level enforcement removes an entire class of bugs.
CREATE OR REPLACE FUNCTION commission_ledger_immutable()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'commission_ledger is append-only: % not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS commission_ledger_no_update ON commission_ledger;
CREATE TRIGGER commission_ledger_no_update
BEFORE UPDATE ON commission_ledger
FOR EACH ROW EXECUTE FUNCTION commission_ledger_immutable();

DROP TRIGGER IF EXISTS commission_ledger_no_delete ON commission_ledger;
CREATE TRIGGER commission_ledger_no_delete
BEFORE DELETE ON commission_ledger
FOR EACH ROW EXECUTE FUNCTION commission_ledger_immutable();

-- Reversal integrity: must reference an accrual on the same order/creator,
-- same currency, same fx rate; cumulative reversals may not exceed the accrual.
CREATE OR REPLACE FUNCTION enforce_reversal_integrity()
RETURNS TRIGGER AS $$
DECLARE
  src commission_ledger%ROWTYPE;
  already_reversed NUMERIC(14,2);
BEGIN
  IF NEW.entry_type <> 'reversal' THEN
    RETURN NEW;
  END IF;
  SELECT * INTO src FROM commission_ledger WHERE id = NEW.reverses_entry_id;
  IF src.id IS NULL OR src.entry_type <> 'accrual' THEN
    RAISE EXCEPTION 'reversal must reference an existing accrual entry';
  END IF;
  IF src.order_id <> NEW.order_id OR src.creator_id <> NEW.creator_id THEN
    RAISE EXCEPTION 'reversal order/creator must match the referenced accrual';
  END IF;
  IF src.currency <> NEW.currency OR src.fx_rate_usd <> NEW.fx_rate_usd THEN
    RAISE EXCEPTION 'reversal must reuse the accrual currency and fx_rate_usd';
  END IF;
  SELECT COALESCE(SUM(amount), 0) INTO already_reversed
  FROM commission_ledger
  WHERE reverses_entry_id = NEW.reverses_entry_id AND entry_type = 'reversal';
  IF src.amount + already_reversed + NEW.amount < 0 THEN
    RAISE EXCEPTION 'cumulative reversals would exceed the original accrual';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS enforce_reversal_integrity ON commission_ledger;
CREATE TRIGGER enforce_reversal_integrity
BEFORE INSERT ON commission_ledger
FOR EACH ROW EXECUTE FUNCTION enforce_reversal_integrity();

-- Derived balances (no mutable balance column anywhere -- finding #5).
CREATE OR REPLACE VIEW creator_commission_balance AS
SELECT
  creator_id,
  currency,
  SUM(amount) AS balance_amount,
  SUM(amount_usd) AS balance_usd,
  COUNT(*) FILTER (WHERE entry_type = 'accrual') AS accrual_count,
  COUNT(*) FILTER (WHERE entry_type = 'reversal') AS reversal_count,
  COUNT(*) FILTER (WHERE entry_type = 'adjustment') AS adjustment_count,
  MAX(created_at) AS last_entry_at
FROM commission_ledger
GROUP BY creator_id, currency;

-- ---------------------------------------------------------------------------
-- 6. Backward-compatible currency retrofit for campaign_performance_snapshot (#6)
-- ---------------------------------------------------------------------------

ALTER TABLE campaign_performance_snapshot
  ADD COLUMN IF NOT EXISTS revenue_amount NUMERIC(14,2) CHECK (revenue_amount IS NULL OR revenue_amount >= 0),
  ADD COLUMN IF NOT EXISTS revenue_currency CHAR(3) CHECK (revenue_currency IS NULL OR revenue_currency IN ('MXN', 'PEN', 'USD')),
  ADD COLUMN IF NOT EXISTS fx_rate_usd NUMERIC(18,8) CHECK (fx_rate_usd IS NULL OR fx_rate_usd > 0);

-- The triple travels together or not at all. Guarded with a catalog check so
-- this migration can be re-run safely (ADD CONSTRAINT has no IF NOT EXISTS).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_snapshot_currency_triple'
  ) THEN
    ALTER TABLE campaign_performance_snapshot
      ADD CONSTRAINT chk_snapshot_currency_triple CHECK (
        (revenue_amount IS NULL AND revenue_currency IS NULL AND fx_rate_usd IS NULL)
        OR (revenue_amount IS NOT NULL AND revenue_currency IS NOT NULL AND fx_rate_usd IS NOT NULL)
      );
  END IF;
END;
$$;

-- Backfill: historical revenue_usd rows were entered as USD; make that explicit.
UPDATE campaign_performance_snapshot
SET revenue_amount = revenue_usd,
    revenue_currency = 'USD',
    fx_rate_usd = 1
WHERE revenue_usd IS NOT NULL AND revenue_amount IS NULL;
