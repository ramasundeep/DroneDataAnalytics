import pytest

from demo import simulator as sim
from demo.twin import InMemoryTwin, SortieStats, merge_patch


def fly(twin, degradation="none", severity=1.5, seed=1, cruise=120, sortie_id="S1"):
    cfg = sim.SortieConfig(sortie_id=sortie_id, cruise_seconds=cruise, degradation=degradation, severity=severity,
                           seed=seed, baseline=twin.wear.get(degradation, 0.0))
    s = sim.SortieSimulator(cfg)
    stats = SortieStats()
    for sample in s:
        twin.merge_features(sample.features)
        stats.add(sample.features)
    return twin.close_sortie(sortie_id, s.flight_hours, stats, degradation, s.wear_added)


def test_merge_patch_is_partial_and_null_deletes():
    t = {"engine": {"properties": {"rpm": 1, "egtC": 2}}}
    merge_patch(t, {"engine": {"properties": {"rpm": 5, "egtC": None}}, "power": {"properties": {"busVoltageV": 28}}})
    assert t == {"engine": {"properties": {"rpm": 5}}, "power": {"properties": {"busVoltageV": 28}}}


def test_initial_state_matches_model_and_is_serviceable():
    twin = InMemoryTwin()
    h = twin.features["health"]["properties"]
    assert h["aircraft"]["releaseStatus"] == "serviceable"
    assert all(h[c]["alertLevel"] == "normal" for c in twin.components)
    assert h["engine"]["rulHours"] == pytest.approx(500 - 142.6, abs=0.1)


def test_nominal_sortie_accrues_hours_without_alerts():
    twin = InMemoryTwin()
    before = twin.features["lifeCounters"]["properties"]["engine"]["hours"]
    rec = fly(twin)
    assert all(c["trendRulHours"] is None for c in twin.condition.values()), "no trend on a nominal sortie"
    assert all(h["rulHours"] > 200 for cid, h in twin.features["health"]["properties"].items() if cid != "aircraft")
    counters = twin.features["lifeCounters"]["properties"]
    assert counters["engine"]["hours"] == pytest.approx(before + rec["flightHours"], abs=1e-3)
    assert counters["engine"]["cycles"] == 232 and counters["lastSortieId"] == "S1"
    assert twin.thing["attributes"]["airframe"]["totalLandings"] == 232
    assert twin.work_orders == []
    assert twin.features["health"]["properties"]["aircraft"]["releaseStatus"] == "serviceable"


@pytest.mark.parametrize("degradation,component", [("vibration", "ductedFan"), ("egt", "engine"), ("servo", "servo3")])
def test_degraded_sortie_raises_alert_and_work_order(degradation, component):
    twin = InMemoryTwin()
    fly(twin, degradation=degradation)
    h = twin.features["health"]["properties"]
    assert h[component]["alertLevel"] in ("caution", "warning")
    assert h[component]["healthScore"] < 80
    wo = twin.open_work_order(component)
    assert wo is not None and wo["evidence"]["sortieId"] == "S1"
    assert h["aircraft"]["releaseStatus"] in ("limited", "unserviceable")
    others = [c for c in twin.components if c != component]
    assert all(h[c]["alertLevel"] == "normal" for c in others), "fault must be isolated"


def test_mild_fault_accumulates_over_sorties_until_it_trips():
    twin = InMemoryTwin()
    levels = []
    for i in range(4):
        fly(twin, degradation="vibration", severity=0.5, sortie_id=f"S{i}", seed=i)
        levels.append(twin.features["health"]["properties"]["ductedFan"]["alertLevel"])
    assert levels[0] == "normal", "half-severity fault should not trip on the first sortie"
    assert levels[-1] in ("caution", "warning")
    assert twin.wear["vibration"] == pytest.approx(4 * 0.5 * sim.WEAR_PER_SORTIE)
    wo = twin.open_work_order("ductedFan")
    twin.sign_off(wo["id"], "repaired", "tech", 3.0)
    assert "vibration" not in twin.wear


def test_trend_projection_shortens_rul():
    twin = InMemoryTwin()
    fly(twin, degradation="vibration", severity=0.5, sortie_id="S0")
    fly(twin, degradation="vibration", severity=0.5, sortie_id="S1", seed=2)   # elevated, rising, under the limit
    cond = twin.condition["ductedFan"]
    assert cond["slopePerHour"] > 0
    assert cond["trendRulHours"] is not None
    assert twin.features["health"]["properties"]["ductedFan"]["rulHours"] <= cond["trendRulHours"]


def test_sign_off_returns_aircraft_to_service_and_replacement_resets_counters():
    twin = InMemoryTwin()
    fly(twin, degradation="servo")
    wo = twin.open_work_order("servo3")
    old_serial = twin.components["servo3"]["serial"]
    closed = twin.sign_off(wo["id"], "replaced", "tech-1", 2.5, ["SRV-CS-40"])
    assert closed["status"] == "closed" and closed["partsConsumed"] == ["SRV-CS-40"]
    assert twin.components["servo3"]["serial"] != old_serial
    assert twin.features["lifeCounters"]["properties"]["servo3"] == {"hours": 0.0, "cycles": 0}
    h = twin.features["health"]["properties"]
    assert h["servo3"]["alertLevel"] == "normal"
    assert h["aircraft"]["releaseStatus"] == "serviceable" and h["aircraft"]["openWorkOrders"] == 0
    with pytest.raises(ValueError):
        twin.sign_off(wo["id"], "repaired", "tech-1", 1.0)
    with pytest.raises(KeyError):
        twin.sign_off("WO-9999", "repaired", "tech-1", 1.0)


def test_life_limit_approach_opens_work_order():
    twin = InMemoryTwin()
    twin.features["lifeCounters"]["properties"]["fuelPump"]["hours"] = 275.0   # 91.7 % of 300 h
    twin._recompute_health()
    h = twin.features["health"]["properties"]["fuelPump"]
    assert h["alertLevel"] == "caution"
    assert "life limit" in twin.open_work_order("fuelPump")["defect"]


def test_reset_restores_model():
    twin = InMemoryTwin()
    fly(twin, degradation="egt")
    twin.reset()
    assert twin.work_orders == [] and twin.sorties == []
    assert twin.features["health"]["properties"]["aircraft"]["releaseStatus"] == "serviceable"
