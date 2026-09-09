"""Unit tests for the scoring primitives (no sorties needed)."""
import numpy as np
import pytest

from analytics.anomaly import GroupDetector
from analytics.features import SortieFeatures
from analytics.rul import assess_component, condition_ratio, trend_rul
from datetime import datetime, timezone


def feats(group, names, values, exceed=()):
    return SortieFeatures("S", "VTOL-1", datetime(2026, 8, 1, tzinfo=timezone.utc), 0.15,
                          dict(zip(names, values)), {group: list(names)}, list(exceed))


def test_condition_ratio_rising_and_falling():
    assert condition_ratio(580, 580, 680) == 0.0
    assert condition_ratio(630, 580, 680) == pytest.approx(0.5)
    assert condition_ratio(500, 580, 680) == 0.0
    assert condition_ratio(23.25, 24.5, 22.0) == pytest.approx(0.5)     # falling indicator (battery voltage)


def test_trend_rul_projects_only_when_elevated_and_rising():
    hours = [100, 100.2, 100.4, 100.6, 100.8, 101.0]
    assert trend_rul(hours, [0.75, 0.76, 0.74, 0.75, 0.76, 0.75], 0.75, 1.8)[0] is None      # nominal noise
    rul, slope = trend_rul(hours, [1.0, 1.1, 1.2, 1.3, 1.4, 1.5], 0.75, 1.8)                 # +0.5/h
    assert slope == pytest.approx(0.5, rel=0.05) and rul == pytest.approx((1.8 - 1.5) / 0.5, rel=0.05)
    assert trend_rul(hours, [1.5, 1.4, 1.3, 1.2, 1.1, 1.0], 0.75, 1.8)[0] is None            # recovering
    assert trend_rul(hours, [1.5, 1.6, 1.7, 1.8, 1.9, 2.0], 0.75, 1.8)[0] == 0.0             # already over
    assert trend_rul([1, 2], [1, 2], 0.75, 1.8)[0] is None                                   # too few points


def test_assess_component_life_and_condition():
    h = assess_component("engine", 142.6, 231, 500, 1200, [], 0.0, False, "S1")
    assert h.alert_level == "normal" and h.rul_hours == pytest.approx(357.4) and h.health_score > 85
    h = assess_component("fuelPump", 275, 400, 300, 900, [], 0.0, False, "S1")              # 91.7 % of hours
    assert h.alert_level == "caution" and h.rul_hours == pytest.approx(25.0)
    hist = [(100 + i * 0.2, 0.8 + 0.12 * i) for i in range(6)]                              # vibration climbing to 1.4
    h = assess_component("ductedFan", 142.6, 231, 800, 2000, hist, 0.0, False, "S6")
    assert h.rul_trend_hours is not None and h.rul_hours == h.rul_trend_hours < 5
    assert h.alert_level in ("advisory", "caution") and h.health_score < 80
    h = assess_component("ductedFan", 142.6, 231, 800, 2000, [(100, 2.1)], 0.9, True, "S7")
    assert h.alert_level == "warning" and h.rul_hours == 0.0


def test_group_detector_warmup_then_flags_outlier_and_keeps_baseline_clean():
    d = GroupDetector("engine", min_baseline=4)
    names = ["egt_cruise_mean", "vib_cruise_mean", "oil_cruise_mean"]
    rng = np.random.default_rng(1)
    for i in range(6):
        r = d.score(feats("engine", names, [570 + rng.normal(0, 3), 0.78 + rng.normal(0, 0.02), 350 + rng.normal(0, 4)]))
        assert not r.flagged
        assert r.warmup == (i < 4)
    n_before = len(d.baseline)
    r = d.score(feats("engine", names, [640, 0.79, 351]))
    assert r.flagged and r.top[0][0] == "egt_cruise_mean" and r.score >= 0.5 and r.top_component == "engine"
    assert len(d.baseline) == n_before, "flagged sorties must not enter the baseline"
    r = d.score(feats("engine", names, [571, 0.77, 349]))
    assert not r.flagged and r.score < 0.5
    r = d.score(feats("engine", names, [571, 0.77, 349], exceed=[("egtC", 690.0, 680.0)]))
    assert r.flagged and r.exceedances and r.score >= 0.5
