"""End-to-end over the synthetic sample set: degraded sorties must be flagged in the right group,
nominal ones must not, and health / RUL / Ditto patch must reflect it."""
import json
from pathlib import Path

import httpx
import pytest

from analytics.engine import Analyzer, ditto_patch, influx_points
from analytics.sources import UlogSource
from common.ditto_client import DittoClient

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = sorted((ROOT / "data" / "samples").glob("*.ulg"))
pytestmark = pytest.mark.skipif(len(SAMPLES) < 20, reason="run data/samples/generate_samples.py first")


@pytest.fixture(scope="module")
def run():
    thing = json.loads((ROOT / "ditto" / "thing-VTOL-1.json").read_text())
    counters = thing["features"]["lifeCounters"]["properties"]
    return Analyzer().run(UlogSource([str(ROOT / "data" / "samples" / "*.ulg")]), counters, thing["attributes"]["components"],
                          starting_hours=float(counters["airframe"]["hours"]))


def by_index(run):
    return {i + 1: s for i, s in enumerate(run.sorties)}


def test_all_sorties_scored_in_order(run):
    assert len(run.sorties) == 20
    ids = [s.features.sortie_id for s in run.sorties]
    assert ids == sorted(ids)
    assert run.sorties[-1].cumulative_hours == pytest.approx(142.6 + sum(s.features.flight_hours for s in run.sorties), abs=1e-3)


def test_degraded_sorties_flagged_in_the_right_group(run):
    s = by_index(run)
    assert s[7].groups["engine"].flagged and s[7].groups["engine"].top_component == "engine"
    assert ("egtC", pytest.approx(764.2, abs=1), 680.0) in [(e[0], e[1], e[2]) for e in s[7].features.exceedances]
    for i in (12, 13, 14):
        assert s[i].groups["engine"].flagged, i
        assert s[i].groups["engine"].top_component == "ductedFan", i
    assert s[18].groups["actuation"].flagged and s[18].groups["actuation"].top_component == "servo3"
    assert not s[18].groups["engine"].flagged


def test_nominal_sorties_not_flagged(run):
    s = by_index(run)
    false_positives = [i for i in range(1, 21) if i not in (7, 12, 13, 14, 18) and s[i].flagged]
    assert false_positives == [], false_positives
    assert all(not s[i].groups["power"].flagged for i in range(1, 21))


def test_anomaly_scores_separate_classes(run):
    s = by_index(run)
    nominal = [s[i].groups["engine"].score for i in range(1, 21) if i not in (7, 12, 13, 14, 18)]
    assert max(nominal) < 0.5
    assert min(s[i].groups["engine"].score for i in (7, 12, 13, 14)) >= 0.5
    vib = [s[i].features.values["vib_cruise_mean"] for i in (12, 13, 14)]
    assert vib[0] < vib[1] < vib[2], "the injected vibration trend must rise sortie over sortie"
    assert all("vib_" in s[i].groups["engine"].top_feature for i in (12, 13, 14))


def test_component_health_reflects_the_last_sorties(run):
    h = run.health
    # the last sortie (20) is nominal, but the servo3 exceedance on sortie 18 is recent (within 3 sorties)
    # and holds the component at caution until maintenance signs it off; the ducted fan exceedances of
    # sorties 12-14 are older and its indicator has recovered, so it is back to normal
    assert h["servo3"].alert_level == "caution" and h["servo3"].health_score < 80
    assert h["servo3"].evidence["lastExceedance"]["signal"] == "servo3CurrentA" and h["servo3"].evidence["lastExceedance"]["recent"]
    assert h["ductedFan"].alert_level == "normal" and h["ductedFan"].evidence["lastExceedance"]["recent"] is False
    assert h["servo1"].alert_level == "normal" and h["servo2"].alert_level == "normal"
    assert h["avionics"].alert_level == "normal" and h["payloadGimbal"].alert_level == "normal"
    assert 0 < h["engine"].rul_hours <= h["engine"].rul_life_hours
    for c, x in h.items():
        assert 0 <= x.health_score <= 100 and x.rul_hours >= 0
    assert run.worst_alert == "caution"


def test_health_after_the_vibration_sorties_shows_short_trend_rul():
    thing = json.loads((ROOT / "ditto" / "thing-VTOL-1.json").read_text())
    counters = thing["features"]["lifeCounters"]["properties"]
    files = [str(p) for p in SAMPLES[:14]]                         # stop right after sortie 14
    run = Analyzer().run(UlogSource(files), counters, thing["attributes"]["components"], starting_hours=142.6)
    fan = run.health["ductedFan"]
    assert fan.alert_level in ("caution", "warning") and fan.health_score < 65
    assert fan.rul_trend_hours is not None and fan.rul_hours == fan.rul_trend_hours < fan.rul_life_hours
    assert fan.evidence["indicator"] == "vib_cruise_mean" and fan.evidence["slopePerHour"] > 0
    assert run.worst_alert in ("caution", "warning")


class FakeDitto:
    def __init__(self):
        self.thing = json.loads((ROOT / "ditto" / "thing-VTOL-1.json").read_text())
        self.merges = []

    def handler(self, request):
        path = request.url.path
        if request.method == "GET" and path.endswith("/attributes"):
            return httpx.Response(200, json=self.thing["attributes"])
        if request.method == "GET" and "/features/" in path:
            fid = path.split("/features/")[1].split("/")[0]
            return httpx.Response(200, json=self.thing["features"][fid]["properties"])
        if request.method == "PATCH" and path.endswith("/features"):
            body = json.loads(request.content)
            self.merges.append(body)
            for fid, f in body.items():
                self.thing["features"].setdefault(fid, {"properties": {}})["properties"].update(f["properties"])
            return httpx.Response(204)
        return httpx.Response(404)


def test_ditto_patch_and_influx_points(run):
    patch = ditto_patch(run)
    assert set(patch) == {"health"}
    props = patch["health"]
    assert set(props) >= {"engine", "ductedFan", "servo3", "battery", "lastRun"}
    for c in ("engine", "servo3"):
        assert {"healthScore", "rulHours", "alertLevel", "anomalyScore", "evidence"} <= set(props[c])
    assert props["lastRun"]["sortiesScored"] == 20 and props["lastRun"]["worstAlert"] == run.worst_alert
    fake = FakeDitto()
    d = DittoClient("http://ditto", "analytics", "x", "vtol.fleet:VTOL-1", transport=httpx.MockTransport(fake.handler))
    d.merge_features(patch)
    assert fake.thing["features"]["health"]["properties"]["servo3"]["alertLevel"] == run.health["servo3"].alert_level
    assert fake.thing["features"]["health"]["properties"]["aircraft"]["releaseStatus"] == "serviceable", "release status is Phase 4's"
    pts = influx_points(run)
    names = {p._name for p in pts}
    assert names == {"health", "anomaly"}
    assert sum(1 for p in pts if p._name == "health") == 10 and sum(1 for p in pts if p._name == "anomaly") == 60
    lp = next(p for p in pts if p._name == "anomaly" and "sortie=" + run.sorties[6].features.sortie_id in p.to_line_protocol() and "group=engine" in p.to_line_protocol()).to_line_protocol()
    assert "flagged=true" in lp
