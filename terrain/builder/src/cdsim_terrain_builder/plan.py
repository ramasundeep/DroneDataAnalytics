"""Build plan for an area package: what will be fetched, produced and where.

``plan_area`` is pure: it reads the manifest and returns the ordered steps and
the output layout without touching the network. Phase 2 executes the plan.

Area package layout (a versioned tarball, ``<id>-<version>.tar.zst``)::

    <id>/
      area.yaml                 manifest (copied verbatim)
      package.json              build metadata: versions, source checksums, tool versions
      tiles/<layer>/{z}/{x}/{y}.<fmt>
      elevation/dem.tif         Cloud-Optimised GeoTIFF, EGM96 heights
      mesh/tileset.json         3D Tiles (if mesh.kind == 3d_tiles)
      mesh/heightmap.png        16-bit heightmap for UE5 Landscape (if heightmap_landscape)
      weather/default.json      default weather from the manifest
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cdsim_terrain_builder.tiles import ground_resolution_m, tile_range


@dataclass
class BuildStep:
    name: str
    detail: str
    phase_available: int  # roadmap phase in which the step is implemented


@dataclass
class AreaPlan:
    area_id: str
    version: str
    package_name: str
    steps: list[BuildStep] = field(default_factory=list)
    tile_counts: dict[str, int] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)

    @property
    def total_tiles(self) -> int:
        return sum(self.tile_counts.values())


def plan_area(area: dict[str, Any]) -> AreaPlan:
    b = area["bounds"]
    plan = AreaPlan(
        area_id=area["id"],
        version=area["version"],
        package_name=f"{area['id']}-{area['version']}.tar.zst",
    )
    sources = {s["id"]: s for s in area["sources"]}
    for s in area["sources"]:
        if s["kind"] == "flat":
            continue
        plan.steps.append(
            BuildStep(
                f"fetch:{s['id']}",
                f"{s['name']} ({s['kind']}, licence: {s['licence']}) → cache, verify sha256",
                2,
            )
        )
    plan.steps.append(BuildStep("clip", "clip all rasters/vectors to bounds (+1 tile margin)", 2))

    for layer in area["tile_layers"]:
        count = 0
        for z in range(layer["min_zoom"], layer["max_zoom"] + 1):
            count += tile_range(b["min_lon"], b["min_lat"], b["max_lon"], b["max_lat"], z).count
        plan.tile_counts[layer["id"]] = count
        res = ground_resolution_m((b["min_lat"] + b["max_lat"]) / 2, layer["max_zoom"])
        plan.steps.append(
            BuildStep(
                f"tiles:{layer['id']}",
                f"{layer['kind']} z{layer['min_zoom']}-{layer['max_zoom']} from "
                f"{layer['source']}: {count} tiles, {res:.2f} m/px at max zoom",
                2,
            )
        )
        plan.outputs.append(f"tiles/{layer['id']}/{{z}}/{{x}}/{{y}}.{layer.get('format', 'png')}")

    elev_src = sources[area["elevation"]["source"]]
    if elev_src["kind"] == "flat":
        plan.steps.append(
            BuildStep("elevation", f"flat plane at {area['elevation']['flat_elevation_m']} m", 0)
        )
    else:
        plan.steps.append(BuildStep("elevation", "reproject DEM → COG (EGM96)", 2))
        plan.outputs.append("elevation/dem.tif")

    mesh = area.get("mesh", {"kind": "none"})
    if mesh["kind"] == "3d_tiles":
        plan.steps.append(BuildStep("mesh", "photogrammetry/DEM → 3D Tiles", 2))
        plan.outputs.append("mesh/tileset.json")
    elif mesh["kind"] == "heightmap_landscape":
        plan.steps.append(BuildStep("mesh", "DEM → 16-bit heightmap for UE5 Landscape", 2))
        plan.outputs.append("mesh/heightmap.png")

    plan.outputs += ["area.yaml", "package.json", "weather/default.json"]
    plan.steps.append(BuildStep("package", f"write {plan.package_name} + upload to MinIO", 2))
    return plan
