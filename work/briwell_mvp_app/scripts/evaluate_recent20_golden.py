from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.workers.recent_posts_screening import RecentPostSnapshot
from app.workers.recent_posts_screening import RecentPostsScreenRequest
from app.workers.recent_posts_screening import run_recent_posts_screen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "golden" / "recent20_screen_v0.json"


def load_cases(path: Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def posts_for_case(case: dict[str, Any]) -> list[RecentPostSnapshot]:
    template = dict(case["post_template"])
    return [
        RecentPostSnapshot(
            video_id=f"{case['case_id']}-{index}",
            url=f"https://www.tiktok.com/@{case['creator']['username']}/video/{7000000000000000000 + index}",
            caption=template.get("caption"),
            transcript=template.get("transcript"),
            hashtags=template.get("hashtags", []),
            view_count=int(template.get("view_count") or 0) + index,
            like_count=template.get("like_count"),
            comment_count=template.get("comment_count"),
            share_count=template.get("share_count"),
        )
        for index in range(1, int(case["post_count"]) + 1)
    ]


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    result = run_recent_posts_screen(
        RecentPostsScreenRequest(
            creator_id=case["creator"]["creator_id"],
            source_risk_level="low",
            recent_posts=posts_for_case(case),
            expected_post_count=20,
            creator_snapshot=case["creator"],
            product_context=case.get("product_context", {}),
            dry_run=True,
            persist_result=False,
        )
    )
    output = result.result.output
    failures = []
    if output.get("suitability_decision") != case["expected_decision"]:
        failures.append(f"decision expected {case['expected_decision']} got {output.get('suitability_decision')}")
    if "min_score" in case and float(output.get("suitability_score") or 0) < float(case["min_score"]):
        failures.append(f"score below min {case['min_score']}")
    if "max_score" in case and float(output.get("suitability_score") or 0) > float(case["max_score"]):
        failures.append(f"score above max {case['max_score']}")
    if case.get("required_gap") and case["required_gap"] not in output.get("coverage_gaps", []):
        failures.append(f"missing gap {case['required_gap']}")
    if case.get("required_risk_note") and case["required_risk_note"] not in output.get("risk_notes", []):
        failures.append(f"missing risk note {case['required_risk_note']}")
    return {
        "case_id": case["case_id"],
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "decision": output.get("suitability_decision"),
        "score": output.get("suitability_score"),
        "coverage_gaps": output.get("coverage_gaps", []),
        "risk_notes": output.get("risk_notes", []),
    }


def evaluate_all(path: Path = DEFAULT_DATASET) -> dict[str, Any]:
    items = [evaluate_case(case) for case in load_cases(path)]
    return {
        "status": "passed" if all(item["status"] == "passed" for item in items) else "failed",
        "case_count": len(items),
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate recent-20 screening against the Briwell golden dataset.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args(argv)
    result = evaluate_all(args.dataset)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
