"""Orchestration: sorties -> features -> anomaly results -> component health, plus the writes.

`Analyzer.run(source, counters, components)` is pure with respect to I/O: it returns a RunResult.
`publish()` turns a RunResult into a Ditto merge patch and InfluxDB points.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from influxdb_client import Point, WritePrecision

from common.logging_setup import log

from .anomaly import FleetAnomalyModel, GroupResult
from .features import GROUPS, SortieData, SortieFeatures, component_of, extract
from .rul import INDICATORS, ComponentHealth, alert_max, assess_component

logger = logging.getLogger("analytics.engine")
RECENT_EXCEEDANCE_SORTIES = 3     # a limit exceedance keeps its component at caution for this many sorties


@dataclass
class SortieResult:
    features: SortieFeatures
    groups: Dict[str, GroupResult]
    cumulative_hours: float

    @property
    def flagged(self) -> bool:
        return any(g.flagged for g in self.groups.values())

    @property
    def flagged_groups(self) -> List[str]:
        return [g for g, r in self.groups.items() if r.flagged]

    def component_anomaly(self, component: str) -> float:
        """Anomaly score attributed to a component: its own features' z within the flagged group."""
        best = 0.0
        for res in self.groups.values():
            for feat, z in res.top:
                if component_of(feat) == component:
                    best = max(best, min(1.0, 0.5 * abs(z) / 4.0))
            if res.flagged and res.top_component == component:
                best = max(best, res.score)
            if res.exceedances and any(component_of_signal(sig) == component for sig, _, _ in res.exceedances):
                best = max(best, res.score)
        return round(best, 3)

    def summary(self) -> dict:
        return {"sortieId": self.features.sortie_id, "endUtc": self.features.end_utc.isoformat(), "flightHours": self.features.flight_hours,
                "cumulativeHours": round(self.cumulative_hours, 3), "flagged": self.flagged, "degradation": self.features.degradation,
                "groups": {g: {"score": r.score, "flagged": r.flagged, "zmax": r.zmax, "ifZ": r.if_z, "baselineN": r.baseline_n,
                               "warmup": r.warmup, "top": r.top[:3], "exceedances": r.exceedances} for g, r in self.groups.items()}}


def component_of_signal(signal: str) -> Optional[str]:
    if signal.startswith("servo"):
        return signal[:6]
    return {"egtC": "engine", "chtC": "engine", "rmsTotal": "ductedFan", "busVoltageV": "avionics", "batteryTempC": "battery"}.get(signal)


@dataclass
class RunResult:
    tail: str
    ran_at: datetime
    sorties: List[SortieResult]
    health: Dict[str, ComponentHealth]
    worst_alert: str

    def summary(self) -> dict:
        return {"tail": self.tail, "ranAt": self.ran_at.isoformat(), "sorties": [s.summary() for s in self.sorties],
                "health": {c: h.to_ditto() for c, h in self.health.items()}, "worstAlert": self.worst_alert,
                "flaggedSorties": [s.features.sortie_id for s in self.sorties if s.flagged]}


class Analyzer:
    def __init__(self, **detector_kw):
        self.detector_kw = detector_kw

    def run(self, source: Iterable[SortieData], counters: Dict[str, dict], components: Dict[str, dict],
            starting_hours: Optional[float] = None) -> RunResult:
        """counters: Thing lifeCounters (hours/cycles per component, post-ingest); components: Thing attributes."""
        model = FleetAnomalyModel(**self.detector_kw)
        results: List[SortieResult] = []
        history: Dict[str, List[tuple]] = {c: [] for c in INDICATORS}
        last_exceedance: Dict[str, dict] = {}
        datas = list(source)
        total_sortie_hours = sum(d.flight_hours for d in datas)
        airframe_hours_now = float((counters.get("airframe") or {}).get("hours", 0.0))
        start = airframe_hours_now - total_sortie_hours if starting_hours is None else starting_hours
        cum = start
        tail = datas[0].tail if datas else "unknown"
        for data in datas:
            feats = extract(data)
            groups = model.score(feats)
            cum += data.flight_hours
            res = SortieResult(feats, groups, cum)
            results.append(res)
            for comp, (feat, _n, _t, _d) in INDICATORS.items():
                if feat in feats.values:
                    history[comp].append((cum, feats.values[feat]))
            for sig, peak, limit in feats.exceedances:
                comp = component_of_signal(sig)
                if comp:
                    last_exceedance[comp] = {"sortieId": feats.sortie_id, "signal": sig, "peak": peak, "limit": limit,
                                             "at": feats.end_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
                                             "sortieIndex": len(results)}
            log(logger, "sortie scored", sortie=feats.sortie_id, flagged=res.flagged, groups=res.flagged_groups,
                degradation=feats.degradation, exceedances=[e[0] for e in feats.exceedances])
        last = results[-1] if results else None
        health: Dict[str, ComponentHealth] = {}
        worst = "normal"
        for cid, c in components.items():
            cnt = counters.get(cid) or {}
            hours = float(cnt.get("hours", c.get("hoursConsumed", 0.0)))
            cycles = float(cnt.get("cycles", c.get("cyclesConsumed", 0)))
            anomaly = last.component_anomaly(cid) if last else 0.0
            exc = last_exceedance.get(cid)
            recent = exc is not None and (len(results) - exc["sortieIndex"]) <= RECENT_EXCEEDANCE_SORTIES
            h = assess_component(cid, hours, cycles, float(c["lifeLimitHours"]), float(c["lifeLimitCycles"]),
                                 history.get(cid, []), anomaly, recent, last.features.sortie_id if last else None)
            if exc is not None:
                h.evidence["lastExceedance"] = {k: v for k, v in exc.items() if k != "sortieIndex"}
                h.evidence["lastExceedance"]["recent"] = recent
            health[cid] = h
            worst = alert_max(worst, h.alert_level)
        return RunResult(tail, datetime.now(timezone.utc), results, health, worst)


def ditto_patch(run: RunResult) -> Dict[str, dict]:
    props = {c: h.to_ditto() for c, h in run.health.items()}
    last = run.sorties[-1] if run.sorties else None
    props["lastRun"] = {"at": run.ran_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
                        "sortiesScored": len(run.sorties), "worstAlert": run.worst_alert,
                        "lastSortieId": last.features.sortie_id if last else None,
                        "lastSortieFlagged": last.flagged if last else False,
                        "flaggedGroups": last.flagged_groups if last else []}
    return {"health": props}


def influx_points(run: RunResult) -> List[Point]:
    pts: List[Point] = []
    for c, h in run.health.items():
        p = (Point("health").tag("tail", run.tail).tag("component", c).field("healthScore", float(h.health_score))
             .field("rulHours", float(h.rul_hours)).field("rulLifeHours", float(h.rul_life_hours))
             .field("anomalyScore", float(h.anomaly_score)).field("alertLevel", h.alert_level)
             .field("alertRank", float(["normal", "advisory", "caution", "warning"].index(h.alert_level)))
             .time(run.ran_at, WritePrecision.MS))
        if h.rul_trend_hours is not None:
            p.field("rulTrendHours", float(h.rul_trend_hours))
        pts.append(p)
    for s in run.sorties:
        for g, r in s.groups.items():
            pts.append(Point("anomaly").tag("tail", run.tail).tag("sortie", s.features.sortie_id).tag("group", g)
                       .field("score", float(r.score)).field("flagged", bool(r.flagged)).field("zmax", float(r.zmax))
                       .field("ifZ", float(r.if_z)).field("topFeature", r.top_feature or "").field("baselineN", float(r.baseline_n))
                       .time(s.features.end_utc, WritePrecision.MS))
    return pts
