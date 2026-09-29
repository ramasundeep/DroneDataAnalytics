"""Rubric scoring: turn metric values into per-metric and overall scores.

Rubric format: schemas/json/rubric.schema.json, semantics in
docs/06_ASSESSMENT_ENGINE.md §"Rubrics". Pure functions, no I/O, fully
deterministic — the same inputs always give byte-identical results (a Phase 3
acceptance criterion).

Band rule: bands are ordered best→worst. For ``lower_is_better`` a value
falls in the first band with ``value <= limit``; for ``higher_is_better`` the
first band with ``value >= limit``. The last band has no limit and catches
everything else.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MetricScore(BaseModel):
    id: str
    metric: str
    value: float | None
    band: str
    score: float
    weight: float
    passed: bool
    critical: bool


class RubricResult(BaseModel):
    rubric_id: str
    rubric_version: str
    total: float
    passed: bool
    critical_failure: bool
    metrics: list[MetricScore]


def band_for(value: float, metric: dict[str, Any]) -> dict[str, Any]:
    lower_better = metric["direction"] == "lower_is_better"
    for band in metric["bands"]:
        limit = band.get("limit")
        if limit is None:
            return dict(band)
        if (lower_better and value <= limit) or (not lower_better and value >= limit):
            return dict(band)
    raise ValueError(f"metric {metric['id']}: no catch-all band")  # schema prevents this


def score_rubric(rubric: dict[str, Any], values: dict[str, float | None]) -> RubricResult:
    """Score ``values`` (keyed by rubric metric id) against ``rubric``.

    A missing value (``None`` or absent) scores 0 in the worst band and fails:
    if the engine could not measure something, the trainee does not get
    credit for it. Weights are normalised so the total is in [0, 1].
    """
    scores: list[MetricScore] = []
    for m in rubric["metrics"]:
        value = values.get(m["id"])
        band: dict[str, Any]
        if value is None:
            worst = m["bands"][-1]
            band = {"label": f"not_measured ({worst['label']})", "score": 0.0, "pass": False}
        else:
            band = band_for(value, m)
        scores.append(
            MetricScore(
                id=m["id"],
                metric=m["metric"],
                value=value,
                band=band["label"],
                score=float(band["score"]),
                weight=float(m["weight"]),
                passed=bool(band.get("pass", True)),
                critical=bool(m.get("critical", False)),
            )
        )
    total_weight = sum(s.weight for s in scores)
    total = sum(s.score * s.weight for s in scores) / total_weight if total_weight else 0.0
    total = round(total, 6)
    critical_failure = any(s.critical and not s.passed for s in scores)
    return RubricResult(
        rubric_id=rubric["id"],
        rubric_version=rubric["version"],
        total=total,
        passed=total >= rubric["pass_threshold"] and not critical_failure,
        critical_failure=critical_failure,
        metrics=scores,
    )
