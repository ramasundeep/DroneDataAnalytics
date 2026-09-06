"""Batch ingester: PX4 .ulg -> InfluxDB (flight_telemetry) + lifeCounters on the Thing.

    python -m bridge.ulog_ingest data/samples/*.ulg            # uses .env / environment
    python -m bridge.ulog_ingest --dry-run data/samples/*.ulg  # parse + summarise only
"""
from __future__ import annotations

import argparse
import bisect
import glob
import hashlib
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from influxdb_client import Point, WritePrecision
from pyulog import ULog

from common.ditto_client import DittoClient
from common.influx import InfluxSink, points_from_features
from common.logging_setup import configure, log

from . import mapping
from .lifecounters import accrue_on_thing

logger = logging.getLogger("bridge.ulog")


@dataclass
class SortieSummary:
    file: str
    tail: str
    sortie_id: str
    start_utc: datetime
    end_utc: datetime
    flight_hours: float
    landings: int
    samples: int
    points: int = 0
    stats: Dict[str, float] = field(default_factory=dict)
    degradation: Optional[str] = None


class ULogSortie:
    """Parsed log + derived sortie metadata (tail, id, absolute time base)."""

    def __init__(self, path: str, tail: Optional[str] = None, sortie_id: Optional[str] = None):
        self.path = path
        self.ulog = ULog(path)
        info = self.ulog.msg_info_dict
        self.tail = tail or str(info.get("tail_number") or os.getenv("TAIL_NUMBER", "VTOL-1"))
        self.degradation = info.get("degradation")
        self.utc_offset_us = self._utc_offset_us()
        self.sortie_id = sortie_id or str(info.get("sortie_id") or self._derived_sortie_id())

    def _dataset(self, name: str):
        try:
            return self.ulog.get_dataset(name)
        except (KeyError, IndexError):
            return None

    def _utc_offset_us(self) -> int:
        """utc_us = timestamp_us + offset. Prefer GPS UTC, then an info key, then the file mtime."""
        gps = self._dataset("sensor_gps")
        if gps is not None and "time_utc_usec" in gps.data:
            for t, utc in zip(gps.data["timestamp"], gps.data["time_utc_usec"]):
                if int(utc) > 0:
                    return int(utc) - int(t)
        info = self.ulog.msg_info_dict
        if "time_start_utc_usec" in info:
            return int(info["time_start_utc_usec"]) - int(self.ulog.start_timestamp)
        mtime = Path(self.path).stat().st_mtime
        return int(mtime * 1e6) - int(self.ulog.last_timestamp)

    def to_utc(self, t_us: int) -> datetime:
        return datetime.fromtimestamp((int(t_us) + self.utc_offset_us) / 1e6, tz=timezone.utc)

    def _derived_sortie_id(self) -> str:
        start = self.to_utc(self.ulog.start_timestamp)
        digest = hashlib.sha1(Path(self.path).name.encode()).hexdigest()[:4]
        return f"{start:%Y%m%d}-{self.tail}-{digest}"

    def flight_time(self) -> tuple[float, int]:
        """(flight hours while armed, landings = armed->disarmed transitions, at least 1 if ever armed)."""
        vs = self._dataset("vehicle_status")
        if vs is None:
            return 0.0, 0
        ts, arming = vs.data["timestamp"], vs.data["arming_state"]
        armed_us, landings, prev_armed, prev_t = 0, 0, False, int(ts[0])
        for t, a in zip(ts, arming):
            armed = int(a) == mapping.ARMING_ARMED
            if prev_armed:
                armed_us += int(t) - prev_t
            if prev_armed and not armed:
                landings += 1
            prev_armed, prev_t = armed, int(t)
        if armed_us and landings == 0:
            landings = 1
        return armed_us / 3.6e9, landings

    def _landed_timeline(self):
        ds = self._dataset("vehicle_land_detected")
        if ds is None:
            return [], []
        return [int(t) for t in ds.data["timestamp"]], [bool(v) for v in ds.data["landed"]]

    def samples(self):
        """Yield (utc datetime, {feature: props}) for every row of every mapped topic."""
        land_t, land_v = self._landed_timeline()

        def landed_at(t_us: int) -> bool:
            i = bisect.bisect_right(land_t, int(t_us)) - 1
            return land_v[i] if i >= 0 else False

        for topic in mapping.TOPICS:
            ds = self._dataset(topic)
            if ds is None:
                continue
            names = [n for n in ds.data.keys()]
            n = len(ds.data["timestamp"])
            for i in range(n):
                row = _row(ds.data, names, i)
                feats = mapping.features_from_topic(topic, row, landed=landed_at(row["timestamp"]))
                if feats:
                    yield self.to_utc(row["timestamp"]), feats


def _row(data: Dict[str, Any], names: List[str], i: int) -> Dict[str, Any]:
    """pyulog flattens arrays to name[0], name[1], ...; rebuild lists for the mapper."""
    row: Dict[str, Any] = {}
    arrays: Dict[str, Dict[int, Any]] = {}
    for name in names:
        v = data[name][i]
        v = v.item() if hasattr(v, "item") else v
        if name.endswith("]"):
            base, idx = name[:-1].split("[")
            arrays.setdefault(base, {})[int(idx)] = v
        else:
            row[name] = v
    for base, items in arrays.items():
        row[base] = [items[k] for k in sorted(items)]
    return row


def summarise(sortie: ULogSortie) -> SortieSummary:
    hours, landings = sortie.flight_time()
    stats: Dict[str, float] = {}
    n = 0

    def track(key: str, v: float, kind: str = "max") -> None:
        if kind == "max":
            stats[key] = max(stats.get(key, v), v)
        else:
            stats[key] = stats.get(key, 0.0) + v
            stats[key + "_n"] = stats.get(key + "_n", 0) + 1

    for _, feats in sortie.samples():
        n += 1
        e = feats.get("engine")
        if e and e.get("running"):
            track("egt_max_c", e["egtC"]); track("egt_mean_c", e["egtC"], "mean"); track("rpm_max", e["rpm"])
        v = feats.get("vibration")
        if v and "rmsTotal" in v:
            track("vib_rms_max", v["rmsTotal"]); track("vib_rms_mean", v["rmsTotal"], "mean")
        a = feats.get("actuation")
        if a and "servo1CurrentA" in a:
            for i in range(1, 5):
                track(f"servo{i}_current_max_a", a[f"servo{i}CurrentA"])
    for key in [k for k in stats if k.endswith("_n")]:
        base = key[:-2]
        stats[base] = round(stats[base] / stats.pop(key), 3)
    stats = {k: round(float(v), 3) for k, v in stats.items()}
    return SortieSummary(file=sortie.path, tail=sortie.tail, sortie_id=sortie.sortie_id,
                         start_utc=sortie.to_utc(sortie.ulog.start_timestamp), end_utc=sortie.to_utc(sortie.ulog.last_timestamp),
                         flight_hours=round(hours, 4), landings=landings, samples=n, stats=stats,
                         degradation=sortie.degradation)


def summary_points(s: SortieSummary, counters: Optional[Dict[str, Any]], components: Dict[str, Any]) -> List[Point]:
    """sortie_summary (one point per sortie) and life_counters (one point per component) measurements."""
    pts = [Point("sortie_summary").tag("tail", s.tail).tag("sortie", s.sortie_id).tag("source", "ulog")
           .field("flight_hours", float(s.flight_hours)).field("landings", float(s.landings))
           .field("samples", float(s.samples)).field("degradation", s.degradation or "none")
           .time(s.end_utc, WritePrecision.MS)]
    for k, v in s.stats.items():
        pts[0].field(k, float(v))
    if counters:
        for cid, c in components.items():
            cnt = counters.get(cid) or {}
            hours = float(cnt.get("hours", c.get("hoursConsumed", 0.0)))
            cycles = float(cnt.get("cycles", c.get("cyclesConsumed", 0)))
            limit_h, limit_c = float(c["lifeLimitHours"]), float(c["lifeLimitCycles"])
            pts.append(Point("life_counters").tag("tail", s.tail).tag("component", cid).tag("sortie", s.sortie_id)
                       .field("hours", hours).field("cycles", cycles).field("life_limit_hours", limit_h)
                       .field("life_limit_cycles", limit_c).field("hours_remaining", max(0.0, limit_h - hours))
                       .field("hours_used_pct", round(100.0 * hours / limit_h, 2))
                       .field("cycles_used_pct", round(100.0 * cycles / limit_c, 2))
                       .time(s.end_utc, WritePrecision.MS))
    return pts


def ingest_file(path: str, sink: Optional[InfluxSink], ditto: Optional[DittoClient], tail: Optional[str] = None,
                sortie_id: Optional[str] = None, source: str = "ulog") -> SortieSummary:
    sortie = ULogSortie(path, tail=tail, sortie_id=sortie_id)
    summary = summarise(sortie)
    if sink is not None:
        batch: List[Point] = []
        for ts, feats in sortie.samples():
            batch.extend(points_from_features(sortie.tail, sortie.sortie_id, source, feats, default_ts=ts))
            if len(batch) >= 5000:
                summary.points += sink.write(batch); batch = []
        summary.points += sink.write(batch)
    counters, components = None, {}
    if ditto is not None:
        patch = accrue_on_thing(ditto, sortie.sortie_id, summary.flight_hours, summary.landings)
        counters = ditto.get_feature_properties("lifeCounters")
        components = ditto.get_attributes().get("components", {})
        log(logger, "life counters", sortie=sortie.sortie_id, updated=patch is not None,
            engine_hours=counters.get("engine", {}).get("hours"))
    if sink is not None:
        summary.points += sink.write(summary_points(summary, counters, components))
    log(logger, "ingested", file=Path(path).name, sortie=summary.sortie_id, tail=summary.tail,
        flight_hours=summary.flight_hours, landings=summary.landings, samples=summary.samples,
        points=summary.points, degradation=summary.degradation, **summary.stats)
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest PX4 .ulg logs into InfluxDB and advance the Thing's life counters")
    ap.add_argument("files", nargs="+", help=".ulg files or globs")
    ap.add_argument("--dry-run", action="store_true", help="parse and summarise only")
    ap.add_argument("--no-ditto", action="store_true", help="write InfluxDB only, do not touch the Thing")
    ap.add_argument("--tail", help="override tail number for logs without one")
    ap.add_argument("--sortie", help="override sortie id (single file only)")
    ap.add_argument("--source", default="ulog", help="InfluxDB source tag")
    args = ap.parse_args(argv)
    configure(os.getenv("LOG_LEVEL", "INFO"), stream=sys.stderr)   # keep stdout for the summary table
    files = sorted({f for pat in args.files for f in glob.glob(pat)})
    if not files:
        print("no files matched", file=sys.stderr)
        return 2
    if args.sortie and len(files) > 1:
        print("--sortie applies to a single file", file=sys.stderr)
        return 2
    sink = ditto = None
    if not args.dry_run:
        sink = InfluxSink(os.getenv("INFLUXDB_URL", f"http://localhost:{os.getenv('INFLUXDB_PORT', '8086')}"),
                          os.environ["INFLUXDB_TOKEN"], os.getenv("INFLUXDB_ORG", "vtol"),
                          os.getenv("INFLUXDB_BUCKET", "flight_telemetry"))
        if not sink.ping():
            print("InfluxDB not reachable", file=sys.stderr)
            return 1
        if not args.no_ditto:
            ditto = DittoClient(os.getenv("DITTO_URL", f"http://localhost:{os.getenv('DITTO_EXTERNAL_PORT', '8080')}"),
                                os.getenv("DITTO_USER", "ditto"), os.environ["DITTO_PASSWORD"],
                                os.getenv("THING_ID", "vtol.fleet:VTOL-1"))
    total_h = 0.0
    print(f"{'file':34} {'sortie':22} {'hours':>6} {'ldg':>3} {'EGTmax':>7} {'vibMax':>7} {'srv3max':>8} {'points':>7}  fault")
    for f in files:
        s = ingest_file(f, sink, ditto, tail=args.tail, sortie_id=args.sortie, source=args.source)
        total_h += s.flight_hours
        print(f"{Path(f).name:34} {s.sortie_id:22} {s.flight_hours:6.3f} {s.landings:3d} {s.stats.get('egt_max_c', 0):7.1f} "
              f"{s.stats.get('vib_rms_max', 0):7.3f} {s.stats.get('servo3_current_max_a', 0):8.3f} {s.points:7d}  {s.degradation or '-'}")
    print(f"{len(files)} sorties, {total_h:.3f} flight hours" + (" (dry run)" if args.dry_run else ""))
    if ditto is not None:
        c = ditto.get_feature_properties("lifeCounters")
        print(f"Thing lifeCounters: engine {c.get('engine', {}).get('hours')} h / airframe {c.get('airframe', {}).get('hours')} h, "
              f"last sortie {c.get('lastSortieId')}")
    if sink:
        sink.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
