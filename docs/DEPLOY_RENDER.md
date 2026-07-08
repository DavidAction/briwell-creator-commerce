# Render Deploy Runbook (API + Managed Postgres + OIDC)

Takes the backend from local-only to a public HTTPS deployment with managed
PostgreSQL and Supabase OIDC auth. This unblocks production blockers 1-3
(managed DB, secret manager, OIDC) and is a prerequisite for Shopify go-live
(`docs/SHOPIFY_GOLIVE.md` needs a public webhook origin).

You need: a Render account connected to the GitHub repo, a Supabase project
(free tier is fine — used only for auth here), and a Gemini API key.

The blueprint is `render.yaml` at the repository root (Render only detects
blueprints there; it points at `work/briwell_mvp_app` via `rootDir`). It
defines the API web service and a managed Postgres (`briwell-postgres`,
basic-256mb — Render's free Postgres expires after 30 days).

## 1. Supabase project for OIDC

1. Create a project at supabase.com. Note the project ref (`<ref>`).
2. **Enable asymmetric JWT signing keys** (Project Settings → JWT Keys →
   migrate to signing keys). Legacy HS256 tokens cannot be verified via JWKS;
   the backend validates ES256/RS256 only.
3. Create an operator user (Authentication → Users → Add user, email+password).
4. Grant the Briwell role via SQL editor (the backend reads
   `app_metadata.briwell_role`):

   ```sql
   update auth.users
   set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb)
       || '{"briwell_role": "admin"}'
   where email = 'operator@yourdomain.com';
   ```

5. Values you will need in step 2:
   - `OIDC_ISSUER_URL` = `https://<ref>.supabase.co/auth/v1`
   - `OIDC_JWKS_URL` = `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`

## 2. Backup/restore evidence (readiness gate)

The deploy gate refuses to boot without `BACKUP_RESTORE_TESTED_AT` (fail-closed
by design). Run the drill locally against the portable Postgres first:

```powershell
cd work\briwell_mvp_app
$env:PG_BIN_DIR="..\postgresql-17.10-portable\pgsql\bin"
python scripts/backup_db.py --output-dir ..\db_backups
python scripts/restore_db.py --backup-file <backup.dump> --target-db briwell_restore_smoke --drop-existing
```

Record the ISO timestamp of the successful restore — that is the value for
`BACKUP_RESTORE_TESTED_AT`. Re-run the drill against the managed DB after
first deploy and update the timestamp.

## 3. Render blueprint deploy

1. Render dashboard → **New → Blueprint** → select the GitHub repo. Render
   picks up the root `render.yaml` (API service + Postgres).
2. Fill every `sync: false` env var when prompted:

   | Key | Value / source |
   | --- | --- |
   | `OIDC_ISSUER_URL` | step 1.5 |
   | `OIDC_JWKS_URL` | step 1.5 |
   | `CORS_ALLOWED_ORIGINS` | dashboard origin(s), e.g. `https://briwell-dashboard.vercel.app` — no localhost |
   | `GEMINI_API_KEY` | Google AI Studio |
   | `BACKUP_RESTORE_TESTED_AT` | step 2 timestamp |
   | `APIFY_API_TOKEN`, `DATA365_API_KEY`, `BRIGHTDATA_API_KEY`, `TIKAPI_API_KEY` | leave empty (unused lanes) |
   | `SHOPIFY_*` (`SHOP_DOMAIN`, `ADMIN_API_TOKEN`, `WEBHOOK_SECRET`, `FX_RATES`) | leave empty until the Shopify store exists — receivers fail closed (503), which is safe |

3. Deploy. `preDeployCommand` runs the readiness gate then
   `bootstrap_db.py --with-seeds --with-keywords --verify` against the managed
   DB. If the gate exits 1, a listed blocker (e.g. `OIDC_CONFIGURATION_MISSING`)
   tells you which variable is wrong — fix and redeploy; nothing half-configured
   ever boots.

## 4. Verify

```powershell
# Health (no auth):
curl https://briwell-api.onrender.com/health

# Get an operator access token from Supabase:
curl -X POST "https://<ref>.supabase.co/auth/v1/token?grant_type=password" `
  -H "apikey: <anon-key>" -H "Content-Type: application/json" `
  -d '{"email":"operator@yourdomain.com","password":"..."}'

# Authenticated call with the returned access_token:
curl https://briwell-api.onrender.com/ops/readiness -H "Authorization: Bearer <access_token>"
```

Expect readiness `status` of `ok` or `ready_with_warnings` (Shopify vars empty
is fine pre-store). A `401` means the JWT/JWKS wiring is off — recheck step 1.2.

## 5. Connect the dashboard

1. Deploy `work/briwell_dashboard_app` as a static site (`vercel.json` is
   included) or keep serving it locally.
2. Make sure its origin is listed in `CORS_ALLOWED_ORIGINS`.
3. In the dashboard 연결 설정 drawer: set API 주소 to the Render URL and paste
   the Supabase access token into the Bearer 토큰 field. The client sends it as
   `Authorization: Bearer …`; header RBAC is rejected in production, so calls
   without a token will 401. Tokens expire (~1h default) — re-issue with the
   curl above, or raise the JWT expiry in Supabase for the pilot.

## 6. Shopify (later, when the store exists)

Follow `docs/SHOPIFY_GOLIVE.md` with
`--public-base https://briwell-api.onrender.com`. Fill the `SHOPIFY_*` vars in
Render (step 3.2 table) instead of a local `.env`, and run the preflight
locally with the same values first.

## Rollback / teardown

- Render keeps previous deploys: **Manual Deploy → Rollback** on the service.
- Suspending the service stops billing for compute; the Postgres keeps data
  (and billing) until deleted — back up first (`scripts/backup_db.py` works
  against the managed `DATABASE_URL`).
