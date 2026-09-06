"""MQTT -> InfluxDB ingester service.

Subscribes to vtol/+/telemetry and vtol/+/telemetry/+, writes every property to the flight_telemetry
bucket tagged by tail and sortie (remembered per tail from flightState.sortieId), and serves
GET /health on INGEST_PORT (default 8091).
"""
from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

from common.influx import InfluxSink, points_from_features
from common.logging_setup import configure, log

from .telemetry import parse_telemetry

logger = logging.getLogger("bridge.mqtt")


class Ingester:
    def __init__(self, sink: InfluxSink, default_source: str = "live"):
        self.sink = sink
        self.default_source = default_source
        self.sortie_by_tail: Dict[str, Optional[str]] = {}
        self.received = 0
        self.written = 0
        self.dropped = 0
        self.last_message_at: Optional[str] = None
        self.mqtt_connected = False

    def handle(self, topic: str, payload: bytes) -> int:
        self.received += 1
        parsed = parse_telemetry(topic, payload)
        if parsed is None:
            self.dropped += 1
            return 0
        tail, features, meta = parsed
        fs = features.get("flightState") or {}
        if "sortieId" in fs:
            self.sortie_by_tail[tail] = fs["sortieId"]
        elif "sortieId" in meta:
            self.sortie_by_tail[tail] = meta["sortieId"]
        sortie = self.sortie_by_tail.get(tail)
        points = points_from_features(tail, sortie, str(meta.get("source") or self.default_source), features)
        n = self.sink.write(points)
        self.written += n
        self.last_message_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return n

    def status(self) -> Dict[str, Any]:
        return {"status": "ok" if self.mqtt_connected else "degraded", "mqttConnected": self.mqtt_connected,
                "received": self.received, "pointsWritten": self.written, "dropped": self.dropped,
                "lastMessageAt": self.last_message_at, "sortieByTail": self.sortie_by_tail}


def serve_health(ingester: Ingester, port: int) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps(ingester.status()).encode()
            self.send_response(200 if self.path in ("/", "/health") else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # silence default access log
            pass

    httpd = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main() -> int:
    configure(os.getenv("LOG_LEVEL", "INFO"))
    sink = InfluxSink(os.getenv("INFLUXDB_URL", "http://influxdb:8086"), os.environ["INFLUXDB_TOKEN"],
                      os.getenv("INFLUXDB_ORG", "vtol"), os.getenv("INFLUXDB_BUCKET", "flight_telemetry"), batched=True)
    ingester = Ingester(sink, os.getenv("SOURCE_TAG", "live"))
    host, port = os.getenv("MQTT_HOST", "mosquitto"), int(os.getenv("MQTT_PORT", "1883"))
    topics = [(t, 1) for t in os.getenv("MQTT_TOPICS", "vtol/+/telemetry,vtol/+/telemetry/+").split(",")]

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=os.getenv("MQTT_CLIENT_ID", "vtol-influx-ingester"),
                         protocol=mqtt.MQTTv5)

    def on_connect(c, userdata, flags, reason_code, properties=None):
        ingester.mqtt_connected = reason_code == 0 or getattr(reason_code, "is_failure", True) is False
        log(logger, "mqtt connected", host=host, port=port, topics=[t for t, _ in topics])
        c.subscribe(topics)

    def on_disconnect(c, userdata, flags, reason_code, properties=None):
        ingester.mqtt_connected = False
        log(logger, "mqtt disconnected", level=logging.WARNING, reason=str(reason_code))

    def on_message(c, userdata, msg):
        try:
            ingester.handle(msg.topic, msg.payload)
        except Exception as exc:  # noqa: BLE001
            ingester.dropped += 1
            log(logger, "message failed", level=logging.ERROR, topic=msg.topic, error=str(exc))

    client.on_connect, client.on_disconnect, client.on_message = on_connect, on_disconnect, on_message
    client.reconnect_delay_set(min_delay=1, max_delay=15)
    httpd = serve_health(ingester, int(os.getenv("INGEST_PORT", "8091")))
    log(logger, "ingester up", health_port=httpd.server_port, influx=sink.ping())
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    client.connect_async(host, port, keepalive=30)
    client.loop_start()
    while not stop.is_set():
        time.sleep(0.5)
    client.loop_stop()
    client.disconnect()
    httpd.shutdown()
    sink.close()
    log(logger, "ingester stopped", **ingester.status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
