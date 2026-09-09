"""Analytics service: scores all sorties on a schedule and after every ingested sortie, writes the
`health` feature to the Thing and health/anomaly points to InfluxDB.

    GET  /health      liveness + last run summary
    GET  /latest      full result of the last run
    POST /run         run now
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException

from common.ditto_client import DittoClient
from common.influx import InfluxSink
from common.logging_setup import configure, log

from .engine import Analyzer, RunResult, ditto_patch, influx_points
from .sources import InfluxSource, UlogSource

configure(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("analytics.service")
TAIL = os.getenv("TAIL_NUMBER", "VTOL-1")


class Runner:
    def __init__(self) -> None:
        self.sink = InfluxSink(os.getenv("INFLUXDB_URL", "http://influxdb:8086"), os.environ["INFLUXDB_TOKEN"],
                               os.getenv("INFLUXDB_ORG", "vtol"), os.getenv("INFLUXDB_BUCKET", "flight_telemetry"))
        self.ditto = DittoClient(os.getenv("DITTO_URL", "http://ditto-nginx"), os.getenv("DITTO_USER", "analytics"),
                                 os.environ["DITTO_PASSWORD"], os.getenv("THING_ID", "vtol.fleet:VTOL-1"))
        self.source_kind = os.getenv("ANALYTICS_SOURCE", "influx")
        self.ulog_glob = os.getenv("ULOG_GLOB", "/app/data/samples/*.ulg")
        self.interval = int(os.getenv("ANALYTICS_INTERVAL_S", "900"))
        self.last: Optional[RunResult] = None
        self.last_error: Optional[str] = None
        self.runs = 0
        self.lock = threading.Lock()
        self.started_at = datetime.now(timezone.utc)

    def run_once(self, reason: str) -> RunResult:
        with self.lock:
            t0 = time.time()
            counters = self.ditto.get_feature_properties("lifeCounters")
            components = self.ditto.get_attributes()["components"]
            source = InfluxSource(self.sink, TAIL) if self.source_kind == "influx" else UlogSource([self.ulog_glob], tail=TAIL)
            run = Analyzer().run(source, counters, components)
            self.ditto.merge_features(ditto_patch(run))
            n = self.sink.write(influx_points(run))
            self.last, self.last_error, self.runs = run, None, self.runs + 1
            log(logger, "analytics run complete", reason=reason, sorties=len(run.sorties), worst=run.worst_alert,
                flagged=run.summary()["flaggedSorties"], points=n, seconds=round(time.time() - t0, 2))
            return run

    def status(self) -> Dict[str, Any]:
        return {"status": "ok" if self.last_error is None else "degraded", "runs": self.runs, "lastError": self.last_error,
                "uptimeS": int((datetime.now(timezone.utc) - self.started_at).total_seconds()),
                "lastRun": None if self.last is None else {"ranAt": self.last.ran_at.isoformat(), "sorties": len(self.last.sorties),
                                                            "worstAlert": self.last.worst_alert,
                                                            "flaggedSorties": self.last.summary()["flaggedSorties"]}}


runner: Optional[Runner] = None
_trigger = threading.Event()


def _mqtt_listener() -> None:
    """Re-run when Ditto publishes a lifeCounters change (a sortie was ingested)."""
    host = os.getenv("MQTT_HOST")
    if not host:
        return
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        return
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="vtol-analytics", protocol=mqtt.MQTTv5)

    def on_connect(c, *_):
        c.subscribe(os.getenv("MQTT_EVENT_TOPIC", "vtol/+/events"), qos=1)

    def on_message(c, userdata, msg):
        try:
            evt = json.loads(msg.payload)
            path = str(evt.get("path", ""))
            if "lifeCounters" in path or (path == "/features" and "lifeCounters" in json.dumps(evt.get("value", {}))):
                _trigger.set()
        except Exception:  # noqa: BLE001
            pass

    client.on_connect, client.on_message = on_connect, on_message
    client.reconnect_delay_set(1, 15)
    client.connect_async(host, int(os.getenv("MQTT_PORT", "1883")), keepalive=30)
    client.loop_start()


async def _scheduler(app: FastAPI) -> None:
    loop = asyncio.get_running_loop()
    next_due = time.time() + 5
    while True:
        await asyncio.sleep(1.0)
        due = time.time() >= next_due
        if _trigger.is_set():
            _trigger.clear()
            await asyncio.sleep(3)             # let the ingester finish writing the sortie
            reason = "sortie-ingested"
        elif due:
            reason = "schedule"
        else:
            continue
        next_due = time.time() + runner.interval
        try:
            await loop.run_in_executor(None, runner.run_once, reason)
        except Exception as exc:  # noqa: BLE001
            runner.last_error = str(exc)
            log(logger, "analytics run failed", level=logging.ERROR, reason=reason, error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global runner
    runner = Runner()
    _mqtt_listener()
    task = asyncio.create_task(_scheduler(app))
    log(logger, "analytics service up", source=runner.source_kind, interval_s=runner.interval, influx=runner.sink.ping())
    yield
    task.cancel()
    runner.sink.close()


app = FastAPI(title="VTOL-1 analytics", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return runner.status()


@app.get("/latest")
async def latest():
    if runner.last is None:
        raise HTTPException(404, "no run yet")
    return runner.last.summary()


@app.post("/run")
async def run_now():
    loop = asyncio.get_running_loop()
    try:
        run = await loop.run_in_executor(None, runner.run_once, "manual")
    except Exception as exc:  # noqa: BLE001
        runner.last_error = str(exc)
        raise HTTPException(500, str(exc))
    return run.summary()
