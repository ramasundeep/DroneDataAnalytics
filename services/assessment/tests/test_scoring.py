from typing import Any

import pytest
from fastapi.testclient import TestClient

from cdsim_assessment.main import create_app
from cdsim_assessment.metrics import landing_attitude_deg, reaction_time_s
from cdsim_assessment.scoring import band_for, score_rubric
from cdsim_common.config import Settings
from cdsim_common.events import Event

LOWER: dict[str, Any] = {
    "id": "m",
    "direction": "lower_is_better",
    "bands": [
        {"label": "a", "limit": 1.0, "score": 1.0},
        {"label": "b", "limit": 2.0, "score": 0.5},
        {"label": "c", "score": 0.0, "pass": False},
    ],
}


@pytest.mark.parametrize(
    ("value", "label"), [(0.0, "a"), (1.0, "a"), (1.0001, "b"), (2.0, "b"), (9.0, "c")]
)
def test_band_boundaries_lower_is_better(value: float, label: str) -> None:
    assert band_for(value, LOWER)["label"] == label


def test_band_higher_is_better() -> None:
    m = {
        "id": "h",
        "direction": "higher_is_better",
        "bands": [{"label": "full", "limit": 1.0, "score": 1}, {"label": "rest", "score": 0}],
    }
    assert band_for(1.0, m)["label"] == "full"
    assert band_for(0.99, m)["label"] == "rest"


def _rubric() -> dict[str, Any]:
    return {
        "id": "r",
        "version": "1.0.0",
        "pass_threshold": 0.6,
        "metrics": [
            {**LOWER, "id": "x", "metric": "reaction_time_s", "weight": 3},
            {**LOWER, "id": "y", "metric": "landing_radial_error_m", "weight": 1, "critical": True},
        ],
    }


def test_weighted_total_and_pass() -> None:
    res = score_rubric(_rubric(), {"x": 0.5, "y": 1.5})
    assert res.total == pytest.approx((3 * 1.0 + 1 * 0.5) / 4)
    assert res.passed and not res.critical_failure


def test_critical_failure_fails_session() -> None:
    res = score_rubric(_rubric(), {"x": 0.1, "y": 50.0})
    assert res.total == 0.75
    assert res.critical_failure and not res.passed


def test_missing_value_scores_zero() -> None:
    res = score_rubric(_rubric(), {"x": 0.1})
    y = next(m for m in res.metrics if m.id == "y")
    assert y.score == 0.0 and not y.passed and y.band.startswith("not_measured")


def test_scoring_is_deterministic() -> None:
    a = score_rubric(_rubric(), {"x": 1.7, "y": 0.2}).model_dump_json()
    b = score_rubric(_rubric(), {"x": 1.7, "y": 0.2}).model_dump_json()
    assert a == b


def test_unimplemented_metric_raises() -> None:
    ev = Event.model_validate(
        {"header": {"simTimeUs": 0, "sessionId": "s", "actorId": "a"}, "annotation": {"text": "t"}}
    )
    with pytest.raises(NotImplementedError, match="Phase 3"):
        reaction_time_s(ev, [])


def test_landing_attitude_from_outcome() -> None:
    ev = Event.model_validate(
        {
            "header": {"simTimeUs": 0, "sessionId": "s", "actorId": "a"},
            "outcome": {"landingTouchdown": {"radialErrorM": 0.2, "rollDeg": -4, "pitchDeg": 2}},
        }
    )
    assert landing_attitude_deg(ev) == 4


def test_api_score_and_validate() -> None:
    c = TestClient(create_app(Settings(), with_infra_checks=False))
    assert c.get("/ready").status_code == 200
    r = c.post(
        "/v1/score",
        json={"rubric_id": "precision_landing_v1", "values": {"landing_radial": 0.2}},
    )
    assert r.status_code == 200 and r.json()["critical_failure"] is True
    bad = c.post("/v1/rubrics/validate", json={"id": "x"}).json()
    assert bad["valid"] is False and bad["errors"]
    assert c.post("/v1/score", json={"rubric_id": "nope", "values": {}}).status_code == 404
