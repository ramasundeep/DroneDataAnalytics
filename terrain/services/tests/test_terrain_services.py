import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cdsim_common.config import Settings
from cdsim_common.paths import repo_root
from cdsim_terrain.apps import elevation_app, mesh_app, tiles_app, weather_app

ROOT = repo_root()
assert ROOT is not None


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # Copy the real flat_test manifest into a temp areas dir and fake a build.
    area_dir = tmp_path / "flat_test"
    (area_dir / "build" / "tiles" / "base" / "1" / "0").mkdir(parents=True)
    (area_dir / "build" / "mesh").mkdir(parents=True)
    (area_dir / "area.yaml").write_text(
        (ROOT / "terrain" / "areas" / "flat_test" / "area.yaml").read_text()
    )
    (area_dir / "build" / "package.json").write_text(json.dumps({"id": "flat_test"}))
    (area_dir / "build" / "tiles" / "base" / "1" / "0" / "1.png").write_bytes(b"\x89PNG")
    (area_dir / "build" / "mesh" / "tileset.json").write_text("{}")
    return Settings(areas_dir=tmp_path, schemas_dir=ROOT / "schemas" / "json")


def test_all_ready(settings: Settings) -> None:
    for factory in (tiles_app, mesh_app, elevation_app, weather_app):
        c = TestClient(factory(settings))
        assert c.get("/ready").status_code == 200
        assert c.get("/v1/areas").json() == [{"id": "flat_test", "version": "1.0.0", "built": True}]


def test_real_repo_areas_are_declared_not_built() -> None:
    c = TestClient(tiles_app(Settings()))
    status = {a["id"]: a["built"] for a in c.get("/v1/areas").json()}
    assert status == {"flat_test": False, "hyd_demo_01": False}
    assert "not built" in c.get("/v1/tiles/hyd_demo_01/imagery/10/1/1.webp").json()["detail"]


def test_tiles(settings: Settings) -> None:
    c = TestClient(tiles_app(settings))
    r = c.get("/v1/tiles/flat_test/base/1/0/1.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert c.get("/v1/tiles/flat_test/base/1/0/2.png").status_code == 404
    assert c.get("/v1/tiles/flat_test/base/1/0/1.exe").status_code == 400
    assert c.get("/v1/tiles/nope/base/1/0/1.png").status_code == 404


def test_mesh_no_traversal(settings: Settings) -> None:
    c = TestClient(mesh_app(settings))
    assert c.get("/v1/mesh/flat_test/tileset.json").status_code == 200
    assert c.get("/v1/mesh/flat_test/../package.json").status_code == 404
    assert c.get("/v1/mesh/flat_test/%2e%2e/package.json").status_code == 404


def test_elevation_flat(settings: Settings) -> None:
    c = TestClient(elevation_app(settings))
    body = c.get("/v1/elevation", params={"lat": 17.40, "lon": 78.50}).json()
    assert body["elevation_msl_m"] == 500.0 and body["source"] == "flat"
    assert c.get("/v1/elevation", params={"lat": 0, "lon": 0}).status_code == 404


def test_elevation_dem_is_phase_2() -> None:
    c = TestClient(elevation_app(Settings()))
    r = c.get("/v1/elevation", params={"lat": 17.38, "lon": 78.30})
    assert r.status_code == 501


def test_weather(settings: Settings) -> None:
    c = TestClient(weather_app(settings))
    assert c.get("/v1/weather/flat_test").json()["wind_speed_mps"] == 0.0
    assert c.get("/v1/weather/unknown").status_code == 404
