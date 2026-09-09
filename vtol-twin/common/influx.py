"""InfluxDB 2.x helpers: feature dicts -> line-protocol points, thin sink with sync or batched writes.

Schema (see docs/data-dictionary.md): measurement = feature id, tags tail / sortie / source,
fields = the feature's properties (numbers, bools, strings). The `ts` property becomes the point time.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from influxdb_client import InfluxDBClient, Point, WriteOptions, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from .logging_setup import log

logger = logging.getLogger("common.influx")
SKIP_FIELDS = {"ts", "tail", "sortieId", "source"}


def parse_ts(value: Any) -> Optional[datetime]:
    """ISO-8601 string (Z or offset), epoch seconds/milliseconds, or datetime -> aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        v = float(value)
        if v > 1e12:          # milliseconds
            v /= 1000.0
        return datetime.fromtimestamp(v, tz=timezone.utc)
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def points_from_features(tail: str, sortie: Optional[str], source: str, features: Dict[str, Dict[str, Any]],
                         default_ts: Optional[datetime] = None) -> List[Point]:
    points: List[Point] = []
    for feature, props in features.items():
        if not isinstance(props, dict):
            continue
        ts = parse_ts(props.get("ts")) or default_ts or datetime.now(timezone.utc)
        p = Point(feature).tag("tail", tail).tag("sortie", sortie or "none").tag("source", source).time(ts, WritePrecision.MS)
        n = 0
        for k, v in props.items():
            if k in SKIP_FIELDS or v is None or isinstance(v, (dict, list)):
                continue
            if isinstance(v, bool):
                p.field(k, v)
            elif isinstance(v, (int, float)):
                p.field(k, float(v))
            else:
                p.field(k, str(v))
            n += 1
        if n:
            points.append(p)
    return points


class InfluxSink:
    """Writes points to one bucket. batched=True uses the background batching write API (for streams)."""

    def __init__(self, url: str, token: str, org: str, bucket: str, batched: bool = False):
        self.bucket, self.org = bucket, org
        self._client = InfluxDBClient(url=url, token=token, org=org, timeout=20_000)
        opts = WriteOptions(batch_size=500, flush_interval=1_000, jitter_interval=200, retry_interval=2_000,
                            max_retries=5) if batched else SYNCHRONOUS
        self._write = self._client.write_api(write_options=opts)
        self.written = 0

    def write(self, points: Iterable[Point]) -> int:
        pts = list(points)
        if pts:
            self._write.write(bucket=self.bucket, org=self.org, record=pts)
            self.written += len(pts)
        return len(pts)

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception as exc:  # noqa: BLE001
            log(logger, "influx ping failed", level=logging.WARNING, error=str(exc))
            return False

    def query(self, flux: str):
        return self._client.query_api().query(flux, org=self.org)

    def close(self) -> None:
        try:
            self._write.close()
        finally:
            self._client.close()
