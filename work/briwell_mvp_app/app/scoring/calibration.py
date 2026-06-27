"""Outcome feedback loop for the creator scoring model.

The base scoring weights in ``creator_score.py`` are fixed expert priors. A best-in-class
system learns from results: dimensions that actually correlate with campaign outcomes
(conversions, revenue, ROAS) should carry more weight. This module measures that
correlation from labeled samples and PROPOSES adjusted weights. It never auto-applies —
proposals go to an operator/admin, matching the human-approval discipline used elsewhere.
"""

from __future__ import annotations

from math import sqrt
from typing import Any

from app.scoring.creator_score import SCORING_WEIGHTS


DIMENSIONS: list[str] = list(SCORING_WEIGHTS.keys())
MIN_SAMPLES = 5


def _cap_and_normalize(weights: dict[str, float], min_weight: float, max_weight: float) -> dict[str, float]:
    """Return weights that sum to 1 with every value within [min_weight, max_weight].

    Iterates clamp-then-normalize so that, unlike a single normalization pass, a capped
    dominant weight does not get pushed back above the ceiling. Bounds must be feasible
    (min*n <= 1 <= max*n).
    """
    dims = list(weights)
    total = sum(max(0.0, weights[dim]) for dim in dims) or 1.0
    current = {dim: max(0.0, weights[dim]) / total for dim in dims}
    for _ in range(50):
        clamped = {dim: min(max_weight, max(min_weight, current[dim])) for dim in dims}
        clamped_total = sum(clamped.values()) or 1.0
        normalized = {dim: clamped[dim] / clamped_total for dim in dims}
        if all(min_weight - 1e-9 <= normalized[dim] <= max_weight + 1e-9 for dim in dims):
            return {dim: round(normalized[dim], 4) for dim in dims}
        current = normalized
    return {dim: round(min(max_weight, max(min_weight, current[dim])), 4) for dim in dims}


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return 0.0
    return cov / sqrt(var_x * var_y)


def build_samples_from_outcomes(
    analyses_by_creator: dict[str, dict[str, Any]],
    outcomes_by_creator: dict[str, float],
) -> list[dict[str, Any]]:
    """Join stored creator dimension scores with a per-creator outcome metric
    (e.g. conversion_rate or revenue_usd) into recalibration samples."""
    samples: list[dict[str, Any]] = []
    for creator_id, outcome in outcomes_by_creator.items():
        analysis = analyses_by_creator.get(creator_id)
        if not analysis:
            continue
        dimension_scores = {dim: float(analysis.get(dim, 0) or 0) for dim in DIMENSIONS}
        samples.append({"creator_id": creator_id, "dimension_scores": dimension_scores, "outcome": float(outcome)})
    return samples


def recalibrate_weights(
    samples: list[dict[str, Any]],
    current_weights: dict[str, float] | None = None,
    blend: float = 0.5,
    min_weight: float = 0.02,
    max_weight: float = 0.40,
) -> dict[str, Any]:
    """Propose new scoring weights from outcome-labeled samples.

    Each sample: ``{"dimension_scores": {dim: 0-100}, "outcome": float}``. The proposal
    blends the current weights with a correlation-derived importance, then bounds and
    renormalizes so the weights remain a valid distribution (sum to 1).
    """
    current = dict(current_weights or SCORING_WEIGHTS)

    if len(samples) < MIN_SAMPLES:
        return {
            "status": "insufficient_data",
            "sample_size": len(samples),
            "min_samples": MIN_SAMPLES,
            "current_weights": current,
            "proposed_weights": current,
            "correlations": {},
            "recommendation": f"Collect at least {MIN_SAMPLES} outcome-labeled creators before recalibrating.",
        }

    outcomes = [float(s["outcome"]) for s in samples]
    correlations: dict[str, float] = {}
    for dim in DIMENSIONS:
        xs = [float(s["dimension_scores"].get(dim, 0) or 0) for s in samples]
        correlations[dim] = _pearson(xs, outcomes)

    # Only positive correlation increases a dimension's importance.
    importance = {dim: max(0.0, correlations[dim]) for dim in DIMENSIONS}
    total_importance = sum(importance.values())
    if total_importance <= 0:
        correlation_weights = dict(current)
    else:
        correlation_weights = {dim: importance[dim] / total_importance for dim in DIMENSIONS}

    blended = {
        dim: blend * correlation_weights[dim] + (1 - blend) * current[dim]
        for dim in DIMENSIONS
    }
    proposed = _cap_and_normalize(blended, min_weight=min_weight, max_weight=max_weight)

    movers = sorted(
        ((dim, round(proposed[dim] - current[dim], 4)) for dim in DIMENSIONS),
        key=lambda item: abs(item[1]),
        reverse=True,
    )
    return {
        "status": "proposed",
        "sample_size": len(samples),
        "current_weights": current,
        "proposed_weights": proposed,
        "correlations": {dim: round(value, 3) for dim, value in correlations.items()},
        "largest_changes": movers[:3],
        "recommendation": (
            "Operator/admin review required before applying. Persist approved weights as a new "
            "scoring_rule version; do not silently overwrite the active rule."
        ),
    }
