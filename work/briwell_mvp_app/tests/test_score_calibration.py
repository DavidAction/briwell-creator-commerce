from app.scoring.calibration import (
    DIMENSIONS,
    build_samples_from_outcomes,
    recalibrate_weights,
)
from app.scoring.creator_score import SCORING_WEIGHTS


def _sample(commerce: float, other: float, outcome: float) -> dict:
    scores = {dim: other for dim in DIMENSIONS}
    scores["commerce_intent_score"] = commerce
    return {"dimension_scores": scores, "outcome": outcome}


def test_insufficient_samples_returns_current_weights() -> None:
    report = recalibrate_weights([_sample(50, 50, 1.0)])
    assert report["status"] == "insufficient_data"
    assert report["proposed_weights"] == report["current_weights"]


def test_dimension_correlated_with_outcome_gains_weight() -> None:
    # commerce_intent_score moves with the outcome; other dimensions are constant.
    samples = [
        _sample(commerce=10, other=50, outcome=0.1),
        _sample(commerce=30, other=50, outcome=0.3),
        _sample(commerce=50, other=50, outcome=0.5),
        _sample(commerce=70, other=50, outcome=0.7),
        _sample(commerce=90, other=50, outcome=0.9),
    ]
    report = recalibrate_weights(samples)

    assert report["status"] == "proposed"
    assert report["sample_size"] == 5
    # commerce_intent correlates ~1.0 with the outcome -> its weight should rise.
    assert report["correlations"]["commerce_intent_score"] > 0.9
    assert report["proposed_weights"]["commerce_intent_score"] > SCORING_WEIGHTS["commerce_intent_score"]
    # Proposed weights remain a valid distribution.
    assert abs(sum(report["proposed_weights"].values()) - 1.0) < 0.01
    assert all(0 <= w <= 0.40 for w in report["proposed_weights"].values())


def test_build_samples_joins_scores_and_outcomes() -> None:
    analyses = {"c1": {dim: 60 for dim in DIMENSIONS}, "c2": {dim: 40 for dim in DIMENSIONS}}
    outcomes = {"c1": 0.8, "c2": 0.2, "missing": 0.5}
    samples = build_samples_from_outcomes(analyses, outcomes)
    # Only creators with a stored analysis become samples.
    assert len(samples) == 2
    assert {s["creator_id"] for s in samples} == {"c1", "c2"}
