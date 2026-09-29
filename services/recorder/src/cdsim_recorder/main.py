"""CD Sim recorder (FastAPI).

Phase 0 scope: ingest of discrete events (``POST /v1/events``), ordered
read-back (``GET /v1/sessions/{id}/events``) and live fan-out on Redis. This
is the foundation of replay and assessment. Telemetry, control-input and
audio ingest arrive in Phase 1 (telemetry/controls) and Phase 3 (audio); their
tables already exist in db/001_init.sql.

Run locally:  uvicorn --factory cdsim_recorder.main:create_app --port 8001
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI, Request
from pydantic import BaseModel

from cdsim_common.config import Settings, get_settings
from cdsim_common.deps import minio_check, postgres_check, redis_check
from cdsim_common.events import Event, EventBatch, EventFamily
from cdsim_common.health import health_router
from cdsim_recorder import __version__
from cdsim_recorder.store import (
    EventPublisher,
    EventStore,
    PostgresEventStore,
    RedisPublisher,
)

SERVICE = "recorder"
log = logging.getLogger(__name__)


class IngestResult(BaseModel):
    received: int
    stored: int


def create_app(
    settings: Settings | None = None,
    store: EventStore | None = None,
    publisher: EventPublisher | None = None,
) -> FastAPI:
    """Build the app. Passing ``store``/``publisher`` (tests) skips infra checks."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    use_infra = store is None
    app = FastAPI(title="CD Sim Recorder", version=__version__, docs_url=None, redoc_url=None)
    app.state.store = store or PostgresEventStore(settings.db_dsn)
    app.state.publisher = publisher or RedisPublisher(settings.redis_url)
    checks = (
        {
            "postgres": postgres_check(settings),
            "redis": redis_check(settings),
            "minio": minio_check(settings, settings.recordings_bucket),
        }
        if use_infra
        else {}
    )
    app.include_router(health_router(SERVICE, __version__, checks))
    app.include_router(_router())
    return app


def _router() -> APIRouter:
    r = APIRouter(prefix="/v1", tags=["events"])

    @r.post("/events", response_model=IngestResult)
    async def ingest(batch: EventBatch, request: Request) -> IngestResult:
        store: EventStore = request.app.state.store
        publisher: EventPublisher = request.app.state.publisher
        stored = await store.write(batch.events)
        try:
            await publisher.publish(batch.events)
        except Exception:  # live fan-out is best-effort; storage is the record
            log.exception("live publish failed; events are stored")
        return IngestResult(received=len(batch.events), stored=stored)

    @r.get("/sessions/{session_id}/events", response_model=list[Event])
    async def read(
        session_id: str,
        request: Request,
        family: EventFamily | None = None,
        from_us: int | None = None,
        to_us: int | None = None,
    ) -> list[Event]:
        store: EventStore = request.app.state.store
        return await store.read(session_id, family, from_us, to_us)

    return r
