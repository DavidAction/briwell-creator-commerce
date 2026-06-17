from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.workers.recent_posts_screening import RecentPostSnapshot
from app.workers.recent_posts_screening import RecentPostsScreenRequest
from app.workers.recent_posts_screening import run_recent_posts_screen


def build_posts() -> list[RecentPostSnapshot]:
    return [
        RecentPostSnapshot(
            video_id=f"live-smoke-{index}",
            url=f"https://www.tiktok.com/@briwell_live_smoke/video/{7000000000000000000 + index}",
            caption="Rutina skincare con protector solar coreano SPF, textura ligera y link de compra.",
            transcript="Protector solar coreano para rutina diaria. Review honesta de textura, acabado y uso.",
            hashtags=["skincare", "kbeauty", "protectorsolar"],
            view_count=12000 + index,
            like_count=800 + index,
            comment_count=50 + index,
            share_count=12,
            save_count=40,
            duration_seconds=38,
        )
        for index in range(1, 21)
    ]


def env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def preflight_errors(confirm_live_cost: bool, persist_result: bool) -> list[str]:
    errors: list[str] = []
    if not confirm_live_cost:
        errors.append("pass --confirm-live-cost to allow one paid Gemini smoke call")
    if not os.getenv("GEMINI_API_KEY"):
        errors.append("GEMINI_API_KEY is required")
    if not env_enabled("ALLOW_LIVE_PROVIDER_CALLS"):
        errors.append("ALLOW_LIVE_PROVIDER_CALLS=true is required")
    if env_enabled("AI_DRY_RUN"):
        errors.append("AI_DRY_RUN=false is required")
    if persist_result and not env_enabled("USE_DATABASE"):
        errors.append("USE_DATABASE=true is required when --persist-result is used")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one guarded live Gemini recent-20 smoke test.")
    parser.add_argument("--confirm-live-cost", action="store_true", help="Required. Allows one paid provider call.")
    parser.add_argument("--creator-id", default="live-smoke-local", help="Creator id. Use a DB UUID with --persist-result.")
    parser.add_argument("--persist-result", action="store_true", help="Persist screen result; requires USE_DATABASE=true and UUID creator_id.")
    args = parser.parse_args(argv)

    errors = preflight_errors(args.confirm_live_cost, args.persist_result)
    if errors:
        print(json.dumps({"status": "blocked", "errors": errors}, indent=2), file=sys.stderr)
        return 2

    result = run_recent_posts_screen(
        RecentPostsScreenRequest(
            creator_id=args.creator_id,
            source_risk_level="low",
            recent_posts=build_posts(),
            expected_post_count=20,
            creator_snapshot={
                "creator_id": args.creator_id,
                "username": "briwell_live_smoke",
                "country": "MX",
                "platform": "tiktok",
                "source_risk_level": "low",
            },
            product_context={"product_category": "sunscreen", "brand": "Briwell", "markets": ["MX", "PE", "EC"]},
            dry_run=False,
            allow_live_provider_calls=True,
            persist_result=args.persist_result,
        )
    )
    body = result.model_dump()
    print(json.dumps(body, ensure_ascii=True, indent=2, default=str))
    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
