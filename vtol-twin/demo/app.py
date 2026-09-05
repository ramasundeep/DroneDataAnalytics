"""FastAPI demo service: flies synthetic sorties against the in-memory twin and streams state to the UI."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import simulator as sim
from .logging_setup import configure, log
from .publisher import MqttPublisher
from .twin import ALERT_ORDER, InMemoryTwin, SortieStats

configure(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("demo")
STATIC = Path(__file__).parent / "static"
TAIL = os.getenv("TAIL_NUMBER", "VTOL-1")


class Controller:
    """Owns the twin, the running sortie (if any) and the SSE subscribers."""

    def __init__(self) -> None:
        self.twin = InMemoryTwin()
        self.publisher = MqttPublisher(os.getenv("MQTT_HOST") or None, int(os.getenv("MQTT_PORT", "1883")), TAIL)
        self.speed = float(os.getenv("DEMO_SPEED", "20"))
        self.task: Optional[asyncio.Task] = None
        self.current: Optional[dict] = None       # sortie in progress (id, phase, t, total, degradation)
        self.history: List[dict] = []              # last N samples for sparklines
        self.seq = 0
        self.subscribers: List[asyncio.Queue] = []
        self.started_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------ sorties
    def start_sortie(self, degradation: str, severity: float, cruise_seconds: int, seed: Optional[int]) -> dict:
        if self.task and not self.task.done():
            raise HTTPException(409, "a sortie is already in progress")
        if degradation not in sim.DEGRADATIONS:
            raise HTTPException(422, f"degradation must be one of {list(sim.DEGRADATIONS)}")
        self.seq += 1
        cfg = sim.SortieConfig(
            sortie_id=sim.next_sortie_id(datetime.now(timezone.utc), self.seq, TAIL),
            cruise_seconds=cruise_seconds, degradation=degradation, severity=severity,
            seed=seed if seed is not None else self.seq,
            baseline=self.twin.wear.get(degradation, 0.0),
        )
        self.current = {"sortieId": cfg.sortie_id, "phase": "preflight", "t": 0,
                        "total": sim.total_seconds(cfg), "degradation": degradation, "severity": severity}
        self.history = []
        self.task = asyncio.create_task(self._fly(cfg))
        log(logger, "sortie started", sortie=cfg.sortie_id, degradation=degradation, severity=severity,
            total_s=self.current["total"], speed=self.speed)
        return self.current

    async def _fly(self, cfg: sim.SortieConfig) -> None:
        s = sim.SortieSimulator(cfg)
        stats = SortieStats()
        try:
            for sample in s:
                self.twin.merge_features(sample.features)
                stats.add(sample.features)
                self.publisher.publish_features(sample.features)
                self.current.update({"phase": sample.phase, "t": sample.t})
                self.history.append({"t": sample.t, "phase": sample.phase,
                                     "rpm": sample.features["engine"]["rpm"],
                                     "egtC": sample.features["engine"]["egtC"],
                                     "rmsTotal": sample.features["vibration"]["rmsTotal"],
                                     "servo3CurrentA": sample.features["actuation"]["servo3CurrentA"],
                                     "busVoltageV": sample.features["power"]["busVoltageV"],
                                     "altAglM": sample.features["flightState"]["altAglM"]})
                self.history = self.history[-900:]
                await self.broadcast("tick")
                await asyncio.sleep(1.0 / max(self.speed, 0.1))
            record = self.twin.close_sortie(cfg.sortie_id, s.flight_hours, stats, cfg.degradation, s.wear_added)
            self.publisher.publish_feature("lifeCounters", self.twin.features["lifeCounters"]["properties"])
            self.publisher.publish_feature("health", self.twin.features["health"]["properties"])
            log(logger, "sortie complete", **record,
                release=self.twin.features["health"]["properties"]["aircraft"]["releaseStatus"])
        except asyncio.CancelledError:
            log(logger, "sortie aborted", sortie=cfg.sortie_id)
            raise
        finally:
            self.current = None
            await self.broadcast("sortie-end")

    async def abort(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def reset(self) -> None:
        await self.abort()
        self.twin.reset()
        self.history = []
        self.seq = 0
        await self.broadcast("reset")

    # ---------------------------------------------------------------- SSE
    def snapshot(self) -> dict:
        snap = self.twin.snapshot()
        snap.update({
            "sortie": self.current, "history": self.history, "speed": self.speed,
            "mqtt": self.publisher.status(), "degradations": sim.DEGRADATIONS, "tail": TAIL,
            "serverTime": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        })
        return snap

    async def broadcast(self, kind: str) -> None:
        payload = json.dumps({"kind": kind, "state": self.snapshot()}, default=str)
        for q in list(self.subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(payload)


ctl = Controller()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log(logger, "demo service up", tail=TAIL, speed=ctl.speed, mqtt=ctl.publisher.status())
    yield
    await ctl.abort()
    ctl.publisher.close()


app = FastAPI(title="VTOL-1 twin demo", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class StartRequest(BaseModel):
    degradation: str = "none"
    severity: float = Field(1.0, ge=0.0, le=2.0)
    cruiseSeconds: int = Field(480, ge=30, le=3600)
    seed: Optional[int] = None


class SignOffRequest(BaseModel):
    action: str = "repaired"
    signedOffBy: str = "operator"
    manHours: float = Field(1.0, ge=0.0)
    partsConsumed: List[str] = []


class SpeedRequest(BaseModel):
    speed: float = Field(..., ge=0.5, le=200)


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "uptimeS": int((datetime.now(timezone.utc) - ctl.started_at).total_seconds()),
            "sortieInProgress": ctl.current is not None, "mqtt": ctl.publisher.status()}


@app.get("/api/state")
async def state():
    return ctl.snapshot()


@app.get("/api/events")
async def events():
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    ctl.subscribers.append(q)

    async def gen():
        try:
            yield f"data: {json.dumps({'kind': 'snapshot', 'state': ctl.snapshot()}, default=str)}\n\n"
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            ctl.subscribers.remove(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/sortie/start")
async def start(req: StartRequest):
    return ctl.start_sortie(req.degradation, req.severity, req.cruiseSeconds, req.seed)


@app.post("/api/sortie/abort")
async def abort():
    await ctl.abort()
    return {"ok": True}


@app.post("/api/speed")
async def speed(req: SpeedRequest):
    ctl.speed = req.speed
    await ctl.broadcast("speed")
    return {"speed": ctl.speed}


@app.post("/api/reset")
async def reset():
    await ctl.reset()
    return {"ok": True}


@app.get("/api/workorders")
async def workorders(status: Optional[str] = None):
    return [w for w in ctl.twin.work_orders if status is None or w["status"] == status]


@app.post("/api/workorders/{wo_id}/signoff")
async def signoff(wo_id: str, req: SignOffRequest):
    try:
        wo = ctl.twin.sign_off(wo_id, req.action, req.signedOffBy, req.manHours, req.partsConsumed)
    except KeyError:
        raise HTTPException(404, f"{wo_id} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    log(logger, "work order signed off", wo=wo_id, action=req.action, by=req.signedOffBy,
        release=ctl.twin.features["health"]["properties"]["aircraft"]["releaseStatus"])
    await ctl.broadcast("workorder")
    return wo
