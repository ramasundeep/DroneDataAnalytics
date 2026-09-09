"""Anomaly detection per signal group: rolling robust baseline + IsolationForest.

For every new sortie, the baseline is the set of earlier sorties that were not flagged (rolling,
bounded). Two detectors run on the group's feature vector:

* robust z-scores against the baseline median / MAD - interpretable, points at the feature that moved;
* IsolationForest fitted on the standardised baseline vectors - catches multivariate drift a single
  z-score misses. Its score is expressed as a z-score against the baseline's own scores so both
  detectors share one scale.

A sortie is flagged for a group when either z exceeds its threshold or a hard limit was exceeded.
The anomaly score is 0.5 at the flag boundary and saturates at 1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .features import GROUPS, SortieFeatures, component_of, noise_floor

Z_FLAG = 4.0            # robust z threshold on any single feature
IF_FLAG = 3.5           # IsolationForest score z threshold
MIN_BASELINE = 5        # sorties needed before statistical scoring starts
MIN_IFOREST = 8         # sorties needed before the IsolationForest is trusted
MAX_BASELINE = 30       # rolling window of normal sorties kept per group
Z_CLIP = 12.0


@dataclass
class GroupResult:
    group: str
    score: float                    # 0..1, >= 0.5 means flagged
    flagged: bool
    zmax: float
    if_z: float
    top: List[Tuple[str, float]]    # (feature, robust z), largest first
    baseline_n: int
    exceedances: List[Tuple[str, float, float]] = field(default_factory=list)
    warmup: bool = False

    @property
    def top_feature(self) -> Optional[str]:
        return self.top[0][0] if self.top else None

    @property
    def top_component(self) -> Optional[str]:
        return component_of(self.top_feature) if self.top_feature else None


class GroupDetector:
    def __init__(self, group: str, z_flag: float = Z_FLAG, if_flag: float = IF_FLAG, min_baseline: int = MIN_BASELINE,
                 max_baseline: int = MAX_BASELINE, seed: int = 0):
        self.group = group
        self.z_flag, self.if_flag, self.min_baseline, self.max_baseline, self.seed = z_flag, if_flag, min_baseline, max_baseline, seed
        self.names: Optional[List[str]] = None
        self.baseline: List[np.ndarray] = []

    def _robust_z(self, x: np.ndarray) -> np.ndarray:
        B = np.vstack(self.baseline)
        med = np.nanmedian(B, axis=0)
        mad = np.nanmedian(np.abs(B - med), axis=0) * 1.4826
        sd = np.nanstd(B, axis=0, ddof=1) if len(B) > 1 else np.zeros_like(med)
        floors = np.array([noise_floor(n) for n in self.names], dtype=float)
        spread = np.maximum.reduce([np.nan_to_num(mad), np.nan_to_num(sd), floors])
        z = (x - med) / spread
        z = np.where(np.isnan(z), 0.0, z)
        return np.clip(z, -Z_CLIP, Z_CLIP)

    def _iforest_z(self, x: np.ndarray) -> float:
        B = np.vstack(self.baseline)
        B = np.where(np.isnan(B), np.nanmean(B, axis=0), B)
        xx = np.where(np.isnan(x), np.nanmean(B, axis=0), x)
        scaler = StandardScaler().fit(B)
        forest = IsolationForest(n_estimators=200, contamination="auto", random_state=self.seed).fit(scaler.transform(B))
        base_scores = forest.score_samples(scaler.transform(B))
        s = forest.score_samples(scaler.transform(xx.reshape(1, -1)))[0]
        mu, sd = base_scores.mean(), max(base_scores.std(), 1e-3)
        return float(np.clip((mu - s) / sd, -Z_CLIP, Z_CLIP))     # positive = more anomalous than baseline

    def score(self, feats: SortieFeatures) -> GroupResult:
        names = feats.groups.get(self.group, [])
        if self.names is None:
            self.names = list(names)
        x = feats.vector(self.group, self.names)
        exceed = [e for e in feats.exceedances if _exceedance_group(e[0]) == self.group]
        if len(self.baseline) < self.min_baseline:
            flagged = bool(exceed)
            res = GroupResult(self.group, 0.5 if flagged else 0.0, flagged, 0.0, 0.0, [], len(self.baseline), exceed, warmup=True)
        else:
            z = self._robust_z(x)
            if_z = self._iforest_z(x) if len(self.baseline) >= MIN_IFOREST else 0.0
            order = np.argsort(-np.abs(z))
            top = [(self.names[i], round(float(z[i]), 2)) for i in order[:5] if abs(z[i]) > 0.5]
            zmax = float(np.max(np.abs(z))) if len(z) else 0.0
            flagged = zmax >= self.z_flag or if_z >= self.if_flag or bool(exceed)
            score = min(1.0, 0.5 * max(zmax / self.z_flag, if_z / self.if_flag, 1.0 if exceed else 0.0))
            res = GroupResult(self.group, round(score, 3), flagged, round(zmax, 2), round(if_z, 2), top, len(self.baseline), exceed)
        if not res.flagged:
            self.baseline.append(x)
            self.baseline = self.baseline[-self.max_baseline:]
        return res


def _exceedance_group(signal: str) -> str:
    if signal.startswith("servo"):
        return "actuation"
    if signal in ("busVoltageV", "batteryTempC"):
        return "power"
    return "engine"


class FleetAnomalyModel:
    """One detector per group; processes sorties in order and keeps the rolling baselines."""

    def __init__(self, **kw):
        self.detectors = {g: GroupDetector(g, **kw) for g in GROUPS}

    def score(self, feats: SortieFeatures) -> Dict[str, GroupResult]:
        return {g: d.score(feats) for g, d in self.detectors.items()}
