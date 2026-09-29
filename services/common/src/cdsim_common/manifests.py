"""Load and validate CD Sim manifests (platform, area, rubric, scenario).

Two layers of validation:

1. **Schema** — the YAML is checked against ``schemas/json/<kind>.schema.json``.
2. **Semantic** — cross-references the schema cannot express: ids match their
   directory, failure modes target real actuators/sensors, procedure steps use
   declared parts/tools, scenarios reference areas/platforms/pads/rubrics that
   exist.

``scripts/validate_manifests.py`` (``make schemas``) runs both over the repo;
services call ``load_*`` at startup so a bad manifest fails loudly, early.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

Manifest = dict[str, Any]


class ManifestKind(str, Enum):
    PLATFORM = "platform"
    AREA = "area"
    RUBRIC = "rubric"
    SCENARIO = "scenario"


class ManifestError(ValueError):
    """Raised when a manifest fails schema or semantic validation."""

    def __init__(self, path: Path | str, errors: list[str]) -> None:
        self.path = str(path)
        self.errors = errors
        super().__init__(f"{path}: " + "; ".join(errors))


@dataclass
class ManifestSet:
    """Everything discovered under the data directories, keyed by id."""

    platforms: dict[str, Manifest] = field(default_factory=dict)
    areas: dict[str, Manifest] = field(default_factory=dict)
    rubrics: dict[str, Manifest] = field(default_factory=dict)
    scenarios: dict[str, Manifest] = field(default_factory=dict)


# ------------------------------------------------------------------ loading


def load_yaml(path: Path) -> Manifest:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ManifestError(path, ["top level must be a mapping"])
    return data


@lru_cache(maxsize=8)
def _validator(schemas_dir: Path, kind: ManifestKind) -> Draft202012Validator:
    schema_path = schemas_dir / f"{kind.value}.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def schema_errors(data: Manifest, kind: ManifestKind, schemas_dir: Path) -> list[str]:
    validator = _validator(schemas_dir.resolve(), kind)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]


# ---------------------------------------------------------- semantic checks


def platform_semantic_errors(data: Manifest, dir_name: str | None = None) -> list[str]:
    errs: list[str] = []
    pid = data["identity"]["id"]
    if dir_name is not None and pid != dir_name:
        errs.append(f"identity.id '{pid}' must equal directory name '{dir_name}'")
    if data["ue_plugin"] != f"CDSimPlatform_{pid}":
        errs.append(f"ue_plugin must be 'CDSimPlatform_{pid}'")

    actuators = [a["id"] for a in data["propulsion"]["actuators"]]
    sensors = [s["id"] for s in data["sensors"]]
    errs += _duplicates("propulsion.actuators", actuators)
    errs += _duplicates("sensors", sensors)
    channels = [a["output_channel"] for a in data["propulsion"]["actuators"]]
    errs += _duplicates("propulsion.actuators output_channel", [str(c) for c in channels])

    for fm in data["failure_modes"]:
        eff = fm["effect"]
        target = eff.get("target")
        if eff["type"] == "actuator_scale" and target not in actuators:
            errs.append(f"failure_mode {fm['id']}: actuator '{target}' not declared")
        if eff["type"] in ("sensor_dropout", "sensor_bias") and target not in sensors:
            errs.append(f"failure_mode {fm['id']}: sensor '{target}' not declared")
    errs += _duplicates("failure_modes", [fm["id"] for fm in data["failure_modes"]])

    maint = data["maintenance"]
    parts = {p["id"] for p in maint["parts"]}
    tools = {t["id"] for t in maint["tools"]}
    for proc in maint["procedures"]:
        errs += _duplicates(f"procedure {proc['id']} steps", [s["id"] for s in proc["steps"]])
        for step in proc["steps"]:
            where = f"procedure {proc['id']} step {step['id']}"
            if "part_id" in step and step["part_id"] not in parts:
                errs.append(f"{where}: part '{step['part_id']}' not declared")
            if "tool_id" in step and step["tool_id"] not in tools:
                errs.append(f"{where}: tool '{step['tool_id']}' not declared")
            if "part_id" not in step and "anchor" not in step:
                errs.append(f"{where}: needs part_id or anchor for the maintainer module")
    return errs


def area_semantic_errors(data: Manifest, dir_name: str | None = None) -> list[str]:
    errs: list[str] = []
    if dir_name is not None and data["id"] != dir_name:
        errs.append(f"id '{data['id']}' must equal directory name '{dir_name}'")
    b = data["bounds"]
    if not (b["min_lat"] < b["max_lat"] and b["min_lon"] < b["max_lon"]):
        errs.append("bounds: min must be < max")

    def inside(lat: float, lon: float) -> bool:
        return b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]

    o = data["origin"]
    if not inside(o["lat_deg"], o["lon_deg"]):
        errs.append("origin lies outside bounds")
    sources = {s["id"]: s for s in data["sources"]}
    for layer in data["tile_layers"]:
        if layer["source"] not in sources:
            errs.append(f"tile_layer {layer['id']}: unknown source '{layer['source']}'")
        if layer["min_zoom"] > layer["max_zoom"]:
            errs.append(f"tile_layer {layer['id']}: min_zoom > max_zoom")
    elev = data["elevation"]
    if elev["source"] not in sources:
        errs.append(f"elevation: unknown source '{elev['source']}'")
    elif sources[elev["source"]]["kind"] == "flat" and "flat_elevation_m" not in elev:
        errs.append("elevation: flat source requires flat_elevation_m")
    for pad in data.get("landing_pads", []):
        if not inside(pad["position"]["lat_deg"], pad["position"]["lon_deg"]):
            errs.append(f"landing_pad {pad['id']} lies outside bounds")
    for vol in data.get("no_fly_volumes", []):
        if vol["floor_msl_m"] >= vol["ceiling_msl_m"]:
            errs.append(f"no_fly_volume {vol['id']}: floor must be below ceiling")
    errs += _duplicates("landing_pads", [p["id"] for p in data.get("landing_pads", [])])
    return errs


def rubric_semantic_errors(data: Manifest) -> list[str]:
    errs: list[str] = []
    errs += _duplicates("metrics", [m["id"] for m in data["metrics"]])
    if sum(m["weight"] for m in data["metrics"]) <= 0:
        errs.append("metric weights must sum to > 0")
    for m in data["metrics"]:
        bands = m["bands"]
        if "limit" in bands[-1]:
            errs.append(f"metric {m['id']}: last band must have no limit (catch-all)")
        limits = [b["limit"] for b in bands[:-1] if "limit" in b]
        if len(limits) != len(bands) - 1:
            errs.append(f"metric {m['id']}: every band except the last needs a limit")
            continue
        ordered = sorted(limits) if m["direction"] == "lower_is_better" else sorted(limits, reverse=True)
        if limits != ordered:
            errs.append(f"metric {m['id']}: band limits must run best→worst for {m['direction']}")
    return errs


def scenario_semantic_errors(data: Manifest, known: ManifestSet) -> list[str]:
    errs: list[str] = []
    area = known.areas.get(data["area_id"])
    if area is None:
        errs.append(f"area_id '{data['area_id']}' not found")
    rubric_id = data.get("rubric_id")
    if rubric_id and rubric_id not in known.rubrics:
        errs.append(f"rubric_id '{rubric_id}' not found")
    pads = {p["id"] for p in (area or {}).get("landing_pads", [])}
    failure_codes: set[str] = set()
    for v in data["vehicles"]:
        platform = known.platforms.get(v["platform_id"])
        if platform is None:
            errs.append(f"vehicle {v['vehicle_id']}: platform '{v['platform_id']}' not found")
        else:
            failure_codes |= {fm["id"] for fm in platform["failure_modes"]}
        pad = v["spawn"].get("pad_id")
        if pad and area is not None and pad not in pads:
            errs.append(f"vehicle {v['vehicle_id']}: pad '{pad}' not in area '{data['area_id']}'")
    for inj in data.get("injects", []):
        if inj["kind"] == "system_failure" and inj["code"] not in failure_codes:
            errs.append(f"inject at {inj['at_s']}s: failure mode '{inj['code']}' not on any vehicle")
    return errs


def _duplicates(what: str, ids: list[str]) -> list[str]:
    dups = sorted({i for i in ids if ids.count(i) > 1})
    return [f"{what}: duplicate id(s) {dups}"] if dups else []


# --------------------------------------------------------- public loaders


def validate_file(path: Path, kind: ManifestKind, schemas_dir: Path) -> Manifest:
    """Schema + single-file semantic validation. Raises ManifestError."""
    data = load_yaml(path)
    errors = schema_errors(data, kind, schemas_dir)
    if not errors:
        if kind is ManifestKind.PLATFORM:
            errors = platform_semantic_errors(data, path.parent.name)
        elif kind is ManifestKind.AREA:
            errors = area_semantic_errors(data, path.parent.name)
        elif kind is ManifestKind.RUBRIC:
            errors = rubric_semantic_errors(data)
    if errors:
        raise ManifestError(path, errors)
    return data


def discover(
    schemas_dir: Path,
    platforms_dir: Path | None = None,
    areas_dir: Path | None = None,
    rubrics_dir: Path | None = None,
    scenarios_dir: Path | None = None,
) -> tuple[ManifestSet, list[ManifestError]]:
    """Load every manifest found; return what loaded plus all errors.

    Directories starting with ``_`` (e.g. ``platforms/_template``) are skipped.
    """
    found = ManifestSet()
    errors: list[ManifestError] = []

    def _load(path: Path, kind: ManifestKind) -> Manifest | None:
        try:
            return validate_file(path, kind, schemas_dir)
        except ManifestError as exc:
            errors.append(exc)
        except (yaml.YAMLError, OSError) as exc:
            errors.append(ManifestError(path, [str(exc)]))
        return None

    if platforms_dir and platforms_dir.is_dir():
        for p in sorted(platforms_dir.glob("*/platform.yaml")):
            if not p.parent.name.startswith("_") and (d := _load(p, ManifestKind.PLATFORM)):
                found.platforms[d["identity"]["id"]] = d
    if areas_dir and areas_dir.is_dir():
        for p in sorted(areas_dir.glob("*/area.yaml")):
            if not p.parent.name.startswith("_") and (d := _load(p, ManifestKind.AREA)):
                found.areas[d["id"]] = d
    if rubrics_dir and rubrics_dir.is_dir():
        for p in sorted(rubrics_dir.glob("*.yaml")):
            if d := _load(p, ManifestKind.RUBRIC):
                found.rubrics[d["id"]] = d
    if scenarios_dir and scenarios_dir.is_dir():
        for p in sorted(scenarios_dir.glob("*.yaml")):
            d = _load(p, ManifestKind.SCENARIO)
            if d is None:
                continue
            if sem := scenario_semantic_errors(d, found):
                errors.append(ManifestError(p, sem))
            else:
                found.scenarios[d["id"]] = d
    return found, errors
