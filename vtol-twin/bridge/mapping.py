"""uORB topics <-> twin features.

`TOPICS` is the ULog schema the synthetic writer emits and the batch ingester reads; PX4-standard topic
and field names are used where they exist, custom topics (servo bus, 28 V bus, INS summary, per-axis
vibration) are marked. `features_from_topic()` converts one row of a topic into twin feature properties;
`topic_rows_from_features()` does the reverse for the writer. Both directions live here so the ULog
path and the MQTT/Ditto path stay consistent with docs/data-dictionary.md.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# name -> list of (type, field). timestamp first (microseconds since boot), like every PX4 topic.
TOPICS: Dict[str, List[Tuple[str, str]]] = {
    "vehicle_status": [("uint64_t", "timestamp"), ("uint8_t", "arming_state"), ("uint8_t", "nav_state"),
                       ("uint8_t", "vehicle_type"), ("bool", "in_transition_mode"), ("bool", "in_transition_to_fw")],
    "vehicle_land_detected": [("uint64_t", "timestamp"), ("bool", "landed")],
    "vehicle_global_position": [("uint64_t", "timestamp"), ("double", "lat"), ("double", "lon"), ("float", "alt")],
    "vehicle_local_position": [("uint64_t", "timestamp"), ("float", "dist_bottom"), ("float", "vx"), ("float", "vy"),
                               ("float", "heading")],
    "airspeed_validated": [("uint64_t", "timestamp"), ("float", "true_airspeed_m_s")],
    "internal_combustion_engine_status": [
        ("uint64_t", "timestamp"), ("uint32_t", "engine_speed_rpm"), ("float", "exhaust_gas_temperature"),
        ("float", "cylinder_head_temperature"), ("float", "fuel_consumption_rate_cm3pm"),
        ("float", "throttle_position_percent"), ("float", "oil_pressure"), ("uint8_t", "state")],
    "fuel_tank_status": [("uint64_t", "timestamp"), ("float", "remaining_fuel")],
    "vehicle_imu_status": [("uint64_t", "timestamp"), ("float", "accel_vibration_metric"),
                           ("uint32_t[3]", "accel_clipping")],
    "vibration_rms": [("uint64_t", "timestamp"), ("float", "rms_x"), ("float", "rms_y"), ("float", "rms_z")],  # custom
    "actuator_outputs": [("uint64_t", "timestamp"), ("float[16]", "output")],
    "servo_telemetry": [("uint64_t", "timestamp"), ("float[4]", "current_a")],                                 # custom
    "battery_status": [("uint64_t", "timestamp"), ("float", "voltage_v"), ("float", "current_a"),
                       ("float", "remaining"), ("float", "temperature")],
    "bus_power": [("uint64_t", "timestamp"), ("float", "bus_voltage_v"), ("float", "bus_current_a")],          # custom
    "sensor_gps": [("uint64_t", "timestamp"), ("uint64_t", "time_utc_usec"), ("uint8_t", "fix_type"),
                   ("uint8_t", "satellites_used"), ("float", "hdop")],
    "ins_status": [("uint64_t", "timestamp"), ("uint8_t", "status"), ("bool", "aligned")],                      # custom
}
CUSTOM_TOPICS = {"vibration_rms", "servo_telemetry", "bus_power", "ins_status"}

ARMING_DISARMED, ARMING_ARMED = 1, 2
VEHICLE_TYPE_ROTARY, VEHICLE_TYPE_FIXED_WING = 1, 2
ENGINE_STOPPED, ENGINE_STARTING, ENGINE_RUNNING = 0, 1, 2
NAV_STATE = {0: "MANUAL", 2: "POSCTL", 3: "AUTO_MISSION", 4: "AUTO_LOITER", 5: "AUTO_RTL",
             17: "AUTO_TAKEOFF", 18: "AUTO_LAND", 14: "OFFBOARD"}
NAV_STATE_BY_NAME = {v: k for k, v in NAV_STATE.items()}
INS_STATUS = {0: "unknown", 1: "aligning", 2: "ok", 3: "degraded", 4: "failed"}
INS_STATUS_BY_NAME = {v: k for k, v in INS_STATUS.items()}
SERVO_PWM_CENTER, SERVO_PWM_PER_DEG = 1500.0, 500.0 / 30.0       # +-30 deg full travel


def vtol_state(vehicle_type: int, in_transition: bool, to_fw: bool, armed: bool, landed: bool = False) -> str:
    if not armed or landed:
        return "ground"
    if in_transition:
        return "transition-forward" if to_fw else "transition-back"
    return "fixed-wing" if vehicle_type == VEHICLE_TYPE_FIXED_WING else "hover"


def _r(v: Any, nd: int = 3) -> float:
    return round(float(v), nd)


def features_from_topic(topic: str, row: Dict[str, Any], landed: bool = False) -> Dict[str, Dict[str, Any]]:
    """One topic sample -> {feature: {property: value}} (without ts; caller adds it).

    `landed` is the vehicle_land_detected state at the row's time (joined by the caller) and only
    matters for vehicle_status.
    """
    if topic == "vehicle_land_detected":
        return {}          # consumed through the join, not emitted on its own
    if topic == "internal_combustion_engine_status":
        return {"engine": {
            "rpm": int(row["engine_speed_rpm"]), "egtC": _r(row["exhaust_gas_temperature"], 1),
            "chtC": _r(row["cylinder_head_temperature"], 1),
            "fuelFlowLph": _r(float(row["fuel_consumption_rate_cm3pm"]) * 60.0 / 1000.0, 2),
            "throttlePct": _r(row["throttle_position_percent"], 1), "oilPressureKpa": _r(row["oil_pressure"], 0),
            "running": int(row["state"]) == ENGINE_RUNNING}}
    if topic == "fuel_tank_status":
        return {"flightState": {"fuelRemainingL": _r(row["remaining_fuel"], 2)}}
    if topic == "vehicle_imu_status":
        clip = row["accel_clipping"]
        clip_total = int(sum(clip)) if isinstance(clip, (list, tuple)) else int(clip)
        return {"vibration": {"rmsTotal": _r(row["accel_vibration_metric"]), "clipCount": clip_total}}
    if topic == "vibration_rms":
        return {"vibration": {"rmsX": _r(row["rms_x"]), "rmsY": _r(row["rms_y"]), "rmsZ": _r(row["rms_z"])}}
    if topic == "actuator_outputs":
        out = row["output"]
        return {"actuation": {f"servo{i + 1}PositionDeg": _r((float(out[i]) - SERVO_PWM_CENTER) / SERVO_PWM_PER_DEG, 2)
                              for i in range(4)}}
    if topic == "servo_telemetry":
        cur = row["current_a"]
        return {"actuation": {f"servo{i + 1}CurrentA": _r(cur[i]) for i in range(4)}}
    if topic == "battery_status":
        return {"power": {"batteryVoltageV": _r(row["voltage_v"], 2), "batteryCurrentA": _r(row["current_a"], 2),
                          "batteryRemainingPct": _r(float(row["remaining"]) * 100.0, 1),
                          "batteryTempC": _r(row["temperature"], 1)}}
    if topic == "bus_power":
        return {"power": {"busVoltageV": _r(row["bus_voltage_v"], 2), "busCurrentA": _r(row["bus_current_a"], 2)}}
    if topic == "sensor_gps":
        return {"navigation": {"gpsFixType": int(row["fix_type"]), "gpsSatellites": int(row["satellites_used"]),
                               "gpsHdop": _r(row["hdop"], 2)}}
    if topic == "ins_status":
        return {"navigation": {"insStatus": INS_STATUS.get(int(row["status"]), "unknown"), "insAligned": bool(row["aligned"])}}
    if topic == "vehicle_status":
        armed = int(row["arming_state"]) == ARMING_ARMED
        return {"flightState": {
            "armed": armed, "flightMode": NAV_STATE.get(int(row["nav_state"]), f"NAV_{int(row['nav_state'])}"),
            "vtolState": vtol_state(int(row["vehicle_type"]), bool(row["in_transition_mode"]),
                                    bool(row["in_transition_to_fw"]), armed, landed)}}
    if topic == "vehicle_global_position":
        return {"flightState": {"lat": _r(row["lat"], 6), "lon": _r(row["lon"], 6), "altMslM": _r(row["alt"], 1)}}
    if topic == "vehicle_local_position":
        import math
        gs = math.hypot(float(row["vx"]), float(row["vy"]))
        return {"flightState": {"altAglM": _r(row["dist_bottom"], 1), "groundspeedMps": _r(gs, 2),
                                "headingDeg": _r(math.degrees(float(row["heading"])) % 360.0, 1)}}
    if topic == "airspeed_validated":
        return {"flightState": {"airspeedMps": _r(row["true_airspeed_m_s"], 2)}}
    return {}


def topic_rows_from_features(features: Dict[str, Dict[str, Any]], t_us: int, utc_us: int) -> Dict[str, Dict[str, Any]]:
    """Reverse mapping for the synthetic writer: twin features (simulator output) -> uORB rows."""
    import math
    e, v, a, p, n, f = (features.get(k, {}) for k in ("engine", "vibration", "actuation", "power", "navigation", "flightState"))
    armed = bool(f.get("armed"))
    vs = f.get("vtolState", "ground")
    rows = {
        "vehicle_status": {"timestamp": t_us, "arming_state": ARMING_ARMED if armed else ARMING_DISARMED,
                           "nav_state": NAV_STATE_BY_NAME.get(f.get("flightMode", "MANUAL"), 0),
                           "vehicle_type": VEHICLE_TYPE_FIXED_WING if vs == "fixed-wing" else VEHICLE_TYPE_ROTARY,
                           "in_transition_mode": vs.startswith("transition"), "in_transition_to_fw": vs == "transition-forward"},
        "vehicle_land_detected": {"timestamp": t_us, "landed": vs == "ground"},
        "vehicle_global_position": {"timestamp": t_us, "lat": f.get("lat", 0.0), "lon": f.get("lon", 0.0), "alt": f.get("altMslM", 0.0)},
        "vehicle_local_position": {"timestamp": t_us, "dist_bottom": f.get("altAglM", 0.0),
                                   "vx": f.get("groundspeedMps", 0.0) * math.cos(math.radians(f.get("headingDeg", 0.0))),
                                   "vy": f.get("groundspeedMps", 0.0) * math.sin(math.radians(f.get("headingDeg", 0.0))),
                                   "heading": math.radians(f.get("headingDeg", 0.0))},
        "airspeed_validated": {"timestamp": t_us, "true_airspeed_m_s": f.get("airspeedMps", 0.0)},
        "internal_combustion_engine_status": {
            "timestamp": t_us, "engine_speed_rpm": e.get("rpm", 0), "exhaust_gas_temperature": e.get("egtC", 0.0),
            "cylinder_head_temperature": e.get("chtC", 0.0), "fuel_consumption_rate_cm3pm": e.get("fuelFlowLph", 0.0) * 1000.0 / 60.0,
            "throttle_position_percent": e.get("throttlePct", 0.0), "oil_pressure": e.get("oilPressureKpa", 0.0),
            "state": ENGINE_RUNNING if e.get("running") else (ENGINE_STARTING if e.get("rpm", 0) > 0 else ENGINE_STOPPED)},
        "fuel_tank_status": {"timestamp": t_us, "remaining_fuel": f.get("fuelRemainingL", 0.0)},
        "vehicle_imu_status": {"timestamp": t_us, "accel_vibration_metric": v.get("rmsTotal", 0.0),
                               "accel_clipping": [v.get("clipCount", 0), 0, 0]},
        "vibration_rms": {"timestamp": t_us, "rms_x": v.get("rmsX", 0.0), "rms_y": v.get("rmsY", 0.0), "rms_z": v.get("rmsZ", 0.0)},
        "actuator_outputs": {"timestamp": t_us, "output": [SERVO_PWM_CENTER + a.get(f"servo{i + 1}PositionDeg", 0.0) * SERVO_PWM_PER_DEG
                                                            for i in range(4)] + [0.0] * 12},
        "servo_telemetry": {"timestamp": t_us, "current_a": [a.get(f"servo{i + 1}CurrentA", 0.0) for i in range(4)]},
        "battery_status": {"timestamp": t_us, "voltage_v": p.get("batteryVoltageV", 0.0), "current_a": p.get("batteryCurrentA", 0.0),
                           "remaining": p.get("batteryRemainingPct", 0.0) / 100.0, "temperature": p.get("batteryTempC", 0.0)},
        "bus_power": {"timestamp": t_us, "bus_voltage_v": p.get("busVoltageV", 0.0), "bus_current_a": p.get("busCurrentA", 0.0)},
        "sensor_gps": {"timestamp": t_us, "time_utc_usec": utc_us, "fix_type": n.get("gpsFixType", 0),
                       "satellites_used": n.get("gpsSatellites", 0), "hdop": n.get("gpsHdop", 0.0)},
        "ins_status": {"timestamp": t_us, "status": INS_STATUS_BY_NAME.get(n.get("insStatus", "unknown"), 0),
                       "aligned": bool(n.get("insAligned", False))},
    }
    return rows
