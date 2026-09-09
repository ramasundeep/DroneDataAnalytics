"""Sortie sources: offline .ulg files (bridge.ulog_ingest) or InfluxDB (flight_telemetry bucket).

Both yield SortieData in chronological order so the rolling baseline sees sorties as they happened.
"""
from __future__ import annotations

import glob
import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, Iterator, List, Optional

import pandas as pd

from bridge.ulog_ingest import ULogSortie
from common.influx import InfluxSink
from common.logging_setup import log

from .features import SortieData

logger = logging.getLogger("analytics.sources")
FEATURES = ("engine", "vibration", "actuation", "power", "flightState")


def _frames_from_samples(samples: Iterable) -> Dict[str, pd.DataFrame]:
    rows: Dict[str, Dict[datetime, dict]] = {f: {} for f in FEATURES}
    for ts, feats in samples:
        for fid, props in feats.items():
            if fid in rows:
                rows[fid].setdefault(ts, {}).update({k: v for k, v in props.items() if k != "ts"})
    frames = {}
    for fid, by_ts in rows.items():
        if by_ts:
            df = pd.DataFrame.from_dict(by_ts, orient="index").sort_index()
            df.index = pd.DatetimeIndex(df.index)
            frames[fid] = df
    return frames


class UlogSource:
    def __init__(self, patterns: List[str], tail: Optional[str] = None):
        self.files = sorted({f for p in patterns for f in glob.glob(p)})
        self.tail = tail

    def __iter__(self) -> Iterator[SortieData]:
        items = []
        for f in self.files:
            s = ULogSortie(f, tail=self.tail)
            hours, _ = s.flight_time()
            items.append((s.to_utc(s.ulog.last_timestamp), s, hours))
        for end, s, hours in sorted(items, key=lambda x: x[0]):
            yield SortieData(sortie_id=s.sortie_id, tail=s.tail, frames=_frames_from_samples(s.samples()),
                             flight_hours=hours, end_utc=end, degradation=s.degradation)


class InfluxSource:
    """Reads sortie_summary for the sortie list, then each sortie's telemetry, from the bucket."""

    def __init__(self, sink: InfluxSink, tail: str, lookback: str = "-2y", max_sorties: int = 200):
        self.sink, self.tail, self.lookback, self.max_sorties = sink, tail, lookback, max_sorties

    def list_sorties(self) -> List[dict]:
        flux = (f'from(bucket: "{self.sink.bucket}") |> range(start: {self.lookback})\n'
                f'  |> filter(fn: (r) => r._measurement == "sortie_summary" and r.tail == "{self.tail}")\n'
                f'  |> filter(fn: (r) => r._field == "flight_hours" or r._field == "degradation")\n'
                f'  |> pivot(rowKey: ["_time", "sortie"], columnKey: ["_field"], valueColumn: "_value")\n'
                f'  |> keep(columns: ["_time", "sortie", "flight_hours", "degradation"])\n'
                f'  |> sort(columns: ["_time"])')
        out = []
        for table in self.sink.query(flux):
            for rec in table.records:
                out.append({"sortie": rec.values["sortie"], "end": rec.get_time(),
                            "flight_hours": float(rec.values.get("flight_hours") or 0.0),
                            "degradation": rec.values.get("degradation")})
        seen, uniq = set(), []
        for s in out:
            if s["sortie"] not in seen:
                seen.add(s["sortie"]); uniq.append(s)
        return uniq[-self.max_sorties:]

    def frames_for(self, sortie: str) -> Dict[str, pd.DataFrame]:
        frames = {}
        for fid in FEATURES:
            flux = (f'from(bucket: "{self.sink.bucket}") |> range(start: {self.lookback})\n'
                    f'  |> filter(fn: (r) => r._measurement == "{fid}" and r.tail == "{self.tail}" and r.sortie == "{sortie}")\n'
                    f'  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")\n'
                    f'  |> drop(columns: ["_start", "_stop", "_measurement", "tail", "sortie", "source"])\n'
                    f'  |> sort(columns: ["_time"])')
            recs = [rec.values for table in self.sink.query(flux) for rec in table.records]
            if recs:
                df = pd.DataFrame(recs)
                df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("_time"), utc=True))
                frames[fid] = df.drop(columns=[c for c in ("result", "table") if c in df], errors="ignore").sort_index()
        return frames

    def __iter__(self) -> Iterator[SortieData]:
        for s in self.list_sorties():
            frames = self.frames_for(s["sortie"])
            if not frames:
                log(logger, "sortie without telemetry, skipped", sortie=s["sortie"])
                continue
            yield SortieData(sortie_id=s["sortie"], tail=self.tail, frames=frames, flight_hours=s["flight_hours"],
                             end_utc=s["end"] if s["end"].tzinfo else s["end"].replace(tzinfo=timezone.utc),
                             degradation=None if s["degradation"] in (None, "none") else s["degradation"])
