"""Provisioned dashboards must be well-formed and point at the provisioned datasource / bucket."""
import json
from pathlib import Path

import pytest

DASH = sorted((Path(__file__).resolve().parents[2] / "dashboards").glob("*.json"))
EXPECTED_UIDS = {"vtol-fleet-health", "vtol-sortie-engine", "vtol-component-life"}


def test_three_dashboards_with_stable_uids():
    assert {json.loads(p.read_text())["uid"] for p in DASH} == EXPECTED_UIDS


@pytest.mark.parametrize("path", DASH, ids=[p.stem for p in DASH])
def test_dashboard_structure(path):
    d = json.loads(path.read_text())
    assert d["schemaVersion"] >= 36 and d["panels"] and d["title"].startswith("VTOL-1")
    ids = [p["id"] for p in d["panels"]]
    assert len(ids) == len(set(ids))
    for p in d["panels"]:
        assert p["datasource"]["uid"] == "influxdb-flight-telemetry"
        assert {"x", "y", "w", "h"} <= set(p["gridPos"]) and p["gridPos"]["x"] + p["gridPos"]["w"] <= 24
        for t in p["targets"]:
            assert 'from(bucket: "flight_telemetry")' in t["query"]
            assert "${tail}" in t["query"]
    assert any(v["name"] == "tail" for v in d["templating"]["list"])
    if d["uid"] == "vtol-sortie-engine":
        assert any(v["name"] == "sortie" for v in d["templating"]["list"])
        assert all("${sortie}" in t["query"] for p in d["panels"] for t in p["targets"])
