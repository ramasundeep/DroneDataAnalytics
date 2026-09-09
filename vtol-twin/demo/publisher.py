"""Optional mirror of demo telemetry onto the real MQTT pipeline (same topics the aircraft uses).

If paho-mqtt is missing or the broker is unreachable the demo keeps running in-memory only.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from .logging_setup import log

logger = logging.getLogger("demo.publisher")

try:  # optional dependency
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    mqtt = None


class MqttPublisher:
    def __init__(self, host: Optional[str], port: int = 1883, tail: str = "VTOL-1", qos: int = 1):
        self.tail = tail
        self.qos = qos
        self.enabled = False
        self.connected = False
        self.published = 0
        self.dropped = 0
        self._client = None
        if not host or mqtt is None:
            log(logger, "mqtt mirror disabled", reason="no host" if not host else "paho-mqtt not installed")
            return
        self.enabled = True
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"vtol-demo-{tail}",
                                   protocol=mqtt.MQTTv5)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.reconnect_delay_set(min_delay=1, max_delay=15)
        try:
            self._client.connect_async(host, port, keepalive=30)
            self._client.loop_start()
            log(logger, "mqtt mirror connecting", host=host, port=port)
        except Exception as exc:  # noqa: BLE001
            log(logger, "mqtt mirror failed to start", error=str(exc))
            self.enabled = False

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = reason_code == 0 or getattr(reason_code, "is_failure", True) is False
        log(logger, "mqtt connected" if self.connected else "mqtt connect refused", reason=str(reason_code))

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False
        log(logger, "mqtt disconnected", reason=str(reason_code))

    def publish_features(self, features: Dict[str, dict], ts: Optional[str] = None) -> None:
        """Multi-feature message on vtol/<tail>/telemetry (mapper fans it out per feature)."""
        self._publish(f"vtol/{self.tail}/telemetry", dict(features, **({"ts": ts} if ts else {})))

    def publish_feature(self, feature: str, props: dict) -> None:
        self._publish(f"vtol/{self.tail}/telemetry/{feature}", props)

    def _publish(self, topic: str, payload: dict) -> None:
        if not self.enabled or self._client is None:
            return
        if not self.connected:
            self.dropped += 1
            return
        info = self._client.publish(topic, json.dumps(payload, default=str), qos=self.qos)
        if info.rc == 0:
            self.published += 1
        else:
            self.dropped += 1

    def status(self) -> dict:
        return {"enabled": self.enabled, "connected": self.connected,
                "published": self.published, "dropped": self.dropped}

    def close(self) -> None:
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
