"""Structural tests for the VTOL-1 Thing model, policy and connection definition.

Run with: python3 -m pytest -q ditto/tests
"""
import json
import os
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DITTO = ROOT / "ditto"

EXPECTED_COMPONENTS = {
    "engine", "ductedFan", "fuelPump", "servo1", "servo2", "servo3", "servo4",
    "avionics", "payloadGimbal", "battery",
}
COMPONENT_KEYS = {
    "name", "partNumber", "serial", "installDate", "lifeLimitHours", "lifeLimitCycles",
    "hoursConsumed", "cyclesConsumed",
}
TELEMETRY_FEATURES = {"engine", "vibration", "actuation", "power", "navigation", "flightState"}


@pytest.fixture(scope="module")
def thing():
    return json.loads((DITTO / "thing-VTOL-1.json").read_text())


@pytest.fixture(scope="module")
def policy():
    return json.loads((DITTO / "policy.json").read_text())


@pytest.fixture(scope="module")
def connection():
    return json.loads((DITTO / "connection-mqtt.json").read_text())


def test_ids_are_consistent(thing, policy):
    assert thing["thingId"] == "vtol.fleet:VTOL-1"
    assert thing["policyId"] == policy["policyId"]
    assert thing["attributes"]["tailNumber"] == thing["thingId"].split(":")[1]


def test_ten_tracked_components_with_life_data(thing):
    comps = thing["attributes"]["components"]
    assert set(comps) == EXPECTED_COMPONENTS
    for cid, c in comps.items():
        missing = COMPONENT_KEYS - set(c)
        assert not missing, f"{cid} missing {missing}"
        date.fromisoformat(c["installDate"])
        assert 0 <= c["hoursConsumed"] <= c["lifeLimitHours"], cid
        assert 0 <= c["cyclesConsumed"] <= c["lifeLimitCycles"], cid
    assert {comps[f"servo{i}"]["position"] for i in range(1, 5)} == {
        "elevon-left", "elevon-right", "thrust-vane-A", "thrust-vane-B"}
    assert len({c["serial"] for c in comps.values()}) == len(comps), "serials must be unique"


def test_component_install_after_airframe_delivery(thing):
    delivered = date.fromisoformat(thing["attributes"]["airframe"]["deliveryDate"])
    for cid, c in thing["attributes"]["components"].items():
        assert date.fromisoformat(c["installDate"]) >= delivered, cid


def test_live_features_present(thing):
    feats = thing["features"]
    assert TELEMETRY_FEATURES <= set(feats)
    for f in TELEMETRY_FEATURES:
        assert "ts" in feats[f]["properties"], f
    for key in ("rpm", "egtC", "chtC", "fuelFlowLph"):
        assert key in feats["engine"]["properties"]
    for i in range(1, 5):
        assert f"servo{i}CurrentA" in feats["actuation"]["properties"]
    assert "busVoltageV" in feats["power"]["properties"]
    assert {"gpsFixType", "insStatus"} <= set(feats["navigation"]["properties"])


def test_life_counters_and_health_cover_every_component(thing):
    comps = thing["attributes"]["components"]
    counters = thing["features"]["lifeCounters"]["properties"]
    health = thing["features"]["health"]["properties"]
    for cid, c in comps.items():
        assert counters[cid] == {"hours": c["hoursConsumed"], "cycles": c["cyclesConsumed"]}, cid
        h = health[cid]
        assert h["alertLevel"] == "normal" and 0 <= h["healthScore"] <= 100
        assert h["rulHours"] == pytest.approx(c["lifeLimitHours"] - c["hoursConsumed"], abs=0.05), cid
    assert health["aircraft"]["releaseStatus"] in {"serviceable", "unserviceable", "limited"}


def test_policy_grants_telemetry_subject_feature_write(policy, connection):
    subjects = {s for e in policy["entries"].values() for s in e["subjects"]}
    for src in connection["sources"]:
        for subj in src["authorizationContext"]:
            assert subj in subjects, subj
    tele = policy["entries"]["TELEMETRY"]["resources"]
    assert "WRITE" in tele["thing:/features"]["grant"]
    assert "WRITE" not in tele["thing:/"]["grant"], "telemetry must not rewrite attributes"
    assert "nginx:ditto" in policy["entries"]["OPERATOR"]["subjects"]


def test_connection_subscribes_to_both_topic_shapes(connection):
    addrs = connection["sources"][0]["addresses"]
    assert "vtol/+/telemetry" in addrs and "vtol/+/telemetry/+" in addrs
    assert connection["connectionType"] == "mqtt-5"
    assert connection["sources"][0]["payloadMapping"] == ["telemetryMapping"]
    opts = connection["mappingDefinitions"]["telemetryMapping"]["options"]
    assert opts["incomingScript"] == "__INCOMING_SCRIPT__"  # substituted by ditto/setup.sh
    assert connection["targets"][0]["address"] == "vtol/{{ thing:name }}/events"


def test_generic_designation_used_consistently():
    """The aircraft is referred to only as VTOL-1 / vtol.fleet:VTOL-1 across the twin definition."""
    ids = set()
    for p in DITTO.glob("*.json"):
        ids |= set(re.findall(r"vtol\.fleet:[A-Za-z0-9._-]+", p.read_text()))
    assert ids == {"vtol.fleet:VTOL-1", "vtol.fleet:vtol-policy"}, ids


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed")
def test_compose_file_is_valid():
    env = dict(os.environ, DITTO_DEVOPS_PASSWORD="x", INFLUXDB_INIT_PASSWORD="x", INFLUXDB_TOKEN="x",
               GRAFANA_ADMIN_PASSWORD="x", ANALYTICS_DITTO_PASSWORD="x", MAINTENANCE_DITTO_PASSWORD="x")
    res = subprocess.run(["docker", "compose", "--env-file", "/dev/null", "--profile", "pipeline", "--profile", "demo",
                          "config", "--quiet"],
                         cwd=ROOT, env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
