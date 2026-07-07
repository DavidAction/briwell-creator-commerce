# Shopify Go-Live Runbook

The Shopify integration code is complete and gated. This runbook is the manual,
operator-side sequence to take it live. Nothing here needs a code change — it is
account setup, secrets, and verification.

You need: a Shopify store (paid plan with Admin API access), the API deployed at
a public HTTPS origin (Shopify cannot reach `127.0.0.1`), and `USE_DATABASE=true`
with a managed Postgres so orders/ledger persist.

## 1. Create a Shopify custom app

1. Shopify admin → **Settings → Apps and sales channels → Develop apps → Create an app**.
2. Name it `Briwell Attribution`.
3. **Configuration → Admin API scopes**, grant:
   - `read_orders`, `write_orders` (order data)
   - `write_price_rules`, `write_discounts` (creator discount-code issuance)
4. **Install app**, then copy the **Admin API access token** (`shpat_…`). It is shown once.
5. **API credentials** → copy the **API secret key** — this is your webhook HMAC secret.

## 2. Set backend secrets

In `work/briwell_mvp_app/.env` (never commit this file — it is gitignored):

```
USE_DATABASE=true
DATABASE_URL=postgresql://…            # managed Postgres

SHOPIFY_SHOP_DOMAIN=your-store.myshopify.com
SHOPIFY_ADMIN_API_TOKEN=shpat_xxxxxxxxxxxxxxxx
SHOPIFY_API_VERSION=2026-01            # match your app's version
SHOPIFY_WEBHOOK_SECRET=your_api_secret_key
SHOPIFY_FX_RATES=MXN:0.058,PEN:0.27   # recorded-at-ingest USD rates; USD is always 1

# Keep discount issuance in dry-run until step 5:
SHOPIFY_DRY_RUN=true
ALLOW_LIVE_SHOPIFY_CALLS=false
```

`SHOPIFY_FX_RATES` is fail-closed: a webhook order in a currency missing here is
rejected (HTTP 422), not persisted with a guessed rate. Add every currency you sell in.

## 3. Register the webhooks

Webhooks require the secret from step 1 (the receiver returns 503 without it).
Preview first, then apply once the live gates are open.

```powershell
# Preview (safe anytime — no calls made while gates are closed):
python -m scripts.register_shopify_webhooks --public-base https://api.your-domain.com

# To apply, temporarily open the live gates in the same shell:
$env:SHOPIFY_DRY_RUN="false"; $env:ALLOW_LIVE_SHOPIFY_CALLS="true"
python -m scripts.register_shopify_webhooks --public-base https://api.your-domain.com
python -m scripts.register_shopify_webhooks --list   # confirm three topics registered
```

Registers `orders/create`, `orders/updated`, `refunds/create` → the Briwell
receiver. The script is idempotent (skips topics already pointing at the same address).

## 4. Verify end to end

1. Place a **test order** in Shopify using a creator discount code that exists in
   `creator_discount_code` (issue one in step 5, or insert manually first).
2. Confirm the order landed: `GET /commerce/orders` shows it; `GET /commerce/attributions`
   shows a decision; `GET /commerce/ledger` shows an `accrual` entry for the creator.
3. **Refund** part of the test order in Shopify. Confirm `GET /commerce/ledger` gains a
   proportional `reversal` entry and the balance in `GET /commerce/ledger/balances` drops.
4. Check backend logs for `401 WEBHOOK_HMAC_INVALID` or `422 WEBHOOK_TRANSFORM_FAILED` —
   both mean a secret/currency/config mismatch, not a code bug.

## 5. Enable live discount-code issuance

Once webhooks are verified, flip the gates permanently in `.env`:

```
SHOPIFY_DRY_RUN=false
ALLOW_LIVE_SHOPIFY_CALLS=true
```

Now `POST /commerce/discount-codes/issue` (and the dashboard 정산 → Shopify 할인코드
발급 panel) create real PriceRule + DiscountCode pairs in Shopify. Live issuance
requires `USE_DATABASE=true` so every Shopify code is mirrored locally for
attribution — there is no path to an untracked code.

## 6. Rollback / disable

- **Stop ingesting**: delete the webhooks — `python -m scripts.register_shopify_webhooks --list`
  to get ids, then delete them in Shopify admin (Notifications → Webhooks) or via the API.
- **Stop issuing codes**: set `SHOPIFY_DRY_RUN=true` (or `ALLOW_LIVE_SHOPIFY_CALLS=false`)
  and restart. The endpoint reverts to returning planned requests without touching Shopify.
- The append-only `commission_ledger` is never mutated by rollback; historical accruals stay intact.

## What is already done in code (no action needed)

- HMAC-verified receivers at `/commerce/webhooks/shopify/{orders,refunds}` reusing the
  same attribution/ledger path as manual ingestion.
- Idempotent order/refund upsert (duplicate webhook deliveries are safe).
- Currency-explicit money with recorded FX; append-only ledger with refund reversal.
- Discount issuance behind the dual live gate + database requirement.
- 352 backend tests pass covering these paths (attribution, allocation, webhook transforms).
