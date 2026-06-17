from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Briwell production readiness gates.")
    parser.add_argument(
        "--env-file",
        default=".env.production",
        help="Environment file to load before checking readiness.",
    )
    args = parser.parse_args()

    env_path = ROOT / args.env_file
    if env_path.exists():
        load_dotenv(env_path, override=True)
    else:
        load_dotenv()

    from app.core.config import settings
    from app.core.readiness import ReadinessSettings, evaluate_readiness

    result = evaluate_readiness(
        ReadinessSettings(
            app_env=settings.app_env,
            database_url=settings.database_url,
            use_database=settings.use_database,
            gemini_api_key=settings.gemini_api_key,
            ai_dry_run=settings.ai_dry_run,
            allow_live_provider_calls=settings.allow_live_provider_calls,
            auth_provider=settings.auth_provider,
            oidc_issuer_url=settings.oidc_issuer_url,
            oidc_audience=settings.oidc_audience,
            oidc_jwks_url=settings.oidc_jwks_url,
            oidc_role_claim=settings.oidc_role_claim,
            cors_allowed_origins=settings.cors_allowed_origins,
            managed_secret_provider=settings.managed_secret_provider,
            backup_restore_tested_at=settings.backup_restore_tested_at,
            rate_limit_enabled=settings.rate_limit_enabled,
        )
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
