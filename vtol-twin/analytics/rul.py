"""Remaining useful life, health score and alert level per component.

Two RUL estimates are combined by taking the minimum:

1. Life-limit RUL - hours left to the component's hour limit, and the hour-equivalent of the cycles
   left (cycles remaining / cycles per hour observed), straight from the Thing's lifeCounters.
2. Trend RUL - a linear regression of the component's condition indicator (per-sortie level, e.g.
   cruise-mean vibration for the ducted fan, cruise-mean EGT for the engine, p95 servo current for a
   servo) against cumulative flight hours over the last TREND_WINDOW sorties, projected to the limit.
   Only projected when the indicator is elevated (ratio above TREND_MIN_RATIO) and rising, so a noisy
   nominal series never produces a spurious short RUL.

Health score (0-100) = 100 - life consumption penalty - condition penalty - exceedance penalty -
anomaly penalty, clamped. Alert levels: normal / advisory / caution / warning; caution or worse
opens a work order in Phase 4.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

ALERT_ORDER = ["normal", "advisory", "caution", "warning"]

# component -> (indicator feature, nominal, threshold, description)
INDICATORS = {
    "engine":    ("egt_cruise_mean", 580.0, 680.0, "cruise EGT"),
    "ductedFan": ("vib_cruise_mean", 0.75, 1.8, "cruise vibration RMS"),
    "servo1":    ("servo1_cur_p95", 1.35, 1.9, "servo 1 current p95"),
    "servo2":    ("servo2_cur_p95", 1.35, 1.9, "servo 2 current p95"),
    "servo3":    ("servo3_cur_p95", 1.35, 1.9, "servo 3 current p95"),
    "servo4":    ("servo4_cur_p95", 1.35, 1.9, "servo 4 current p95"),
    "fuelPump":  ("fuel_flow_per_krpm", 0.9, 1.15, "fuel flow per kRPM"),
    "battery":   ("batt_v_start_min", 24.5, 22.0, "battery voltage under starter load"),   # falling indicator
}
TREND_WINDOW = 6
TREND_MIN_RATIO = 0.2
LIFE_PENALTY, CONDITION_PENALTY, EXCEEDANCE_PENALTY, ANOMALY_PENALTY = 35.0, 60.0, 25.0, 15.0


def alert_max(a: str, b: str) -> str:
    return a if ALERT_ORDER.index(a) >= ALERT_ORDER.index(b) else b


@dataclass
class ComponentHealth:
    component: str
    health_score: float
    rul_hours: float
    rul_life_hours: float
    rul_trend_hours: Optional[float]
    alert_level: str
    anomaly_score: float
    evidence: Dict[str, object] = field(default_factory=dict)

    def to_ditto(self) -> Dict[str, object]:
        return {"healthScore": round(self.health_score, 1), "rulHours": round(self.rul_hours, 1),
                "rulLifeHours": round(self.rul_life_hours, 1),
                "rulTrendHours": None if self.rul_trend_hours is None else round(self.rul_trend_hours, 1),
                "alertLevel": self.alert_level, "anomalyScore": round(self.anomaly_score, 3), "evidence": self.evidence}


def condition_ratio(level: float, nominal: float, threshold: float) -> float:
    """0 at nominal, 1 at threshold, works for rising and falling indicators."""
    span = threshold - nominal
    if abs(span) < 1e-9:
        return 0.0
    return max(0.0, (level - nominal) / span)


def trend_rul(hours: List[float], levels: List[float], nominal: float, threshold: float,
              window: int = TREND_WINDOW) -> Tuple[Optional[float], float]:
    """(hours to threshold or None, slope per hour) from the last `window` (hours, level) points."""
    pts = [(h, l) for h, l in zip(hours, levels) if l is not None and not np.isnan(l)][-window:]
    if len(pts) < 3:
        return None, 0.0
    h = np.array([p[0] for p in pts]); l = np.array([p[1] for p in pts])
    if h[-1] - h[0] < 1e-6:
        return None, 0.0
    slope = float(np.polyfit(h, l, 1)[0])
    level_now = float(l[-1])
    rising = threshold > nominal
    towards = slope > 0 if rising else slope < 0
    ratio = condition_ratio(level_now, nominal, threshold)
    if ratio >= 1.0:
        return 0.0, slope
    if not towards or ratio < TREND_MIN_RATIO:
        return None, slope
    return max(0.0, (threshold - level_now) / slope), slope


def assess_component(component: str, hours: float, cycles: float, limit_hours: float, limit_cycles: float,
                     level_history: List[Tuple[float, float]], anomaly_score: float, exceeded: bool,
                     last_sortie: Optional[str]) -> ComponentHealth:
    """level_history: [(cumulative hours at sortie end, indicator level)] chronological."""
    life_ratio = max(hours / limit_hours if limit_hours else 0.0, cycles / limit_cycles if limit_cycles else 0.0)
    rul_life = max(0.0, limit_hours - hours)
    if cycles and hours and limit_cycles:
        cycles_per_hour = cycles / max(hours, 1e-6)
        rul_life = min(rul_life, max(0.0, (limit_cycles - cycles) / max(cycles_per_hour, 1e-6)))
    score = 100.0 - LIFE_PENALTY * min(life_ratio, 1.0)
    level = alert_max("normal", "caution" if life_ratio >= 0.9 else "advisory" if life_ratio >= 0.8 else "normal")
    evidence: Dict[str, object] = {"lifeRatio": round(life_ratio, 3), "sortieId": last_sortie}
    rul_trend = None
    ind = INDICATORS.get(component)
    if ind and level_history:
        feat, nominal, thr, desc = ind
        hs, ls = [h for h, _ in level_history], [l for _, l in level_history]
        level_now = ls[-1]
        ratio = condition_ratio(level_now, nominal, thr)
        rul_trend, slope = trend_rul(hs, ls, nominal, thr)
        if ratio >= 1.0:
            rul_trend = 0.0                      # already at/over the limit, whatever the history length
        if rul_trend is not None:
            rul_trend = round(rul_trend, 1)
        score -= CONDITION_PENALTY * min(ratio, 1.5)
        if ratio >= 1.0 or exceeded:
            score -= EXCEEDANCE_PENALTY
            level = alert_max(level, "caution")
        evidence.update({"indicator": feat, "description": desc, "level": round(level_now, 3), "nominal": nominal,
                         "threshold": thr, "conditionRatio": round(ratio, 3), "slopePerHour": round(slope, 4),
                         "trendRulHours": None if rul_trend is None else round(rul_trend, 1)})
    if anomaly_score >= 0.5:
        score -= ANOMALY_PENALTY * min(anomaly_score / 0.5, 2.0) / 2.0
        level = alert_max(level, "advisory")
    score = max(0.0, min(100.0, score))
    if score < 50:
        level = alert_max(level, "warning")
    elif score < 65:
        level = alert_max(level, "caution")
    elif score < 80:
        level = alert_max(level, "advisory")
    rul = rul_life if rul_trend is None else min(rul_life, rul_trend)
    return ComponentHealth(component, round(score, 1), round(rul, 1), round(rul_life, 1), rul_trend, level,
                           round(anomaly_score, 3), evidence)
