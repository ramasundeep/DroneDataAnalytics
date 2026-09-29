from pathlib import Path

import pytest

from cdsim_common.paths import repo_root
from cdsim_terrain_builder.cli import EXIT_NOT_IMPLEMENTED, main
from cdsim_terrain_builder.plan import plan_area
from cdsim_terrain_builder.tiles import ground_resolution_m, lonlat_to_tile, tile_range

ROOT = repo_root()
assert ROOT is not None
HYD = ROOT / "terrain" / "areas" / "hyd_demo_01" / "area.yaml"
FLAT = ROOT / "terrain" / "areas" / "flat_test" / "area.yaml"


def test_known_tile() -> None:
    # z=0 is one tile; (0,0) lon/lat is the centre at z=1 → tile (1,1)
    assert lonlat_to_tile(0.0, 0.0, 0) == (0, 0)
    assert lonlat_to_tile(0.0, 0.0, 1) == (1, 1)
    assert lonlat_to_tile(-179.9, 85.0, 3) == (0, 0)


def test_tile_range_is_ordered() -> None:
    r = tile_range(78.29, 17.37, 78.311, 17.39, 16)
    assert r.x_min <= r.x_max and r.y_min <= r.y_max and r.count >= 1


def test_ground_resolution_equator() -> None:
    assert ground_resolution_m(0, 0) == pytest.approx(156_543.03392)


def test_plan_hyd() -> None:
    from cdsim_common.manifests import load_yaml

    plan = plan_area(load_yaml(HYD))
    assert plan.package_name == "hyd_demo_01-0.1.0.tar.zst"
    assert set(plan.tile_counts) == {"imagery", "terrain", "osm"}
    assert "elevation/dem.tif" in plan.outputs and "mesh/heightmap.png" in plan.outputs


def test_cli(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert main(["validate", str(FLAT)]) == 0
    assert main(["plan", str(HYD)]) == 0
    assert "total tiles" in capsys.readouterr().out
    assert main(["package", str(FLAT)]) == EXIT_NOT_IMPLEMENTED
    bad = tmp_path / "area.yaml"
    bad.write_text("schema_version: 1\nid: x\n")
    assert main(["validate", str(bad)]) == 1
