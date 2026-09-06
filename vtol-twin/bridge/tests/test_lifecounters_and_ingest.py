"""Life-counter accrual (pure + against a fake Ditto) and the full ingest_file path with fakes."""
import json
from pathlib import Path

import httpx
import pytest

from bridge.lifecounters import accrue_on_thing, accrue_sortie
from bridge.ulog_ingest import ingest_file
from common.ditto_client import DittoClient

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = sorted((ROOT / "data" / "samples").glob("*.ulg"))


class FakeDitto:
    """Enough of Ditto's HTTP API 2 to serve GET attributes / feature properties and PATCH merges."""

    def __init__(self):
        self.thing = json.loads((ROOT / "ditto" / "thing-VTOL-1.json").read_text())
        self.merges = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith("/attributes"):
            return httpx.Response(200, json=self.thing["attributes"])
        if request.method == "GET" and "/features/" in path and path.endswith("/properties"):
            fid = path.split("/features/")[1].split("/")[0]
            f = self.thing["features"].get(fid)
            return httpx.Response(200, json=f["properties"]) if f else httpx.Response(404)
        if request.method == "PATCH" and path.endswith("/features"):
            body = json.loads(request.content)
            self.merges.append(body)
            for fid, f in body.items():
                props = self.thing["features"].setdefault(fid, {"properties": {}})["properties"]
                for k, v in f["properties"].items():
                    if v is None:
                        props.pop(k, None)
                    elif isinstance(v, dict) and isinstance(props.get(k), dict):
                        props[k].update(v)
                    else:
                        props[k] = v
            return httpx.Response(204)
        return httpx.Response(404)

    def client(self) -> DittoClient:
        return DittoClient("http://ditto", "ditto", "ditto", "vtol.fleet:VTOL-1", transport=httpx.MockTransport(self.handler))


def test_accrue_sortie_pure_and_idempotent():
    counters = {"engine": {"hours": 10.0, "cycles": 5}, "airframe": {"hours": 10.0, "cycles": 8}, "lastSortieId": None}
    patch = accrue_sortie(counters, ["engine", "battery"], "S1", 0.5, landings=2, updated_at="T")
    assert patch["engine"] == {"hours": 10.5, "cycles": 6}
    assert patch["battery"] == {"hours": 0.5, "cycles": 1}
    assert patch["airframe"] == {"hours": 10.5, "cycles": 10}
    assert patch["lastSortieId"] == "S1" and patch["ingestedSorties"] == ["S1"] and patch["updatedAt"] == "T"
    counters.update(patch)
    assert accrue_sortie(counters, ["engine"], "S1", 0.5) is None
    assert accrue_sortie(counters, ["engine"], "S2", 0.25)["engine"]["hours"] == 10.75


def test_accrue_on_thing_updates_all_components_once():
    fake = FakeDitto()
    d = fake.client()
    before = fake.thing["features"]["lifeCounters"]["properties"]["engine"]["hours"]
    assert accrue_on_thing(d, "S1", 0.4) is not None
    assert accrue_on_thing(d, "S1", 0.4) is None
    props = fake.thing["features"]["lifeCounters"]["properties"]
    assert props["engine"]["hours"] == pytest.approx(before + 0.4)
    for cid in fake.thing["attributes"]["components"]:
        assert props[cid]["cycles"] == fake.thing["attributes"]["components"][cid]["cyclesConsumed"] + 1
    assert props["lastSortieId"] == "S1" and len(fake.merges) == 1


class FakeSink:
    def __init__(self):
        self.points = []
        self.written = 0

    def write(self, points):
        pts = list(points)
        self.points.extend(pts)
        self.written += len(pts)
        return len(pts)


@pytest.mark.skipif(not SAMPLES, reason="run data/samples/generate_samples.py first")
def test_ingest_sample_file_end_to_end_with_fakes():
    fake = FakeDitto()
    sink = FakeSink()
    path = str(SAMPLES[6])   # sortie 07: EGT drift
    summary = ingest_file(path, sink, fake.client())
    assert summary.degradation == "egt" and summary.stats["egt_max_c"] > 680
    assert summary.points == len(sink.points) > 1000
    measurements = {p._name for p in sink.points}
    assert {"engine", "vibration", "actuation", "power", "navigation", "flightState", "sortie_summary", "life_counters"} <= measurements
    lp = next(p for p in sink.points if p._name == "sortie_summary").to_line_protocol()
    assert f"sortie={summary.sortie_id}" in lp and 'degradation="egt"' in lp
    life = [p for p in sink.points if p._name == "life_counters"]
    assert len(life) == 10 and all("hours_remaining=" in p.to_line_protocol() for p in life)
    counters = fake.thing["features"]["lifeCounters"]["properties"]
    assert counters["lastSortieId"] == summary.sortie_id
    assert counters["engine"]["hours"] == pytest.approx(142.6 + summary.flight_hours, abs=1e-3)
    # a second ingest of the same file writes telemetry again but does not double-count hours
    ingest_file(path, sink, fake.client())
    assert counters["engine"]["hours"] == pytest.approx(142.6 + summary.flight_hours, abs=1e-3)


@pytest.mark.skipif(len(SAMPLES) < 20, reason="full sample set not generated")
def test_manifest_matches_sample_set():
    manifest = json.loads((ROOT / "data" / "samples" / "manifest.json").read_text())
    assert len(manifest["sorties"]) == 20 == len(SAMPLES)
    degraded = [s for s in manifest["sorties"] if s["degradation"] != "none"]
    assert {s["degradation"] for s in degraded} == {"egt", "vibration", "servo"}
    assert [s["index"] for s in degraded] == [7, 12, 13, 14, 18]
    assert all((ROOT / "data" / "samples" / s["file"]).exists() for s in manifest["sorties"])
