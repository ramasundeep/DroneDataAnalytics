"""Web-Mercator (XYZ / "slippy map") tile maths used for planning and serving."""

from __future__ import annotations

import math
from dataclasses import dataclass

MAX_LAT = 85.05112878


@dataclass(frozen=True)
class TileRange:
    z: int
    x_min: int
    x_max: int
    y_min: int
    y_max: int

    @property
    def count(self) -> int:
        return (self.x_max - self.x_min + 1) * (self.y_max - self.y_min + 1)


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    lat = max(-MAX_LAT, min(MAX_LAT, lat))
    n = 2**z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def tile_range(min_lon: float, min_lat: float, max_lon: float, max_lat: float, z: int) -> TileRange:
    x0, y0 = lonlat_to_tile(min_lon, max_lat, z)  # north-west corner → smallest y
    x1, y1 = lonlat_to_tile(max_lon, min_lat, z)
    return TileRange(z, x0, x1, y0, y1)


def ground_resolution_m(lat: float, z: int, tile_px: int = 256) -> float:
    """Metres per pixel at latitude ``lat`` and zoom ``z``."""
    return float(156_543.033_92 * math.cos(math.radians(lat)) / (2**z) * 256 / tile_px)
