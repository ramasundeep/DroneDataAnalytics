"""Read-only catalogue of platforms, areas, scenarios and rubrics.

Loaded once from the manifest directories at startup (mounted read-only in
Docker). Invalid manifests are logged and excluded, and surface in /ready as
a failed ``manifests`` check so they cannot go unnoticed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from cdsim_common.config import Settings
from cdsim_common.manifests import ManifestError, ManifestSet, discover

log = logging.getLogger(__name__)


class Bounds(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


class AreaSummary(BaseModel):
    id: str
    name: str
    version: str
    classification: str
    landing_pads: int
    bounds: Bounds


class ScenarioSummary(BaseModel):
    id: str
    name: str
    session_kind: str
    area_id: str
    rubric_id: str | None = None


@dataclass
class Catalogue:
    manifests: ManifestSet
    errors: list[ManifestError] = field(default_factory=list)

    @classmethod
    def load(cls, settings: Settings) -> Catalogue:
        found, errors = discover(
            settings.schemas_dir,
            platforms_dir=settings.platforms_dir,
            areas_dir=settings.areas_dir,
            rubrics_dir=settings.rubrics_dir,
            scenarios_dir=settings.scenarios_dir,
        )
        for err in errors:
            log.error("invalid manifest %s", err)
        return cls(found, errors)

    def platforms(self) -> list[dict[str, Any]]:
        return [
            {
                "id": p["identity"]["id"],
                "name": p["identity"]["name"],
                "class": p["class"],
                "status": p["identity"]["status"],
                "version": p["identity"]["version"],
            }
            for p in self.manifests.platforms.values()
        ]

    def areas(self) -> list[AreaSummary]:
        return [
            AreaSummary(
                id=a["id"],
                name=a["name"],
                version=a["version"],
                classification=a.get("classification", "public"),
                landing_pads=len(a.get("landing_pads", [])),
                bounds=Bounds(**a["bounds"]),
            )
            for a in self.manifests.areas.values()
        ]

    def scenarios(self) -> list[ScenarioSummary]:
        return [
            ScenarioSummary(
                id=s["id"],
                name=s["name"],
                session_kind=s["session_kind"],
                area_id=s["area_id"],
                rubric_id=s.get("rubric_id"),
            )
            for s in self.manifests.scenarios.values()
        ]
