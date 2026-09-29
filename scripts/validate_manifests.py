#!/usr/bin/env python3
"""Validate every JSON Schema and every manifest in the repository.

Run via `make schemas`. Exit status 1 if anything is invalid. Checks:
  * each schemas/json/*.schema.json is itself a valid Draft 2020-12 schema
  * platforms/*/platform.yaml, terrain/areas/*/area.yaml,
    services/assessment/rubrics/*.yaml, scenarios/*.yaml pass schema +
    semantic validation (cdsim_common.manifests)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from cdsim_common.manifests import discover
from cdsim_common.paths import repo_root


def main() -> int:
    root = repo_root(Path(__file__))
    if root is None:
        print("cannot locate repository root", file=sys.stderr)
        return 2
    schemas = root / "schemas" / "json"
    for schema_file in sorted(schemas.glob("*.schema.json")):
        Draft202012Validator.check_schema(json.loads(schema_file.read_text()))
        print(f"  schema ok   {schema_file.relative_to(root)}")

    found, errors = discover(
        schemas,
        platforms_dir=root / "platforms",
        areas_dir=root / "terrain" / "areas",
        rubrics_dir=root / "services" / "assessment" / "rubrics",
        scenarios_dir=root / "scenarios",
    )
    for kind, items in (
        ("platform", found.platforms),
        ("area", found.areas),
        ("rubric", found.rubrics),
        ("scenario", found.scenarios),
    ):
        for manifest_id in items:
            print(f"  {kind:<9} ok  {manifest_id}")
    for err in errors:
        print(f"  INVALID  {err.path}", file=sys.stderr)
        for line in err.errors:
            print(f"           - {line}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} invalid manifest(s)", file=sys.stderr)
        return 1
    print("all manifests valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
