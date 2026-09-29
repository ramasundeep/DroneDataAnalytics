"""Discovery of area manifests and their built packages on local disk.

Each terrain service mounts the areas directory read-only. An area is
*declared* when ``<areas_dir>/<id>/area.yaml`` is valid, and *built* when
the unpacked package exists at ``<areas_dir>/<id>/build/`` (produced by
``cdsim-area package`` in Phase 2). Nothing is ever fetched over the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from cdsim_common.config import Settings
from cdsim_common.manifests import ManifestError, discover


class AreaStatus(BaseModel):
    id: str
    version: str
    built: bool


@dataclass
class AreaRegistry:
    areas_dir: Path
    areas: dict[str, dict[str, Any]]
    errors: list[ManifestError]

    @classmethod
    def load(cls, settings: Settings) -> AreaRegistry:
        found, errors = discover(settings.schemas_dir, areas_dir=settings.areas_dir)
        return cls(settings.areas_dir, found.areas, errors)

    def build_dir(self, area_id: str) -> Path:
        return self.areas_dir / area_id / "build"

    def is_built(self, area_id: str) -> bool:
        return (self.build_dir(area_id) / "package.json").is_file()

    def status(self) -> list[AreaStatus]:
        return [
            AreaStatus(id=a["id"], version=a["version"], built=self.is_built(a["id"]))
            for a in self.areas.values()
        ]

    def area_at(self, lat: float, lon: float) -> dict[str, Any] | None:
        for a in self.areas.values():
            b = a["bounds"]
            if b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]:
                return a
        return None
