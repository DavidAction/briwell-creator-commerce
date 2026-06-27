"""AI evaluation harness for the recent-20 creator-fit screen.

Measures whether the AI's decisions match labeled ground truth and how well its
confidence is calibrated. This is the instrument that tells us if a prompt/model
change actually improved quality, and it catches the failure mode we observed live
(flash models returning everything as a high-score, high-confidence pass).

Run against the deterministic dry-run baseline (default) or against live Gemini
(``allow_live=True``) to compare the model to ground truth. Compare both with
``compare_modes`` to see exactly where live diverges from the heuristic baseline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.workers.recent_posts_screening import (
    RecentPostSnapshot,
    RecentPostsScreenRequest,
    run_recent_posts_screen,
)


GOLDEN_DIR = Path(__file__).resolve().parents[2] / "data" / "golden"
DEFAULT_GOLDEN_PATH = GOLDEN_DIR / "creator_eval_set_v0.json"


def load_golden_set(path: str | Path | None = None) -> list[dict[str, Any]]:
    golden_path = Path(path) if path else DEFAULT_GOLDEN_PATH
    data = json.loads(golden_path.read_text(encoding="utf-8"))
    return list(data.get("cases", []))


def _predict_case(case: dict[str, Any], dry_run: bool, allow_live: bool) -> dict[str, Any]:
    posts = [RecentPostSnapshot(**post) for post in case["recent_posts"]]
    request = RecentPostsScreenRequest(
        creator_id=case.get("id", "eval-case"),
        source_risk_level=case.get("source_risk_level", "low"),
        recent_posts=posts,
        expected_post_count=int(case.get("expected_post_count", 20)),
        creator_snapshot=case.get("creator", {}),
        product_context=case.get("product_context", {}),
        dry_run=dry_run,
        allow_live_provider_calls=allow_live,
        persist_result=False,
    )
    run = run_recent_posts_screen(request)
    output = run.result.output if run.status == "success" else {}
    return {
        "status": run.status,
        "decision": output.get("suitability_decision"),
        "score": float(output.get("suitability_score") or 0.0),
        "confidence": float(run.result.confidence or 0.0),
        "error_code": run.result.error_code,
    }


def evaluate_cases(
    cases: list[dict[str, Any]],
    dry_run: bool = True,
    allow_live: bool = False,
) -> dict[str, Any]:
    """Score predictions against labels and report accuracy + calibration metrics."""
    results: list[dict[str, Any]] = []
    for case in cases:
        label = case.get("label", {})
        prediction = _predict_case(case, dry_run=dry_run, allow_live=allow_live)
        decision_ok = prediction["decision"] == label.get("expected_decision")
        score = prediction["score"]
        band_ok = True
        if "expected_score_min" in label and score < float(label["expected_score_min"]):
            band_ok = False
        if "expected_score_max" in label and score > float(label["expected_score_max"]):
            band_ok = False
        results.append(
            {
                "id": case.get("id"),
                "expected_decision": label.get("expected_decision"),
                "predicted_decision": prediction["decision"],
                "decision_ok": decision_ok,
                "score": round(score, 2),
                "score_band_ok": band_ok,
                "confidence": round(prediction["confidence"], 3),
                "status": prediction["status"],
                "error_code": prediction["error_code"],
            }
        )
    return _metrics(results, mode="live" if (allow_live and not dry_run) else "dry_run")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _metrics(results: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    total = len(results)
    correct = [r for r in results if r["decision_ok"]]
    wrong = [r for r in results if not r["decision_ok"]]
    accuracy = len(correct) / total if total else 0.0
    band_pass = sum(1 for r in results if r["score_band_ok"]) / total if total else 0.0
    mean_conf = _mean([r["confidence"] for r in results])
    conf_on_correct = _mean([r["confidence"] for r in correct]) if correct else None
    conf_on_wrong = _mean([r["confidence"] for r in wrong]) if wrong else None
    return {
        "mode": mode,
        "total": total,
        "decision_accuracy": round(accuracy, 3),
        "score_band_pass_rate": round(band_pass, 3),
        "mean_confidence": round(mean_conf, 3),
        # Calibration gap > 0 means over-confident (confidence exceeds accuracy).
        "calibration_gap": round(mean_conf - accuracy, 3),
        "mean_confidence_on_correct": round(conf_on_correct, 3) if conf_on_correct is not None else None,
        "mean_confidence_on_wrong": round(conf_on_wrong, 3) if conf_on_wrong is not None else None,
        "failures": [
            {"id": r["id"], "expected": r["expected_decision"], "predicted": r["predicted_decision"], "confidence": r["confidence"]}
            for r in wrong
        ],
        "cases": results,
    }


def run_golden_eval(dry_run: bool = True, allow_live: bool = False, path: str | Path | None = None) -> dict[str, Any]:
    return evaluate_cases(load_golden_set(path), dry_run=dry_run, allow_live=allow_live)


def compare_modes(path: str | Path | None = None) -> dict[str, Any]:
    """Run the same golden set through the dry-run baseline and live Gemini, side by side.

    Use this to see exactly which cases the live model gets wrong and whether it is
    over-confident relative to the deterministic baseline. Live mode performs real
    provider calls and is subject to the configured daily cost/rate limits.
    """
    cases = load_golden_set(path)
    baseline = evaluate_cases(cases, dry_run=True, allow_live=False)
    live = evaluate_cases(cases, dry_run=False, allow_live=True)
    regressions = []
    live_by_id = {c["id"]: c for c in live["cases"]}
    for case in baseline["cases"]:
        live_case = live_by_id.get(case["id"], {})
        if case["decision_ok"] and not live_case.get("decision_ok", False):
            regressions.append(
                {
                    "id": case["id"],
                    "expected": case["expected_decision"],
                    "baseline": case["predicted_decision"],
                    "live": live_case.get("predicted_decision"),
                    "live_confidence": live_case.get("confidence"),
                }
            )
    return {
        "baseline": baseline,
        "live": live,
        "accuracy_delta": round(live["decision_accuracy"] - baseline["decision_accuracy"], 3),
        "calibration_gap_delta": round(live["calibration_gap"] - baseline["calibration_gap"], 3),
        "live_regressions": regressions,
    }
