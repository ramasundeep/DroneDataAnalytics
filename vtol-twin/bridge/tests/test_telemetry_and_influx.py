"""MQTT payload parsing (mirror of the JS mapper), Influx point building, and the ingester handler."""
import json
from datetime import datetime, timezone

from bridge.mqtt_ingest import Ingester
from bridge.telemetry import parse_telemetry, parse_topic
from common.influx import parse_ts, points_from_features


def test_parse_topic_shapes():
    assert parse_topic("vtol/VTOL-1/telemetry") == ("VTOL-1", None)
    assert parse_topic("vtol/VTOL-1/telemetry/engine") == ("VTOL-1", "engine")
    assert parse_topic("vtol/VTOL-1/events") is None
    assert parse_topic("vtol/VTOL-1/telemetry/engine/rpm") is None


def test_parse_telemetry_single_and_multi():
    tail, feats, meta = parse_telemetry("vtol/VTOL-1/telemetry/engine", json.dumps({"ts": "T", "rpm": 5000, "tail": "X"}))
    assert tail == "VTOL-1" and feats == {"engine": {"ts": "T", "rpm": 5000}} and meta == {"tail": "X"}
    tail, feats, meta = parse_telemetry("vtol/VTOL-1/telemetry", json.dumps(
        {"ts": "T1", "sortieId": "S9", "power": {"busVoltageV": 28}, "vibration": {"ts": "T2", "rmsX": 0.1}, "scalar": 1}))
    assert feats == {"power": {"busVoltageV": 28, "ts": "T1"}, "vibration": {"ts": "T2", "rmsX": 0.1}}
    assert meta["sortieId"] == "S9"
    assert parse_telemetry("vtol/VTOL-1/telemetry", "[1]") is None
    assert parse_telemetry("vtol/VTOL-1/telemetry", "{not json") is None
    assert parse_telemetry("vtol/VTOL-1/telemetry", json.dumps({"ts": "T", "rpm": 1})) is None
    assert parse_telemetry("other/topic", json.dumps({"tail": "VTOL-1", "feature": "engine", "rpm": 1}))[1] == {"engine": {"rpm": 1}}


def test_parse_ts_variants():
    assert parse_ts("2026-09-05T10:00:00Z") == datetime(2026, 9, 5, 10, tzinfo=timezone.utc)
    assert parse_ts(1_800_000_000) == datetime.fromtimestamp(1_800_000_000, tz=timezone.utc)
    assert parse_ts(1_800_000_000_000) == datetime.fromtimestamp(1_800_000_000, tz=timezone.utc)
    assert parse_ts("garbage") is None and parse_ts(None) is None


def test_points_carry_tags_fields_and_time():
    pts = points_from_features("VTOL-1", "S1", "ulog", {
        "engine": {"ts": "2026-09-05T10:00:00Z", "rpm": 5000, "running": True, "note": "x", "nested": {"a": 1}, "nothing": None},
        "empty": {"ts": "2026-09-05T10:00:00Z"},
    })
    assert len(pts) == 1
    lp = pts[0].to_line_protocol()
    assert lp.startswith('engine,sortie=S1,source=ulog,tail=VTOL-1 ')
    assert 'rpm=5000' in lp and 'running=true' in lp and 'note="x"' in lp and "nested" not in lp and "nothing" not in lp
    assert lp.endswith(" 1788602400000")


class FakeSink:
    def __init__(self):
        self.points = []

    def write(self, points):
        pts = list(points)
        self.points.extend(pts)
        return len(pts)


def test_ingester_tags_sortie_from_flight_state_and_counts():
    sink = FakeSink()
    ing = Ingester(sink, default_source="live")
    assert ing.handle("vtol/VTOL-1/telemetry/engine", b'{"rpm": 1000}') == 1
    assert ",sortie=none," in sink.points[-1].to_line_protocol()
    ing.handle("vtol/VTOL-1/telemetry", json.dumps({"ts": "2026-09-05T10:00:00Z", "flightState": {"sortieId": "S7", "armed": True},
                                                    "power": {"busVoltageV": 28.0}}).encode())
    assert all(",sortie=S7," in p.to_line_protocol() for p in sink.points[-2:])
    ing.handle("vtol/VTOL-1/telemetry/vibration", b'{"rmsTotal": 0.5, "source": "sitl"}')
    assert ",sortie=S7,source=sitl," in sink.points[-1].to_line_protocol()
    assert ing.handle("vtol/VTOL-1/telemetry/engine", b"nope") == 0
    st = ing.status()
    assert st["received"] == 4 and st["pointsWritten"] == 4 and st["dropped"] == 1 and st["sortieByTail"] == {"VTOL-1": "S7"}
