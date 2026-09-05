"""In-memory stand-in for the Ditto Thing plus a compact preview of the Phase 3/4 logic.

* merge semantics identical to what the Ditto mapper produces (JSON merge patch on /features)
* life counters accrue after each sortie
* health scoring: life-limit consumption + condition penalties + linear trend projection
* alerts at caution or above open work orders; sign-off restores the release status
"""
from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

MODEL_PATH = Path(__file__).resolve().parents[1] / "ditto" / "thing-VTOL-1.json"
ALERT_ORDER = ["normal", "advisory", "caution", "warning"]

# component -> (feature, property, nominal, threshold, description). Trend inputs for condition scoring:
# a sortie mean at `nominal` costs nothing, at `threshold` it costs the full condition penalty.
CONDITION_SIGNALS = {
    "engine":    ("engine",    "egtC",           580.0, 680.0, "EGT above continuous limit"),
    "ductedFan": ("vibration", "rmsTotal",       0.9,   1.8,   "vibration RMS above limit"),
    "servo1":    ("actuation", "servo1CurrentA", 0.9,   1.9,   "servo current above limit"),
    "servo2":    ("actuation", "servo2CurrentA", 0.9,   1.9,   "servo current above limit"),
    "servo3":    ("actuation", "servo3CurrentA", 0.9,   1.9,   "servo current above limit"),
    "servo4":    ("actuation", "servo4CurrentA", 0.9,   1.9,   "servo current above limit"),
}
CONDITION_PENALTY = 60.0      # full penalty when the sortie mean sits at the threshold
EXCEEDANCE_PENALTY = 25.0     # extra when the peak crossed the threshold at all
PRIORITY = {"advisory": "low", "caution": "medium", "warning": "high"}
# which injected fault kind a maintenance action on a component clears
FAULT_OF_COMPONENT = {"engine": "egt", "ductedFan": "vibration",
                      "servo1": "servo", "servo2": "servo", "servo3": "servo", "servo4": "servo"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def merge_patch(target: dict, patch: dict) -> dict:
    """RFC 7396 JSON merge patch, applied in place (null deletes)."""
    for k, v in patch.items():
        if v is None:
            target.pop(k, None)
        elif isinstance(v, dict):
            node = target.get(k)
            if not isinstance(node, dict):
                node = target[k] = {}
            merge_patch(node, v)
        else:
            target[k] = v
    return target


def alert_max(a: str, b: str) -> str:
    return a if ALERT_ORDER.index(a) >= ALERT_ORDER.index(b) else b


# a within-sortie trend is only projected when the sortie mean is this far above nominal (0..1 scale)
TREND_MIN_RATIO = 0.2


class SortieStats:
    """Per-sortie running statistics used for condition scoring and trend projection.

    Means and peaks cover every armed sample; the slope is a least-squares fit over the steady
    fixed-wing cruise segment only, so engine start-up and shutdown transients do not masquerade
    as a trend.
    """

    def __init__(self) -> None:
        self.n = 0
        self.last: Dict[str, float] = {}
        self.peak: Dict[str, float] = {}
        self.mean_acc: Dict[str, float] = {}
        self.cruise: Dict[str, List[tuple]] = {}      # comp -> [(t_hours, value)]

    def add(self, features: dict, only_when_flying: bool = True) -> None:
        fs = features.get("flightState", {})
        if only_when_flying and not fs.get("armed", False):
            return
        self.n += 1
        in_cruise = fs.get("vtolState") == "fixed-wing"
        t_h = float(fs.get("flightTimeS", 0)) / 3600.0
        for comp, (feat, prop, _nom, _thr, _d) in CONDITION_SIGNALS.items():
            v = features.get(feat, {}).get(prop)
            if v is None:
                continue
            self.last[comp] = v
            self.peak[comp] = max(self.peak.get(comp, v), v)
            self.mean_acc[comp] = self.mean_acc.get(comp, 0.0) + v
            if in_cruise:
                self.cruise.setdefault(comp, []).append((t_h, v))

    def mean(self, comp: str) -> Optional[float]:
        return self.mean_acc[comp] / self.n if comp in self.mean_acc and self.n else None

    def slope_per_hour(self, comp: str) -> float:
        """Least-squares slope (units/hour) over the cruise samples; 0 when there are too few."""
        pts = self.cruise.get(comp, [])
        if len(pts) < 10:
            return 0.0
        n = len(pts)
        mx = sum(t for t, _ in pts) / n
        my = sum(v for _, v in pts) / n
        sxx = sum((t - mx) ** 2 for t, _ in pts)
        if sxx <= 0:
            return 0.0
        return sum((t - mx) * (v - my) for t, v in pts) / sxx

    def cruise_mean(self, comp: str) -> Optional[float]:
        pts = self.cruise.get(comp, [])
        return sum(v for _, v in pts) / len(pts) if pts else None


class WorkOrder(dict):
    pass


class InMemoryTwin:
    def __init__(self, model_path: Path = MODEL_PATH):
        self.model = json.loads(Path(model_path).read_text())
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self) -> None:
        self.thing = copy.deepcopy(self.model)
        self.work_orders: List[WorkOrder] = []
        self.alerts: List[dict] = []
        self.sorties: List[dict] = []
        self.revision = 0
        self.condition: Dict[str, dict] = {}   # component -> last condition assessment
        self.wear: Dict[str, float] = {}       # injected fault kind -> accumulated wear (demo timeline)
        self._recompute_health()

    @property
    def components(self) -> Dict[str, dict]:
        return self.thing["attributes"]["components"]

    @property
    def features(self) -> Dict[str, dict]:
        return self.thing["features"]

    def merge_features(self, patch: Dict[str, dict]) -> None:
        """patch: {featureId: {props}} exactly as published on MQTT."""
        wrapped = {fid: {"properties": props} for fid, props in patch.items()}
        merge_patch(self.thing["features"], wrapped)
        self.revision += 1

    # ---------------------------------------------------------------- sorties
    def close_sortie(self, sortie_id: str, flight_hours: float, stats: SortieStats,
                     degradation: str = "none", wear_added: float = 0.0) -> dict:
        if degradation != "none" and wear_added:
            self.wear[degradation] = round(self.wear.get(degradation, 0.0) + wear_added, 4)
        counters = self.features["lifeCounters"]["properties"]
        for cid in list(self.components) + ["airframe"]:
            c = counters.setdefault(cid, {"hours": 0.0, "cycles": 0})
            c["hours"] = round(c["hours"] + flight_hours, 3)
            c["cycles"] = int(c["cycles"]) + 1
        counters["lastSortieId"] = sortie_id
        counters["updatedAt"] = now_iso()
        self.thing["attributes"]["airframe"]["totalAirframeHours"] = counters["airframe"]["hours"]
        self.thing["attributes"]["airframe"]["totalLandings"] = counters["airframe"]["cycles"]

        # condition assessment from this sortie's statistics
        for comp, (feat, prop, nominal, thr, desc) in CONDITION_SIGNALS.items():
            if comp not in stats.last:
                continue
            peak, mean = stats.peak[comp], stats.mean(comp)
            slope_per_h = stats.slope_per_hour(comp)
            ratio = max(0.0, (mean - nominal) / (thr - nominal))
            trend_rul = None
            level_now = stats.cruise_mean(comp)
            if level_now is not None and level_now >= thr:
                trend_rul = 0.0
            elif slope_per_h > 0 and ratio >= TREND_MIN_RATIO and level_now is not None:
                trend_rul = (thr - level_now) / slope_per_h
            self.condition[comp] = {
                "signal": f"{feat}.{prop}", "mean": round(mean, 3), "peak": round(peak, 3),
                "nominal": nominal, "threshold": thr, "ratio": round(ratio, 3),
                "slopePerHour": round(slope_per_h, 4),
                "trendRulHours": None if trend_rul is None else round(trend_rul, 1),
                "sortieId": sortie_id, "description": desc,
            }
        record = {
            "sortieId": sortie_id, "flightHours": round(flight_hours, 3), "degradation": degradation,
            "endedAt": now_iso(), "samples": stats.n,
            "wear": self.wear.get(degradation) if degradation != "none" else None,
        }
        self.sorties.append(record)
        self._recompute_health()
        self.revision += 1
        return record

    # ----------------------------------------------------------------- health
    def _recompute_health(self) -> None:
        health = self.features["health"]["properties"]
        counters = self.features["lifeCounters"]["properties"]
        worst = "normal"
        for cid, c in self.components.items():
            hours = counters.get(cid, {}).get("hours", c["hoursConsumed"])
            cycles = counters.get(cid, {}).get("cycles", c["cyclesConsumed"])
            life_ratio = max(hours / c["lifeLimitHours"], cycles / c["lifeLimitCycles"])
            rul_life = max(0.0, c["lifeLimitHours"] - hours)
            score = 100.0 - 35.0 * min(life_ratio, 1.0)
            level = "normal"
            cond = self.condition.get(cid)
            rul = rul_life
            if cond:
                score -= CONDITION_PENALTY * min(cond["ratio"], 1.5)
                if cond["peak"] >= cond["threshold"]:
                    score -= EXCEEDANCE_PENALTY
                    level = alert_max(level, "caution")
                if cond["trendRulHours"] is not None:
                    rul = min(rul, cond["trendRulHours"])
            if life_ratio >= 0.9:
                level = alert_max(level, "caution")
            elif life_ratio >= 0.8:
                level = alert_max(level, "advisory")
            score = max(0.0, min(100.0, score))
            if score < 50:
                level = alert_max(level, "warning")
            elif score < 65:
                level = alert_max(level, "caution")
            elif score < 80:
                level = alert_max(level, "advisory")
            # an open work order keeps the component at least at caution until signed off
            if self.open_work_order(cid):
                level = alert_max(level, "caution")
            health[cid] = {"healthScore": round(score, 1), "rulHours": round(rul, 1), "alertLevel": level}
            worst = alert_max(worst, level)
        self._raise_work_orders()
        self._update_release()

    def _raise_work_orders(self) -> None:
        health = self.features["health"]["properties"]
        for cid, h in health.items():
            if cid == "aircraft":
                continue
            if ALERT_ORDER.index(h["alertLevel"]) >= ALERT_ORDER.index("caution") and not self.open_work_order(cid):
                cond = self.condition.get(cid)
                c = self.components[cid]
                counters = self.features["lifeCounters"]["properties"].get(cid, {})
                if cond and cond["peak"] >= cond["threshold"]:
                    defect = f"{cond['description']}: peak {cond['peak']} vs limit {cond['threshold']} ({cond['signal']})"
                elif counters.get("hours", 0) / c["lifeLimitHours"] >= 0.9:
                    defect = f"life limit approaching: {counters.get('hours')} of {c['lifeLimitHours']} h"
                else:
                    defect = f"health score {h['healthScore']} below threshold"
                self.alerts.append({"ts": now_iso(), "component": cid, "level": h["alertLevel"], "text": defect})
                self.work_orders.append(WorkOrder({
                    "id": f"WO-{len(self.work_orders) + 1:04d}", "uuid": uuid.uuid4().hex[:8],
                    "createdAt": now_iso(), "status": "open", "component": cid,
                    "componentName": c["name"], "serial": c["serial"],
                    "priority": PRIORITY[h["alertLevel"]], "alertLevel": h["alertLevel"],
                    "defect": defect, "evidence": cond, "manHours": None, "partsConsumed": [],
                    "action": None, "signedOffBy": None, "closedAt": None,
                }))

    def _update_release(self) -> None:
        health = self.features["health"]["properties"]
        open_wos = [w for w in self.work_orders if w["status"] == "open"]
        worst = "normal"
        for cid, h in health.items():
            if cid != "aircraft":
                worst = alert_max(worst, h["alertLevel"])
        if worst == "warning" or any(w["priority"] == "high" for w in open_wos):
            status = "unserviceable"
        elif open_wos or worst == "caution":
            status = "limited"
        else:
            status = "serviceable"
        health["aircraft"] = {"releaseStatus": status, "openWorkOrders": len(open_wos), "updatedAt": now_iso()}

    # ------------------------------------------------------------ work orders
    def open_work_order(self, cid: str) -> Optional[WorkOrder]:
        return next((w for w in self.work_orders if w["component"] == cid and w["status"] == "open"), None)

    def sign_off(self, wo_id: str, action: str, signed_by: str, man_hours: float,
                 parts: Optional[List[str]] = None) -> WorkOrder:
        wo = next((w for w in self.work_orders if w["id"] == wo_id), None)
        if wo is None:
            raise KeyError(wo_id)
        if wo["status"] != "open":
            raise ValueError(f"{wo_id} is already {wo['status']}")
        if action not in ("repaired", "replaced", "inspected-no-fault"):
            raise ValueError("action must be repaired | replaced | inspected-no-fault")
        cid = wo["component"]
        wo.update({"status": "closed", "action": action, "signedOffBy": signed_by,
                   "manHours": man_hours, "partsConsumed": parts or [], "closedAt": now_iso()})
        self.condition.pop(cid, None)          # the defect evidence is cleared by the maintenance action
        if action != "inspected-no-fault":
            self.wear.pop(FAULT_OF_COMPONENT.get(cid, ""), None)
        if action == "replaced":
            c = self.components[cid]
            c["serial"] = f"{c['serial'].rsplit('-', 1)[0]}-{uuid.uuid4().hex[:4].upper()}"
            c["installDate"] = now_iso()[:10]
            c["hoursConsumed"] = 0.0
            c["cyclesConsumed"] = 0
            self.features["lifeCounters"]["properties"][cid] = {"hours": 0.0, "cycles": 0}
        self._recompute_health()
        self.revision += 1
        return wo

    # --------------------------------------------------------------- snapshot
    def snapshot(self) -> dict:
        return {
            "revision": self.revision,
            "thing": self.thing,
            "workOrders": self.work_orders,
            "alerts": self.alerts[-50:],
            "sorties": self.sorties[-20:],
            "condition": self.condition,
            "wear": self.wear,
        }
