"""Per-sortie feature extraction.

Input: a SortieData - one pandas DataFrame per twin feature (engine, vibration, actuation, power,
flightState), indexed by UTC time, columns = properties. Output: a flat dict of scalar features grouped
by signal group, plus threshold exceedances. Everything is computed on armed samples; "cruise" is the
fixed-wing segment where the engine runs at a steady point, so cruise statistics are the cleanest
condition indicators.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

GROUPS = ("engine", "actuation", "power")

# signal limits shared with the demo twin and the Grafana limit lines
LIMITS = {
    "egtC": 680.0, "chtC": 205.0, "rmsTotal": 1.8,
    "servo1CurrentA": 1.9, "servo2CurrentA": 1.9, "servo3CurrentA": 1.9, "servo4CurrentA": 1.9,
    "busVoltageV_min": 24.0, "batteryTempC": 55.0,
}

# sensor / process noise floors per feature (units of the feature): the baseline spread used for z-scores
# is never smaller than this, so a handful of near-identical sorties cannot make trivial noise look anomalous
NOISE_FLOOR = [
    ("egt_", 3.0), ("cht_", 1.5), ("rpm_cruise_std", 10.0), ("oil_", 5.0), ("fuel_flow_per_krpm", 0.02),
    ("vib_per_rpm2", 0.05), ("vib_max", 0.08), ("vib_", 0.03),
    ("servo", 0.03), ("bus_v", 0.1), ("bus_i", 0.2), ("batt_v", 0.1), ("batt_temp", 0.5), ("batt_drop", 0.5),
]


def noise_floor(feature: str) -> float:
    for prefix, floor in NOISE_FLOOR:
        if feature.startswith(prefix):
            return floor
    return 1e-6


# feature name prefix -> component it speaks for (used to attribute anomalies)
FEATURE_COMPONENT = {
    "egt": "engine", "cht": "engine", "oil": "engine", "rpm": "engine",
    "vib": "ductedFan", "fuel": "fuelPump",
    "servo1": "servo1", "servo2": "servo2", "servo3": "servo3", "servo4": "servo4",
    "bus": "avionics", "batt": "battery",
}


@dataclass
class SortieData:
    sortie_id: str
    tail: str
    frames: Dict[str, pd.DataFrame]          # feature id -> DataFrame (index: UTC datetime)
    flight_hours: float
    end_utc: datetime
    degradation: Optional[str] = None       # synthetic logs only, used by tests / reporting

    def frame(self, name: str) -> pd.DataFrame:
        return self.frames.get(name, pd.DataFrame())


@dataclass
class SortieFeatures:
    sortie_id: str
    tail: str
    end_utc: datetime
    flight_hours: float
    values: Dict[str, float]                 # flat feature -> value
    groups: Dict[str, List[str]]             # group -> feature names
    exceedances: List[Tuple[str, float, float]] = field(default_factory=list)   # (signal, peak, limit)
    degradation: Optional[str] = None

    def vector(self, group: str, names: Optional[List[str]] = None) -> np.ndarray:
        names = names or self.groups[group]
        return np.array([self.values.get(n, np.nan) for n in names], dtype=float)


def _slope_per_hour(series: pd.Series) -> float:
    """Least-squares slope in units/hour over the series' own time axis (0 when too short/flat)."""
    s = series.dropna()
    if len(s) < 10:
        return 0.0
    t = (s.index - s.index[0]).total_seconds().to_numpy() / 3600.0
    if t[-1] - t[0] < 1e-6:
        return 0.0
    tm, ym = t.mean(), s.to_numpy().mean()
    denom = ((t - tm) ** 2).sum()
    return float(((t - tm) * (s.to_numpy() - ym)).sum() / denom) if denom > 0 else 0.0


def _stat(series: pd.Series, fn: str) -> float:
    s = series.dropna()
    if s.empty:
        return float("nan")
    if fn == "p95":
        return float(np.percentile(s, 95))
    return float(getattr(s, fn)())


def extract(data: SortieData) -> SortieFeatures:
    fs = data.frame("flightState")
    armed_idx = fs.index[fs.get("armed", pd.Series(dtype=bool)).fillna(False).astype(bool)] if not fs.empty else pd.DatetimeIndex([])
    cruise_idx = fs.index[fs.get("vtolState", pd.Series(dtype=object)) == "fixed-wing"] if not fs.empty else pd.DatetimeIndex([])
    hover_idx = fs.index[fs.get("vtolState", pd.Series(dtype=object)) == "hover"] if not fs.empty else pd.DatetimeIndex([])
    start_idx = fs.index[fs.get("flightMode", pd.Series(dtype=object)).eq("MANUAL") & fs.get("armed", pd.Series(dtype=bool)).fillna(False).astype(bool)] if not fs.empty else pd.DatetimeIndex([])

    def sel(frame: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.DataFrame:
        if frame.empty or len(idx) == 0:
            return pd.DataFrame(columns=frame.columns)
        return frame.reindex(frame.index.intersection(idx))

    v: Dict[str, float] = {}
    groups: Dict[str, List[str]] = {g: [] for g in GROUPS}
    exceed: List[Tuple[str, float, float]] = []

    def put(group: str, name: str, value: float) -> None:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return
        v[name] = round(float(value), 4)
        groups[group].append(name)

    # ---------------------------------------------------------------- engine (+ vibration, fuel)
    eng, vib = data.frame("engine"), data.frame("vibration")
    e_arm, e_cr = sel(eng, armed_idx), sel(eng, cruise_idx)
    if not e_arm.empty and "egtC" in e_arm:
        running = e_arm[e_arm.get("running", True).astype(bool)] if "running" in e_arm else e_arm
        put("engine", "egt_cruise_mean", _stat(e_cr.get("egtC", pd.Series(dtype=float)), "mean"))
        put("engine", "egt_cruise_p95", _stat(e_cr.get("egtC", pd.Series(dtype=float)), "p95"))
        put("engine", "egt_max", _stat(running["egtC"], "max"))
        put("engine", "cht_cruise_mean", _stat(e_cr.get("chtC", pd.Series(dtype=float)), "mean"))
        put("engine", "rpm_cruise_std", _stat(e_cr.get("rpm", pd.Series(dtype=float)), "std"))
        put("engine", "oil_cruise_mean", _stat(e_cr.get("oilPressureKpa", pd.Series(dtype=float)), "mean"))
        rpm_mean = _stat(e_cr.get("rpm", pd.Series(dtype=float)), "mean")
        ff_mean = _stat(e_cr.get("fuelFlowLph", pd.Series(dtype=float)), "mean")
        if rpm_mean and not np.isnan(rpm_mean) and rpm_mean > 0 and not np.isnan(ff_mean):
            put("engine", "fuel_flow_per_krpm", ff_mean / rpm_mean * 1000.0)
        peak = _stat(running["egtC"], "max")
        if not np.isnan(peak) and peak >= LIMITS["egtC"]:
            exceed.append(("egtC", round(peak, 1), LIMITS["egtC"]))
        cpeak = _stat(running.get("chtC", pd.Series(dtype=float)), "max")
        if not np.isnan(cpeak) and cpeak >= LIMITS["chtC"]:
            exceed.append(("chtC", round(cpeak, 1), LIMITS["chtC"]))
    v_arm, v_cr, v_hv = sel(vib, armed_idx), sel(vib, cruise_idx), sel(vib, hover_idx)
    if not v_arm.empty and "rmsTotal" in v_arm:
        put("engine", "vib_cruise_mean", _stat(v_cr.get("rmsTotal", pd.Series(dtype=float)), "mean"))
        put("engine", "vib_hover_mean", _stat(v_hv.get("rmsTotal", pd.Series(dtype=float)), "mean"))
        put("engine", "vib_max", _stat(v_arm["rmsTotal"], "max"))
        rpm_cr = sel(eng, cruise_idx).get("rpm", pd.Series(dtype=float))
        rm = _stat(rpm_cr, "mean")
        vm = _stat(v_cr.get("rmsTotal", pd.Series(dtype=float)), "mean")
        if not np.isnan(rm) and rm > 0 and not np.isnan(vm):
            put("engine", "vib_per_rpm2", vm / (rm / 6500.0) ** 2)
        peak = _stat(v_arm["rmsTotal"], "max")
        if peak >= LIMITS["rmsTotal"]:
            exceed.append(("rmsTotal", round(peak, 3), LIMITS["rmsTotal"]))

    # ---------------------------------------------------------------- actuation
    act = data.frame("actuation")
    a_arm = sel(act, armed_idx)
    if not a_arm.empty and "servo1CurrentA" in a_arm:
        means = {i: _stat(a_arm[f"servo{i}CurrentA"], "mean") for i in range(1, 5) if f"servo{i}CurrentA" in a_arm}
        med = float(np.nanmedian(list(means.values()))) if means else float("nan")
        for i, m in means.items():
            col = a_arm[f"servo{i}CurrentA"]
            put("actuation", f"servo{i}_cur_mean", m)
            put("actuation", f"servo{i}_cur_p95", _stat(col, "p95"))
            put("actuation", f"servo{i}_cur_ratio", m / med if med and med > 0 else float("nan"))
            peak = _stat(col, "max")
            if peak >= LIMITS[f"servo{i}CurrentA"]:
                exceed.append((f"servo{i}CurrentA", round(peak, 3), LIMITS[f"servo{i}CurrentA"]))

    # ---------------------------------------------------------------- power
    pw = data.frame("power")
    p_arm, p_st = sel(pw, armed_idx), sel(pw, start_idx)
    if not p_arm.empty and "busVoltageV" in p_arm:
        put("power", "bus_v_mean", _stat(p_arm["busVoltageV"], "mean"))
        put("power", "bus_v_min", _stat(p_arm["busVoltageV"], "min"))
        put("power", "bus_i_mean", _stat(p_arm.get("busCurrentA", pd.Series(dtype=float)), "mean"))
        put("power", "batt_v_min", _stat(p_arm.get("batteryVoltageV", pd.Series(dtype=float)), "min"))
        put("power", "batt_v_start_min", _stat(p_st.get("batteryVoltageV", pd.Series(dtype=float)), "min"))
        put("power", "batt_temp_max", _stat(p_arm.get("batteryTempC", pd.Series(dtype=float)), "max"))
        rem = p_arm.get("batteryRemainingPct", pd.Series(dtype=float)).dropna()
        if len(rem) > 2:
            put("power", "batt_drop_pct", float(rem.iloc[0] - rem.min()))
        bmin = _stat(p_arm["busVoltageV"], "min")
        if not np.isnan(bmin) and bmin < LIMITS["busVoltageV_min"]:
            exceed.append(("busVoltageV", round(bmin, 2), LIMITS["busVoltageV_min"]))
        tmax = _stat(p_arm.get("batteryTempC", pd.Series(dtype=float)), "max")
        if not np.isnan(tmax) and tmax >= LIMITS["batteryTempC"]:
            exceed.append(("batteryTempC", round(tmax, 1), LIMITS["batteryTempC"]))

    return SortieFeatures(sortie_id=data.sortie_id, tail=data.tail, end_utc=data.end_utc, flight_hours=data.flight_hours,
                          values=v, groups=groups, exceedances=exceed, degradation=data.degradation)


def component_of(feature: str) -> Optional[str]:
    for prefix, comp in FEATURE_COMPONENT.items():
        if feature.startswith(prefix):
            return comp
    return None
