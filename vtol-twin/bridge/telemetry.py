"""MQTT telemetry topic/payload parsing - the Python twin of ditto/mapping/telemetry-incoming.js.

    vtol/<tail>/telemetry             {"ts": ..., "engine": {...}, "power": {...}}
    vtol/<tail>/telemetry/<feature>   {"ts": ..., "rpm": 5400, ...}
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

META_KEYS = {"tail", "thingId", "sortieId", "source"}   # recognised at the top level of a message
STRIP_KEYS = {"tail", "thingId"}                          # never stored as feature properties (as in the JS mapper)


def parse_topic(topic: str) -> Optional[Tuple[str, Optional[str]]]:
    parts = topic.split("/")
    if len(parts) < 3 or len(parts) > 4 or parts[0] != "vtol" or parts[2] != "telemetry":
        return None
    return parts[1], (parts[3] if len(parts) == 4 else None)


def parse_telemetry(topic: str, payload: bytes | str) -> Optional[Tuple[str, Dict[str, Dict[str, Any]], Dict[str, Any]]]:
    """Returns (tail, {feature: props}, meta) or None when the message is not telemetry / not JSON."""
    route = parse_topic(topic)
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if route is None:
        if not data.get("tail"):
            return None
        route = (str(data["tail"]), data.get("feature"))
    tail, feature = route
    meta = {k: data[k] for k in META_KEYS if k in data}
    if feature is not None:
        props = {k: v for k, v in data.items() if k not in STRIP_KEYS and k != "feature"}
        return tail, {feature: props}, meta
    ts = data.get("ts")
    features: Dict[str, Dict[str, Any]] = {}
    for key, value in data.items():
        if isinstance(value, dict) and key not in META_KEYS:
            props = {k: v for k, v in value.items() if k not in STRIP_KEYS}
            if ts is not None and "ts" not in props:
                props["ts"] = ts
            features[key] = props
    if not features:
        return None
    return tail, features, meta
