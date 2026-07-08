from __future__ import annotations

"""Executable checklist for the Shopify go-live runbook (docs/SHOPIFY_GOLIVE.md).

Run after filling `.env` (runbook step 2) and before registering webhooks
(step 3). Makes NO network calls - it only validates local configuration, so
it is safe to run anytime, with or without a Shopify account.

    python -m scripts.shopify_golive_preflight
    python -m scripts.shopify_golive_preflight --json

Exit code 0 = nothing missing (warnings allowed), 1 = at least one MISSING item.
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

from app.commerce.shopify_webhook import parse_fx_rates
from app.core.config import settings

# Currencies the LATAM pilot sells in; webhook orders in a currency missing
# from SHOPIFY_FX_RATES are rejected 422 (fail-closed), so flag gaps early.
PILOT_CURRENCIES = ("MXN", "PEN")

STATUS_READY = "ready"
STATUS_MISSING = "missing"
STATUS_WARN = "warn"
STATUS_INFO = "info"


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    runbook_step: str


def evaluate_preflight(cfg: Any = None) -> list[Check]:
    cfg = cfg or settings
    checks: list[Check] = []

    domain = cfg.shopify_shop_domain
    if not domain:
        checks.append(Check("shop domain", STATUS_MISSING, "SHOPIFY_SHOP_DOMAIN is not set.", "2"))
    elif not domain.endswith(".myshopify.com"):
        checks.append(
            Check(
                "shop domain",
                STATUS_WARN,
                f"{domain!r} is not a *.myshopify.com domain; the Admin API needs the "
                "myshopify domain, not a storefront custom domain.",
                "2",
            )
        )
    else:
        checks.append(Check("shop domain", STATUS_READY, domain, "2"))

    token = cfg.shopify_admin_api_token
    if not token:
        checks.append(
            Check("admin API token", STATUS_MISSING, "SHOPIFY_ADMIN_API_TOKEN is not set.", "2")
        )
    elif not token.startswith("shpat_"):
        checks.append(
            Check(
                "admin API token",
                STATUS_WARN,
                "Token does not start with 'shpat_' - expected a custom-app Admin API "
                "access token (runbook step 1.4).",
                "2",
            )
        )
    else:
        checks.append(Check("admin API token", STATUS_READY, "set (shpat_...)", "2"))

    if not cfg.shopify_webhook_secret:
        checks.append(
            Check(
                "webhook HMAC secret",
                STATUS_MISSING,
                "SHOPIFY_WEBHOOK_SECRET is not set - the receiver rejects every delivery "
                "with 503 until it is (use the app's API secret key, runbook step 1.5).",
                "2",
            )
        )
    else:
        checks.append(Check("webhook HMAC secret", STATUS_READY, "set", "2"))

    if not cfg.shopify_api_version:
        checks.append(
            Check("API version", STATUS_MISSING, "SHOPIFY_API_VERSION is not set.", "2")
        )
    else:
        checks.append(Check("API version", STATUS_READY, cfg.shopify_api_version, "2"))

    checks.append(_fx_check(cfg.shopify_fx_rates_raw))

    if not cfg.use_database:
        checks.append(
            Check(
                "database",
                STATUS_MISSING,
                "USE_DATABASE is false - live webhook ingest and discount issuance both "
                "require the database so orders/ledger persist and every Shopify code "
                "is mirrored locally.",
                "2",
            )
        )
    else:
        checks.append(Check("database", STATUS_READY, "USE_DATABASE=true", "2"))

    gates_open = not cfg.shopify_dry_run and cfg.allow_live_shopify_calls
    checks.append(
        Check(
            "live gates",
            STATUS_INFO,
            "OPEN - live Shopify calls are enabled."
            if gates_open
            else "closed (dry-run) - open them only at runbook steps 3/5.",
            "3/5",
        )
    )
    return checks


def _fx_check(raw: str) -> Check:
    if not raw.strip():
        return Check(
            "FX rates",
            STATUS_MISSING,
            "SHOPIFY_FX_RATES is not set - webhook orders in any non-USD currency "
            "would be rejected 422 (fail-closed).",
            "2",
        )
    try:
        rates = parse_fx_rates(raw)
    except ValueError as exc:
        return Check("FX rates", STATUS_MISSING, str(exc), "2")
    uncovered = [currency for currency in PILOT_CURRENCIES if currency not in rates]
    if uncovered:
        return Check(
            "FX rates",
            STATUS_WARN,
            f"parsed OK but pilot currencies missing: {', '.join(uncovered)} - orders "
            "in those currencies will be rejected 422.",
            "2",
        )
    listed = ", ".join(f"{currency}:{rate}" for currency, rate in sorted(rates.items()))
    return Check("FX rates", STATUS_READY, listed, "2")


STATUS_LABELS = {
    STATUS_READY: "READY  ",
    STATUS_MISSING: "MISSING",
    STATUS_WARN: "WARN   ",
    STATUS_INFO: "INFO   ",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shopify go-live configuration preflight.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    checks = evaluate_preflight()
    missing = [check for check in checks if check.status == STATUS_MISSING]

    if args.json:
        print(
            json.dumps(
                {"checks": [asdict(check) for check in checks], "missing_count": len(missing)},
                indent=2,
            )
        )
        return 1 if missing else 0

    print("Shopify go-live preflight (docs/SHOPIFY_GOLIVE.md) - no network calls\n")
    for check in checks:
        print(f"  [{STATUS_LABELS[check.status]}] {check.name:20} {check.detail}  (step {check.runbook_step})")
    print()
    if missing:
        print(f"{len(missing)} item(s) missing - finish runbook step 2 before registering webhooks.")
        return 1
    print("All required items present. Next: runbook step 3 (register webhooks).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
