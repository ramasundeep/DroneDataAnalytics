import math
from datetime import datetime, timezone

from demo import simulator as sim


def cfg(**kw):
    base = dict(sortie_id="20260905-VTOL-1-01", cruise_seconds=120, seed=7,
                start_time=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc))
    base.update(kw)
    return sim.SortieConfig(**base)


def test_phase_sequence_and_duration():
    c = cfg()
    samples = list(sim.SortieSimulator(c))
    assert len(samples) == sim.total_seconds(c)
    seen = []
    for s in samples:
        if not seen or seen[-1] != s.phase:
            seen.append(s.phase)
    assert seen == [p for p, _ in sim.PHASES]
    assert samples[0].features["flightState"]["vtolState"] == "ground"
    assert any(s.features["flightState"]["vtolState"] == "fixed-wing" for s in samples)


def test_samples_match_thing_feature_shape():
    s = sim.SortieSimulator(cfg()).step(200)
    assert set(s.features) == {"engine", "vibration", "actuation", "power", "navigation", "flightState"}
    for props in s.features.values():
        assert props["ts"].endswith("Z")
    assert {"rpm", "egtC", "chtC", "fuelFlowLph", "throttlePct", "running"} <= set(s.features["engine"])
    for i in range(1, 5):
        assert f"servo{i}CurrentA" in s.features["actuation"]


def test_nominal_flight_stays_within_limits():
    s = sim.SortieSimulator(cfg())
    samples = list(s)
    assert max(x.features["engine"]["egtC"] for x in samples) < 680
    assert max(x.features["vibration"]["rmsTotal"] for x in samples) < 1.8
    assert max(x.features["actuation"]["servo3CurrentA"] for x in samples) < 1.9
    assert 0.05 < s.flight_hours < 0.2
    assert samples[-1].features["flightState"]["fuelRemainingL"] < 18.0


def test_degradations_push_their_signal_over_the_limit():
    peaks = {}
    for kind, feat, prop in (("vibration", "vibration", "rmsTotal"), ("egt", "engine", "egtC"),
                             ("servo", "actuation", "servo3CurrentA")):
        samples = list(sim.SortieSimulator(cfg(degradation=kind, severity=1.5)))
        peaks[kind] = max(x.features[feat][prop] for x in samples)
    assert peaks["vibration"] > 1.8 and peaks["egt"] > 680 and peaks["servo"] > 1.9


def test_servo_fault_is_isolated_to_servo3():
    samples = list(sim.SortieSimulator(cfg(degradation="servo", severity=1.5)))
    for i in (1, 2, 4):
        assert max(x.features["actuation"][f"servo{i}CurrentA"] for x in samples) < 1.9


def test_deterministic_for_seed():
    a = [x.features["engine"]["rpm"] for x in sim.SortieSimulator(cfg(seed=3))]
    b = [x.features["engine"]["rpm"] for x in sim.SortieSimulator(cfg(seed=3))]
    assert a == b


def test_position_moves_in_cruise_and_returns_home():
    samples = list(sim.SortieSimulator(cfg(cruise_seconds=200)))
    cruise = [x for x in samples if x.phase == "cruise"]
    assert any(abs(x.features["flightState"]["lat"] - sim.HOME_LAT) > 0.005 for x in cruise)
    last = samples[-1].features["flightState"]
    assert math.isclose(last["lat"], sim.HOME_LAT, abs_tol=1e-6) and last["altAglM"] == 0
