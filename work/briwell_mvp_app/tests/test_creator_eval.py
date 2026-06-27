from app.evals.creator_eval import evaluate_cases, load_golden_set, run_golden_eval


def test_golden_set_loads_and_has_labels() -> None:
    cases = load_golden_set()
    assert len(cases) >= 5
    for case in cases:
        assert case["label"]["expected_decision"] in {
            "pass_to_full_analysis",
            "human_review",
            "recheck_later",
            "avoid",
        }
        assert case["recent_posts"], f"case {case['id']} has no posts"


def test_dry_run_baseline_matches_ground_truth() -> None:
    report = run_golden_eval(dry_run=True)
    # The deterministic heuristic should agree with expert ground truth on clear cases.
    assert report["decision_accuracy"] >= 0.8
    assert report["score_band_pass_rate"] >= 0.8
    assert report["total"] == len(load_golden_set())


def test_report_exposes_calibration_metrics() -> None:
    report = evaluate_cases(load_golden_set(), dry_run=True)
    for key in (
        "decision_accuracy",
        "mean_confidence",
        "calibration_gap",
        "mean_confidence_on_wrong",
        "failures",
        "cases",
    ):
        assert key in report
    # calibration_gap is the headline over-confidence signal; it must be a number.
    assert isinstance(report["calibration_gap"], (int, float))
