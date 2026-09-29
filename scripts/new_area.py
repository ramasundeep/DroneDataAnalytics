#!/usr/bin/env python3
"""Scaffold a new area package manifest: ``make new-area id=<area_id>``.

Creates terrain/areas/<id>/area.yaml with a small placeholder box around a
given centre (``--lat/--lon``, default: the flat_test origin) and validates
it. Refuses to overwrite. Spec: docs/03_DIGITAL_TERRAIN_TWINS.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from cdsim_common.manifests import ManifestError, ManifestKind, validate_file
from cdsim_common.paths import repo_root

ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,40}$")

TEMPLATE = """# {aid} — area package manifest (scaffolded; edit every value).
# Spec: docs/03_DIGITAL_TERRAIN_TWINS.md. Use public data only unless the
# area is classified restricted and handled per docs/09_DEPLOYMENT_OFFLINE.md.

schema_version: 1
id: {aid}
name: {name}
version: 0.1.0
classification: public
description: TODO describe the area and why it exists.

bounds: {{min_lat: {min_lat:.4f}, min_lon: {min_lon:.4f}, max_lat: {max_lat:.4f}, max_lon: {max_lon:.4f}}}
origin: {{lat_deg: {lat:.4f}, lon_deg: {lon:.4f}, alt_msl_m: 0.0}}

crs:
  geographic: EPSG:4326
  projected: EPSG:32644      # TODO: UTM zone of the area
  vertical_datum: EGM96

sources:
  - {{id: dem_cop30, kind: dem, name: Copernicus DEM GLO-30, licence: Copernicus DEM licence, resolution_m: 30}}
  - {{id: img_s2, kind: imagery, name: Sentinel-2 L2A mosaic, licence: Copernicus Sentinel data terms, resolution_m: 10}}

tile_layers:
  - {{id: imagery, kind: raster, source: img_s2, min_zoom: 10, max_zoom: 16, format: webp}}
  - {{id: terrain, kind: terrain_rgb, source: dem_cop30, min_zoom: 8, max_zoom: 14, format: png}}

elevation:
  source: dem_cop30
  resolution_m: 30

mesh:
  kind: heightmap_landscape
  source: dem_cop30

landing_pads:
  - {{id: pad_home, name: Home pad, position: {{lat_deg: {lat:.4f}, lon_deg: {lon:.4f}}}, heading_deg: 0, size_m: 2.0, marker: apriltag, marker_id: 0}}

weather:
  wind_speed_mps: 0.0
  wind_from_deg: 0
"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--lat", type=float, default=17.4)
    ap.add_argument("--lon", type=float, default=78.5)
    ap.add_argument("--half-size-deg", type=float, default=0.01)
    args = ap.parse_args(argv)
    if not ID_RE.match(args.id):
        print("id must be lowercase letters, digits, underscores (3-41 chars)")
        return 2
    root = repo_root(Path(__file__))
    assert root is not None
    adir = root / "terrain" / "areas" / args.id
    if adir.exists():
        print(f"refusing to overwrite existing {adir.relative_to(root)}")
        return 1
    h = args.half_size_deg
    adir.mkdir(parents=True)
    path = adir / "area.yaml"
    path.write_text(
        TEMPLATE.format(
            aid=args.id,
            name=args.id.replace("_", " ").title(),
            lat=args.lat,
            lon=args.lon,
            min_lat=args.lat - h,
            max_lat=args.lat + h,
            min_lon=args.lon - h,
            max_lon=args.lon + h,
        ),
        encoding="utf-8",
    )
    try:
        validate_file(path, ManifestKind.AREA, root / "schemas" / "json")
    except ManifestError as exc:
        print(f"scaffold created but invalid: {exc}")
        return 1
    print(f"created {path.relative_to(root)} — edit it, then `make schemas`")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
