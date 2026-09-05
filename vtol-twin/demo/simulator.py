"""Synthetic sortie generator for VTOL-1.

Produces one telemetry sample per simulated second through a hover -> transition -> cruise ->
transition -> land profile, with optional degradation injection (rising vibration, EGT drift,
servo current creep). Deterministic for a given seed. Pure Python, no I/O.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterator, List, Optional

TAIL = "VTOL-1"

# phase name, duration in simulated seconds (cruise is overridden by SortieConfig)
PHASES: List[tuple] = [
    ("preflight", 15),
    ("engine-start", 15),
    ("hover-climb", 60),
    ("transition-forward", 25),
    ("cruise", 480),
    ("transition-back", 25),
    ("hover-descent", 60),
    ("landed", 10),
    ("shutdown", 10),
]
FLIGHT_PHASES = {"hover-climb", "transition-forward", "cruise", "transition-back", "hover-descent"}
VTOL_STATE = {
    "preflight": "ground", "engine-start": "ground", "hover-climb": "hover",
    "transition-forward": "transition-forward", "cruise": "fixed-wing",
    "transition-back": "transition-back", "hover-descent": "hover", "landed": "ground", "shutdown": "ground",
}
FLIGHT_MODE = {
    "preflight": "MANUAL", "engine-start": "MANUAL", "hover-climb": "AUTO_TAKEOFF",
    "transition-forward": "AUTO_MISSION", "cruise": "AUTO_MISSION", "transition-back": "AUTO_MISSION",
    "hover-descent": "AUTO_LAND", "landed": "AUTO_LAND", "shutdown": "MANUAL",
}
# RPM / throttle targets per phase for the single ducted fan
RPM_TARGET = {
    "preflight": 0, "engine-start": 1500, "hover-climb": 6300, "transition-forward": 6500,
    "cruise": 5100, "transition-back": 6400, "hover-descent": 6000, "landed": 1500, "shutdown": 0,
}
HOME_LAT, HOME_LON = 34.6672, -118.0873   # generic desert test range, WGS-84

# wear added per sortie at severity 1.0 (progress units); alerts trip at roughly 0.2-0.4 depending on the signal
WEAR_PER_SORTIE = 0.35

DEGRADATIONS = {
    "none": "no injected fault",
    "vibration": "ducted-fan imbalance: vibration RMS rises through the sortie",
    "egt": "engine EGT drifts upward (lean mixture / injector wear)",
    "servo": "servo3 (thrust-vane-A) current creeps up (bearing friction)",
}


@dataclass
class SortieConfig:
    sortie_id: str
    cruise_seconds: int = 480
    degradation: str = "none"          # one of DEGRADATIONS
    severity: float = 1.0              # 0..2, scales the wear added during this sortie
    baseline: float = 0.0              # wear already accumulated from earlier sorties (0..1+)
    seed: int = 1
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Sample:
    t: int                              # simulated seconds since sortie start
    ts: datetime
    phase: str
    features: Dict[str, dict]           # feature id -> flat properties (matches the Thing model)


def phase_table(cfg: SortieConfig) -> List[tuple]:
    return [(name, cfg.cruise_seconds if name == "cruise" else dur) for name, dur in PHASES]


def total_seconds(cfg: SortieConfig) -> int:
    return sum(d for _, d in phase_table(cfg))


class SortieSimulator:
    """Iterates telemetry samples; keeps per-sortie state (fuel, battery, position, servo activity)."""

    def __init__(self, cfg: SortieConfig):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.phases = phase_table(cfg)
        self.total = total_seconds(cfg)
        self.fuel_l = 18.0
        self.batt_pct = 100.0
        self.rpm = 0.0
        self.egt = 25.0
        self.cht = 25.0
        self.alt_agl = 0.0
        self.airspeed = 0.0
        self.track_angle = 0.0
        self.clip_count = 0
        self.flight_time = 0
        self.max_alt = 120.0

    # ----------------------------------------------------------------- helpers
    def phase_at(self, t: int) -> tuple:
        acc = 0
        for name, dur in self.phases:
            if t < acc + dur:
                return name, (t - acc) / max(dur, 1)
            acc += dur
        return "shutdown", 1.0

    def _degrade(self, t: int) -> float:
        """Wear progress of the injected fault: accumulated baseline plus this sortie's ramp."""
        if self.cfg.degradation == "none":
            return 0.0
        return self.cfg.baseline + (t / self.total) * self.cfg.severity * WEAR_PER_SORTIE

    @property
    def wear_added(self) -> float:
        return 0.0 if self.cfg.degradation == "none" else self.cfg.severity * WEAR_PER_SORTIE

    # ---------------------------------------------------------------- stepping
    def step(self, t: int) -> Sample:
        rng = self.rng
        phase, frac = self.phase_at(t)
        flying = phase in FLIGHT_PHASES
        dgr = self._degrade(t)
        armed = phase not in ("preflight", "shutdown")

        # engine
        target = RPM_TARGET[phase]
        self.rpm += (target - self.rpm) * 0.25 + rng.gauss(0, 25 if target else 0)
        self.rpm = max(0.0, self.rpm)
        running = self.rpm > 500
        throttle = 0.0 if not running else min(100.0, 10 + (self.rpm - 1500) / 5200 * 85)
        egt_target = 25 if not running else 420 + (self.rpm - 1500) / 5000 * 210
        if self.cfg.degradation == "egt":
            egt_target += 180 * dgr
        self.egt += (egt_target - self.egt) * 0.08 + (rng.gauss(0, 2.5) if running else 0)
        cht_target = 25 if not running else 120 + (self.rpm - 1500) / 5000 * 75
        self.cht += (cht_target - self.cht) * 0.03 + (rng.gauss(0, 0.6) if running else 0)
        fuel_flow = 0.0 if not running else 0.9 + (self.rpm / 6500) ** 2 * 5.6
        self.fuel_l = max(0.0, self.fuel_l - fuel_flow / 3600)
        oil_kpa = 0.0 if not running else 180 + self.rpm / 6500 * 210 + rng.gauss(0, 4)

        # vibration (m/s^2 RMS): scales with rpm^2, elevated in transitions
        base = 0.15 + (self.rpm / 6500) ** 2 * 0.6
        if phase.startswith("transition"):
            base *= 1.35
        if self.cfg.degradation == "vibration":
            base *= 1 + 1.6 * dgr
        vib = [abs(base * f + rng.gauss(0, 0.04)) for f in (0.72, 0.65, 1.0)]
        rms_total = math.sqrt(sum(v * v for v in vib))
        if rms_total > 2.2 and rng.random() < 0.3:
            self.clip_count += 1

        # actuation: servo deflection activity is highest in hover/transition
        activity = {"hover-climb": 1.0, "hover-descent": 1.1, "transition-forward": 1.3,
                    "transition-back": 1.3, "cruise": 0.35}.get(phase, 0.05)
        actuation = {}
        for i in range(1, 5):
            pos = (10 * activity * math.sin(t / (3.0 + i) + i) + rng.gauss(0, 0.6)) if armed else 0.0
            cur = 0.12 + (0.55 + 0.4 * abs(pos) / 10) * activity + rng.gauss(0, 0.03) if armed else 0.02
            if i == 3 and self.cfg.degradation == "servo":
                cur *= 1 + 1.2 * dgr
            actuation[f"servo{i}CurrentA"] = round(max(0.0, cur), 3)
            actuation[f"servo{i}PositionDeg"] = round(pos, 2)

        # power: 28 V bus from the engine generator when running, else from the battery
        bus_current = 5.5 + 0.9 * activity + rng.gauss(0, 0.15)
        if running:
            bus_v = 28.2 - bus_current * 0.05 + rng.gauss(0, 0.03)
            batt_cur = -0.8 if self.batt_pct < 99 else 0.1     # charging
            self.batt_pct = min(100.0, self.batt_pct + 0.004)
        else:
            bus_v = 25.6 - (100 - self.batt_pct) * 0.02 + rng.gauss(0, 0.03)
            batt_cur = bus_current
            self.batt_pct = max(0.0, self.batt_pct - bus_current / 3600 / 8 * 100)
        if phase == "engine-start" and frac < 0.3:
            batt_cur = 45.0; bus_v -= 1.4       # starter load
        batt_v = 22.0 + self.batt_pct / 100 * 3.2 - batt_cur * 0.01
        batt_temp = 24 + (100 - self.batt_pct) * 0.08 + (2 if running else 0)

        # flight state
        if phase == "hover-climb":
            self.alt_agl = self.max_alt * frac
            self.airspeed = 2 + rng.gauss(0, 0.5)
        elif phase == "transition-forward":
            self.airspeed = 4 + 20 * frac
            self.alt_agl = self.max_alt + 10 * frac
        elif phase == "cruise":
            self.airspeed = 25 + rng.gauss(0, 0.6)
            self.alt_agl = self.max_alt + 10 + 5 * math.sin(t / 60)
            self.track_angle += 2 * math.pi / self.cfg.cruise_seconds
        elif phase == "transition-back":
            self.airspeed = 24 - 20 * frac
            self.alt_agl = self.max_alt + 10 - 10 * frac
        elif phase == "hover-descent":
            self.alt_agl = self.max_alt * (1 - frac)
            self.airspeed = 2 + rng.gauss(0, 0.5)
        else:
            self.alt_agl = 0.0
            self.airspeed = 0.0
        radius = 0.012
        lat = HOME_LAT + radius * math.sin(self.track_angle) * (1 if phase == "cruise" else 0)
        lon = HOME_LON + radius * (math.cos(self.track_angle) - 1) * (1 if phase == "cruise" else 0)
        heading = (math.degrees(self.track_angle) + 90) % 360 if phase == "cruise" else 270.0
        if flying:
            self.flight_time += 1

        # navigation
        sats = 13 + int(2 * math.sin(t / 90)) + (rng.randint(-1, 1) if t % 7 == 0 else 0)
        features = {
            "engine": {
                "rpm": round(self.rpm), "egtC": round(self.egt, 1), "chtC": round(self.cht, 1),
                "fuelFlowLph": round(fuel_flow, 2), "throttlePct": round(throttle, 1),
                "oilPressureKpa": round(oil_kpa), "running": running,
            },
            "vibration": {
                "rmsX": round(vib[0], 3), "rmsY": round(vib[1], 3), "rmsZ": round(vib[2], 3),
                "rmsTotal": round(rms_total, 3), "clipCount": self.clip_count,
            },
            "actuation": actuation,
            "power": {
                "busVoltageV": round(bus_v, 2), "busCurrentA": round(bus_current, 2),
                "batteryVoltageV": round(batt_v, 2), "batteryCurrentA": round(batt_cur, 2),
                "batteryRemainingPct": round(self.batt_pct, 1), "batteryTempC": round(batt_temp, 1),
            },
            "navigation": {
                "gpsFixType": 3, "gpsSatellites": sats, "gpsHdop": round(0.7 + 0.2 * (16 - sats) / 4, 2),
                "insStatus": "ok" if armed else "aligning", "insAligned": t > 5,
            },
            "flightState": {
                "sortieId": self.cfg.sortie_id, "armed": armed, "flightMode": FLIGHT_MODE[phase],
                "vtolState": VTOL_STATE[phase], "lat": round(lat, 6), "lon": round(lon, 6),
                "altMslM": round(720 + self.alt_agl, 1), "altAglM": round(self.alt_agl, 1),
                "airspeedMps": round(max(0.0, self.airspeed), 2),
                "groundspeedMps": round(max(0.0, self.airspeed - 1.5) if flying else 0.0, 2),
                "headingDeg": round(heading, 1), "flightTimeS": self.flight_time,
                "fuelRemainingL": round(self.fuel_l, 2),
            },
        }
        ts = self.cfg.start_time + timedelta(seconds=t)
        for f in features.values():
            f["ts"] = ts.isoformat(timespec="seconds").replace("+00:00", "Z")
        return Sample(t=t, ts=ts, phase=phase, features=features)

    def __iter__(self) -> Iterator[Sample]:
        for t in range(self.total):
            yield self.step(t)

    @property
    def flight_hours(self) -> float:
        return self.flight_time / 3600.0


def next_sortie_id(date: datetime, seq: int, tail: str = TAIL) -> str:
    return f"{date:%Y%m%d}-{tail}-{seq:02d}"
