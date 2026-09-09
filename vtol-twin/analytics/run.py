"""Offline analytics CLI.

    python -m analytics.run "data/samples/*.ulg"                 # score the sample set, print tables
    python -m analytics.run --source influx --tail VTOL-1        # read the live bucket instead
    python -m analytics.run --write "data/samples/*.ulg"         # also write health to Ditto + InfluxDB
    python -m analytics.run --json out.json "data/samples/*.ulg"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from common.ditto_client import DittoClient
from common.influx import InfluxSink
from common.logging_setup import configure

from .engine import Analyzer, ditto_patch, influx_points
from .sources import InfluxSource, UlogSource

ROOT = Path(__file__).resolve().parents[1]


def model_counters_and_components():
    thing = json.loads((ROOT / "ditto" / "thing-VTOL-1.json").read_text())
    return thing["features"]["lifeCounters"]["properties"], thing["attributes"]["components"]


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Run anomaly detection + RUL over sorties")
    ap.add_argument("files", nargs="*", help=".ulg files/globs (source=ulog)")
    ap.add_argument("--source", choices=["ulog", "influx"], default="ulog")
    ap.add_argument("--tail", default=os.getenv("TAIL_NUMBER", "VTOL-1"))
    ap.add_argument("--write", action="store_true", help="write results to Ditto and InfluxDB")
    ap.add_argument("--json", help="write the full result as JSON to this path")
    args = ap.parse_args(argv)
    configure(os.getenv("LOG_LEVEL", "WARNING"), stream=sys.stderr)

    sink = ditto = None
    if args.source == "influx" or args.write:
        sink = InfluxSink(os.getenv("INFLUXDB_URL", f"http://localhost:{os.getenv('INFLUXDB_PORT', '8086')}"),
                          os.environ["INFLUXDB_TOKEN"], os.getenv("INFLUXDB_ORG", "vtol"), os.getenv("INFLUXDB_BUCKET", "flight_telemetry"))
    if args.write:
        ditto = DittoClient(os.getenv("DITTO_URL", f"http://localhost:{os.getenv('DITTO_EXTERNAL_PORT', '8080')}"),
                            os.getenv("DITTO_USER", "ditto"), os.environ["DITTO_PASSWORD"], os.getenv("THING_ID", "vtol.fleet:VTOL-1"))
        counters = ditto.get_feature_properties("lifeCounters")
        components = ditto.get_attributes()["components"]
    else:
        counters, components = model_counters_and_components()

    if args.source == "ulog":
        if not args.files:
            print("give .ulg files or globs", file=sys.stderr); return 2
        source = UlogSource(args.files, tail=args.tail)
        starting = None if args.write else float(counters["airframe"]["hours"])   # model file = hours before the samples
    else:
        source = InfluxSource(sink, args.tail)
        starting = None

    run = Analyzer().run(source, counters, components, starting_hours=starting)

    print(f"{'sortie':22} {'hours':>6} {'cum h':>7}  {'engine':>15} {'actuation':>15} {'power':>15}  flag  fault")
    for s in run.sorties:
        cells = []
        for g in ("engine", "actuation", "power"):
            r = s.groups[g]
            tag = "warm" if r.warmup else f"z{r.zmax:>4.1f}/i{r.if_z:>4.1f}"
            cells.append(f"{r.score:4.2f} {tag:>10}")
        print(f"{s.features.sortie_id:22} {s.features.flight_hours:6.3f} {s.cumulative_hours:7.2f}  " + " ".join(f"{c:>15}" for c in cells)
              + f"  {'YES' if s.flagged else '-':>4}  {s.features.degradation or '-'}")
    print()
    print(f"{'component':14} {'health':>6} {'RUL h':>8} {'life h':>8} {'trend h':>8}  {'alert':9} {'anom':>5}  indicator")
    for c, h in run.health.items():
        ev = h.evidence
        ind = f"{ev.get('indicator', '')} {ev.get('level', '')} / {ev.get('threshold', '')}" if ev.get("indicator") else ""
        print(f"{c:14} {h.health_score:6.1f} {h.rul_hours:8.1f} {h.rul_life_hours:8.1f} "
              f"{('%8.1f' % h.rul_trend_hours) if h.rul_trend_hours is not None else '       -'}  {h.alert_level:9} {h.anomaly_score:5.2f}  {ind}")
    print(f"\nworst alert: {run.worst_alert}; flagged sorties: {', '.join(run.summary()['flaggedSorties']) or 'none'}")

    if args.json:
        Path(args.json).write_text(json.dumps(run.summary(), indent=2, default=str))
    if args.write:
        ditto.merge_features(ditto_patch(run))
        n = sink.write(influx_points(run))
        print(f"wrote health to Thing and {n} points to InfluxDB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
