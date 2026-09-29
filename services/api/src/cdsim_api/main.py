"""CD Sim platform API (FastAPI).

Phase 0 scope: health, version, system-wide health aggregation, and a
read-only catalogue of platforms / areas / scenarios / rubrics loaded from the
manifest directories. Session, trainee, scoring and replay routes exist as
explicit 501 stubs naming the roadmap phase that delivers them
(docs/10_ROADMAP.md), so the API surface is visible from day one.

Run locally:  uvicorn --factory cdsim_api.main:create_app --reload --port 8000
"""

from __future__ import annotations

import logging
from typing import Any, NoReturn

from fastapi import APIRouter, FastAPI, HTTPException, Request

from cdsim_api import __version__
from cdsim_api.catalogue import AreaSummary, Catalogue, ScenarioSummary
from cdsim_api.system import SystemHealth, probe_all
from cdsim_common.config import Settings, get_settings
from cdsim_common.deps import minio_check, postgres_check, redis_check
from cdsim_common.health import Check, health_router

SERVICE = "api"


def create_app(settings: Settings | None = None, with_infra_checks: bool = True) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    catalogue = Catalogue.load(settings)

    async def manifests_ok() -> None:
        if catalogue.errors:
            raise RuntimeError(f"{len(catalogue.errors)} invalid manifest(s); see logs")

    checks: dict[str, Check] = {"manifests": manifests_ok}
    if with_infra_checks:
        checks |= {
            "postgres": postgres_check(settings),
            "redis": redis_check(settings),
            "minio": minio_check(settings),
        }

    app = FastAPI(
        docs_url=None,  # Swagger/ReDoc load JS from a CDN: offline-first
        redoc_url=None,
        title="CD Sim API",
        version=__version__,
        description="Chakravyuha Dynamics CD Sim platform API. Offline-first.",
    )
    app.state.settings = settings
    app.state.catalogue = catalogue
    app.include_router(health_router(SERVICE, __version__, checks))
    app.include_router(_v1_router())
    return app


def _catalogue(request: Request) -> Catalogue:
    cat: Catalogue = request.app.state.catalogue
    return cat


def _not_yet(phase: int, what: str) -> NoReturn:
    raise HTTPException(
        status_code=501,
        detail=f"{what} is not implemented yet — scheduled for Phase {phase} "
        "(docs/10_ROADMAP.md)",
    )


def _v1_router() -> APIRouter:
    r = APIRouter(prefix="/v1")

    @r.get("/version", tags=["system"])
    async def version() -> dict[str, str]:
        return {"service": SERVICE, "version": __version__, "roadmap_phase": "0"}

    @r.get("/system/health", response_model=SystemHealth, tags=["system"])
    async def system_health(request: Request) -> SystemHealth:
        settings: Settings = request.app.state.settings
        return await probe_all(settings.service_url_map())

    # ---------------------------------------------------------- catalogue
    @r.get("/platforms", tags=["catalogue"])
    async def list_platforms(request: Request) -> list[dict[str, Any]]:
        return _catalogue(request).platforms()

    @r.get("/platforms/{platform_id}", tags=["catalogue"])
    async def get_platform(platform_id: str, request: Request) -> dict[str, Any]:
        found = _catalogue(request).manifests.platforms.get(platform_id)
        if found is None:
            raise HTTPException(404, f"platform '{platform_id}' not found")
        return found

    @r.get("/areas", response_model=list[AreaSummary], tags=["catalogue"])
    async def list_areas(request: Request) -> list[AreaSummary]:
        return _catalogue(request).areas()

    @r.get("/areas/{area_id}", tags=["catalogue"])
    async def get_area(area_id: str, request: Request) -> dict[str, Any]:
        found = _catalogue(request).manifests.areas.get(area_id)
        if found is None:
            raise HTTPException(404, f"area '{area_id}' not found")
        return found

    @r.get("/scenarios", response_model=list[ScenarioSummary], tags=["catalogue"])
    async def list_scenarios(request: Request) -> list[ScenarioSummary]:
        return _catalogue(request).scenarios()

    @r.get("/scenarios/{scenario_id}", tags=["catalogue"])
    async def get_scenario(scenario_id: str, request: Request) -> dict[str, Any]:
        found = _catalogue(request).manifests.scenarios.get(scenario_id)
        if found is None:
            raise HTTPException(404, f"scenario '{scenario_id}' not found")
        return found

    @r.get("/rubrics", tags=["catalogue"])
    async def list_rubrics(request: Request) -> list[dict[str, Any]]:
        return [
            {"id": k, "name": v["name"], "version": v["version"]}
            for k, v in _catalogue(request).manifests.rubrics.items()
        ]

    # ---------------------------------------------------- later phases (501)
    @r.get("/sessions", tags=["sessions"])
    async def list_sessions() -> None:
        _not_yet(1, "Session listing")

    @r.post("/sessions", tags=["sessions"])
    async def create_session() -> None:
        _not_yet(4, "Session creation from the console")

    @r.get("/sessions/{session_id}/replay", tags=["replay"])
    async def replay(session_id: str) -> None:
        _not_yet(1, "Replay")

    @r.get("/sessions/{session_id}/score", tags=["scoring"])
    async def score(session_id: str) -> None:
        _not_yet(3, "Session scoring")

    @r.get("/trainees", tags=["trainees"])
    async def trainees() -> None:
        _not_yet(4, "Trainee records")

    return r
