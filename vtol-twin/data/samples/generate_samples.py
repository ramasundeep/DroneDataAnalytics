"""Generate the synthetic sortie set: 20 PX4-style .ulg logs for VTOL-1 plus manifest.json.

    python data/samples/generate_samples.py            # writes into data/samples/
    python data/samples/generate_samples.py --out DIR --count 20

Sorties are chronological (one per day). Three degradation trends are injected:
  * EGT drift on sortie 07 (engine, single sharp event)
  * vibration rise building over sorties 12, 13, 14 (ducted fan)
  * servo3 current creep on sortie 18
Everything else is nominal. Files are deterministic for a given seed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bridge import mapping  # noqa: E402
from bridge.ulog_writer import Topic, ULogWriter  # noqa: E402
from demo import simulator as sim  # noqa: E402

TAIL = "VTOL-1"
# sortie index (1-based) -> (degradation, severity, baseline wear)
DEGRADED = {
    7: ("egt", 1.5, 0.35),
    12: ("vibration", 0.5, 0.20), 13: ("vibration", 0.5, 0.40), 14: ("vibration", 0.5, 0.60),
    18: ("servo", 1.2, 0.30),
}


def build(out: Path, count: int, first_day: datetime, cruise: int, seed0: int) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i in range(1, count + 1):
        degr, sev, base = DEGRADED.get(i, ("none", 0.0, 0.0))
        start = first_day + timedelta(days=i - 1, hours=(i * 7) % 9, minutes=(i * 13) % 60)
        sortie_id = sim.next_sortie_id(start, 1, TAIL)
        cfg = sim.SortieConfig(sortie_id=sortie_id, cruise_seconds=cruise + (i % 4) * 60, degradation=degr,
                               severity=sev, baseline=base, seed=seed0 + i, start_time=start)
        s = sim.SortieSimulator(cfg)
        fname = f"{i:02d}_{sortie_id}.ulg"
        boot_us = 30_000_000                      # log starts 30 s after boot, like a real FCU
        start_utc_us = int(start.timestamp() * 1e6)
        info = {"sys_name": "PX4", "ver_hw": "VTOL-1-FCU", "tail_number": TAIL, "sortie_id": sortie_id,
                "degradation": degr, "time_start_utc_usec": start_utc_us}
        params = {"VT_TYPE": 0, "MAV_SYS_ID": 1}   # VT_TYPE 0 = tailsitter
        with ULogWriter(str(out / fname), boot_us, info=info, params=params) as w:
            for name, fields in mapping.TOPICS.items():
                w.add_topic(Topic(name, fields))
            for sample in s:
                t_us = boot_us + sample.t * 1_000_000
                rows = mapping.topic_rows_from_features(sample.features, t_us, start_utc_us + sample.t * 1_000_000)
                for name, row in rows.items():
                    w.write(name, row)
        manifest.append({"index": i, "file": fname, "sortieId": sortie_id, "tail": TAIL, "startUtc": start.isoformat(),
                         "airborneHours": round(s.flight_hours, 4), "degradation": degr, "severity": sev,
                         "baselineWear": base, "seed": cfg.seed, "simSeconds": s.total})
    (out / "manifest.json").write_text(json.dumps({"tail": TAIL, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                   "sorties": manifest}, indent=2))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).parent))
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--first-day", default="2026-08-01T14:00:00+00:00")
    ap.add_argument("--cruise", type=int, default=300, help="base cruise seconds (varies +0..180 s per sortie)")
    ap.add_argument("--seed", type=int, default=100)
    a = ap.parse_args()
    m = build(Path(a.out), a.count, datetime.fromisoformat(a.first_day), a.cruise, a.seed)
    total = sum(x["airborneHours"] for x in m)
    for x in m:
        print(f"{x['file']:36} {x['airborneHours']:.3f} h  {x['degradation']}")
    print(f"{len(m)} sorties, {total:.2f} airborne hours (armed/block time is what the ingester books) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
