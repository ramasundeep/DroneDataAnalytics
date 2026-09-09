"""Synthetic ULog writer -> pyulog reader -> feature mapping, plus flight-time derivation."""
from datetime import datetime, timezone

import pytest
from pyulog import ULog

from bridge import mapping
from bridge.ulog_ingest import ULogSortie, summarise
from bridge.ulog_writer import Topic, ULogWriter
from demo import simulator as sim


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    start = datetime(2026, 8, 1, 14, 0, tzinfo=timezone.utc)
    cfg = sim.SortieConfig(sortie_id="20260801-VTOL-1-01", cruise_seconds=90, seed=3, start_time=start,
                           degradation="servo", severity=1.2, baseline=0.3)
    s = sim.SortieSimulator(cfg)
    path = tmp_path_factory.mktemp("ulg") / "test.ulg"
    boot, utc0 = 30_000_000, int(start.timestamp() * 1e6)
    samples = list(s)
    with ULogWriter(str(path), boot, info={"sys_name": "PX4", "tail_number": "VTOL-1", "sortie_id": cfg.sortie_id,
                                            "degradation": "servo", "time_start_utc_usec": utc0}, params={"VT_TYPE": 0}) as w:
        for name, fields in mapping.TOPICS.items():
            w.add_topic(Topic(name, fields))
        for smp in samples:
            for name, row in mapping.topic_rows_from_features(smp.features, boot + smp.t * 1_000_000, utc0 + smp.t * 1_000_000).items():
                w.write(name, row)
    return path, samples, s


def test_pyulog_reads_every_topic_and_info(sample):
    path, samples, _ = sample
    u = ULog(str(path))
    assert not u.file_corruption
    assert set(d.name for d in u.data_list) == set(mapping.TOPICS)
    assert u.msg_info_dict["sys_name"] == "PX4" and u.msg_info_dict["sortie_id"] == "20260801-VTOL-1-01"
    assert u.initial_parameters["VT_TYPE"] == 0
    for d in u.data_list:
        assert len(d.data["timestamp"]) == len(samples), d.name


def test_mapping_roundtrip_preserves_feature_values(sample):
    path, samples, _ = sample
    sortie = ULogSortie(str(path))
    by_t = {}
    for ts, feats in sortie.samples():
        by_t.setdefault(ts, {}).update({f: {**by_t.get(ts, {}).get(f, {}), **p} for f, p in feats.items()})
    assert len(by_t) == len(samples)
    for smp in samples[::37]:
        got = by_t[smp.ts]
        e = smp.features["engine"]
        assert got["engine"]["rpm"] == e["rpm"]
        assert got["engine"]["egtC"] == pytest.approx(e["egtC"], abs=0.11)
        assert got["engine"]["fuelFlowLph"] == pytest.approx(e["fuelFlowLph"], abs=0.02)
        assert got["engine"]["running"] == e["running"]
        assert got["vibration"]["rmsTotal"] == pytest.approx(smp.features["vibration"]["rmsTotal"], abs=1e-3)
        assert got["actuation"]["servo3CurrentA"] == pytest.approx(smp.features["actuation"]["servo3CurrentA"], abs=1e-3)
        assert got["actuation"]["servo1PositionDeg"] == pytest.approx(smp.features["actuation"]["servo1PositionDeg"], abs=0.02)
        assert got["power"]["batteryRemainingPct"] == pytest.approx(smp.features["power"]["batteryRemainingPct"], abs=0.11)
        fs = smp.features["flightState"]
        assert got["flightState"]["armed"] == fs["armed"] and got["flightState"]["vtolState"] == fs["vtolState"]
        assert got["flightState"]["flightMode"] == fs["flightMode"]
        assert got["flightState"]["lat"] == pytest.approx(fs["lat"], abs=1e-6)
        assert got["navigation"]["insStatus"] == smp.features["navigation"]["insStatus"]


def test_sortie_metadata_and_flight_time(sample):
    path, samples, s = sample
    sortie = ULogSortie(str(path))
    assert sortie.tail == "VTOL-1" and sortie.sortie_id == "20260801-VTOL-1-01" and sortie.degradation == "servo"
    assert sortie.to_utc(30_000_000) == samples[0].ts
    hours, landings = sortie.flight_time()
    armed_s = sum(1 for x in samples if x.features["flightState"]["armed"])
    assert hours == pytest.approx(armed_s / 3600.0, abs=2 / 3600.0)
    assert landings == 1
    summary = summarise(sortie)
    assert summary.samples == len(samples) * (len(mapping.TOPICS) - 1)   # land_detected is joined, not emitted
    assert summary.stats["servo3_current_max_a"] > 1.9 and summary.stats["servo1_current_max_a"] < 1.9
    assert summary.stats["egt_max_c"] < 680


def test_overrides_and_derived_ids(sample, tmp_path):
    path, samples, _ = sample
    sortie = ULogSortie(str(path), tail="VTOL-2", sortie_id="custom-01")
    assert sortie.tail == "VTOL-2" and sortie.sortie_id == "custom-01"
    # a log without our custom info keys still gets a deterministic id from date + file name
    bare = tmp_path / "bare.ulg"
    with ULogWriter(str(bare), 1_000_000, info={"sys_name": "PX4"}) as w:
        w.add_topic(Topic("vehicle_status", mapping.TOPICS["vehicle_status"]))
        w.add_topic(Topic("sensor_gps", mapping.TOPICS["sensor_gps"]))
        utc0 = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1e6)
        for t in range(0, 120):
            w.write("vehicle_status", {"timestamp": 1_000_000 + t * 1_000_000, "arming_state": 2 if 10 <= t < 100 else 1,
                                       "nav_state": 3, "vehicle_type": 1, "in_transition_mode": False, "in_transition_to_fw": False})
            w.write("sensor_gps", {"timestamp": 1_000_000 + t * 1_000_000, "time_utc_usec": utc0 + t * 1_000_000,
                                   "fix_type": 3, "satellites_used": 12, "hdop": 0.8})
    b = ULogSortie(str(bare))
    assert b.sortie_id.startswith("20260901-VTOL-1-") and len(b.sortie_id) == len("20260901-VTOL-1-abcd")
    assert b.flight_time() == (pytest.approx(90 / 3600.0), 1)
    assert b.degradation is None
