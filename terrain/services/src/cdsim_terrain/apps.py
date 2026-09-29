"""The four offline terrain services, each a small FastAPI app.

One image, four entrypoints (``uvicorn --factory cdsim_terrain.apps:<name>``):

* ``tiles_app``     — XYZ raster / terrain-RGB / vector tiles from built packages
* ``mesh_app``      — 3D Tiles tilesets and UE5 heightmaps from built packages
* ``elevation_app`` — point elevation queries (flat areas now; DEM in Phase 2)
* ``weather_app``   — default weather + scenario store per area

All read the areas directory read-only; all work fully offline. See
docs/03_DIGITAL_TERRAIN_TWINS.md and docs/ADR/0017-own-lightweight-terrain-services.md.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from cdsim_common.config import Settings, get_settings
from cdsim_common.health import Check, health_router
from cdsim_terrain import __version__
from cdsim_terrain.registry import AreaRegistry, AreaStatus

_SAFE = re.compile(r"^[a-z][a-z0-9_]*$")
_TILE_EXT = {"png", "webp", "jpg", "pbf"}
_MEDIA = {
    "png": "image/png",
    "webp": "image/webp",
    "jpg": "image/jpeg",
    "pbf": "application/x-protobuf",
    "json": "application/json",
}


def _base(name: str, settings: Settings | None) -> tuple[FastAPI, AreaRegistry]:
    settings = settings or get_settings()
    registry = AreaRegistry.load(settings)

    async def manifests_ok() -> None:
        if registry.errors:
            raise RuntimeError(f"{len(registry.errors)} invalid area manifest(s)")

    async def areas_dir_ok() -> None:
        if not settings.areas_dir.is_dir():
            raise RuntimeError(f"areas dir {settings.areas_dir} not mounted")

    checks: dict[str, Check] = {"areas_dir": areas_dir_ok, "manifests": manifests_ok}
    app = FastAPI(
        title=f"CD Sim terrain — {name}", version=__version__, docs_url=None, redoc_url=None
    )
    app.state.registry = registry
    app.include_router(health_router(f"terrain-{name}", __version__, checks))

    @app.get("/v1/areas", response_model=list[AreaStatus], tags=["areas"])
    async def areas() -> list[AreaStatus]:
        return registry.status()

    return app, registry


def _require_area(registry: AreaRegistry, area_id: str) -> dict[str, Any]:
    if not _SAFE.match(area_id) or area_id not in registry.areas:
        raise HTTPException(404, f"area '{area_id}' not found")
    return registry.areas[area_id]


def _require_built(registry: AreaRegistry, area_id: str) -> Path:
    _require_area(registry, area_id)
    if not registry.is_built(area_id):
        raise HTTPException(
            404,
            f"area '{area_id}' is declared but not built; run `cdsim-area package` (Phase 2)",
        )
    return registry.build_dir(area_id)


# ------------------------------------------------------------------- tiles


def tiles_app(settings: Settings | None = None) -> FastAPI:
    app, registry = _base("tiles", settings)
    r = APIRouter(prefix="/v1/tiles", tags=["tiles"])

    @r.get("/{area_id}/{layer}/{z}/{x}/{y}.{ext}")
    async def tile(area_id: str, layer: str, z: int, x: int, y: int, ext: str) -> FileResponse:
        build = _require_built(registry, area_id)
        if not _SAFE.match(layer) or ext not in _TILE_EXT or min(z, x, y) < 0:
            raise HTTPException(400, "bad tile request")
        path = build / "tiles" / layer / str(z) / str(x) / f"{y}.{ext}"
        if not path.is_file():
            raise HTTPException(404, "tile not in package")
        return FileResponse(path, media_type=_MEDIA[ext])

    app.include_router(r)
    return app


# -------------------------------------------------------------------- mesh


def mesh_app(settings: Settings | None = None) -> FastAPI:
    app, registry = _base("mesh", settings)
    r = APIRouter(prefix="/v1/mesh", tags=["mesh"])

    @r.get("/{area_id}/{path:path}")
    async def mesh_file(area_id: str, path: str) -> FileResponse:
        mesh_root = (_require_built(registry, area_id) / "mesh").resolve()
        target = (mesh_root / path).resolve()
        if not target.is_relative_to(mesh_root) or not target.is_file():
            raise HTTPException(404, "mesh file not in package")
        media = _MEDIA.get(target.suffix.lstrip("."), "application/octet-stream")
        return FileResponse(target, media_type=media)

    app.include_router(r)
    return app


# --------------------------------------------------------------- elevation


class Elevation(BaseModel):
    area_id: str
    lat_deg: float
    lon_deg: float
    elevation_msl_m: float
    source: str


def elevation_app(settings: Settings | None = None) -> FastAPI:
    app, registry = _base("elevation", settings)

    @app.get("/v1/elevation", response_model=Elevation, tags=["elevation"])
    async def elevation(
        lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)
    ) -> Elevation:
        area = registry.area_at(lat, lon)
        if area is None:
            raise HTTPException(404, "no loaded area covers this point")
        elev = area["elevation"]
        src = next(s for s in area["sources"] if s["id"] == elev["source"])
        if src["kind"] == "flat":
            return Elevation(
                area_id=area["id"],
                lat_deg=lat,
                lon_deg=lon,
                elevation_msl_m=float(elev["flat_elevation_m"]),
                source="flat",
            )
        raise HTTPException(
            501, "DEM sampling is scheduled for Phase 2 (docs/03_DIGITAL_TERRAIN_TWINS.md)"
        )

    return app


# ----------------------------------------------------------------- weather


def weather_app(settings: Settings | None = None) -> FastAPI:
    app, registry = _base("weather", settings)

    @app.get("/v1/weather/{area_id}", tags=["weather"])
    async def weather(area_id: str) -> dict[str, Any]:
        area = _require_area(registry, area_id)
        return {"area_id": area_id, "source": "area_default", **area["weather"]}

    return app
