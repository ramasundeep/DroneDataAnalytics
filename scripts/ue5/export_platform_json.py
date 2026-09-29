#!/usr/bin/env python3
"""Export platform and area manifests from YAML to JSON for the UE5 project.

Unreal Engine has no YAML parser, so the build converts the source-of-truth
manifests into JSON files with the *same tree* that the C++ code reads:

    platforms/<id>/platform.yaml     -> sim/Config/Platforms/<id>.json
    terrain/areas/<id>/area.yaml     -> sim/Config/Areas/<id>.json

Directories whose name starts with ``_`` (e.g. ``platforms/_template``) are
skipped. The output is generated and gitignored (``sim/.gitignore``); never
edit it by hand. Schema validation is *not* repeated here — run
``make schemas`` for that.

Run from anywhere::

    python scripts/ue5/export_platform_json.py            # write
    python scripts/ue5/export_platform_json.py --check    # exit 1 if output is stale

Dependencies: Python 3.11 standard library + PyYAML.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

GENERATOR = "scripts/ue5/export_platform_json.py"


@dataclass(frozen=True)
class ManifestKind:
    """One kind of manifest to export."""

    name: str
    source_glob: str
    manifest_name: str
    out_subdir: str


PLATFORMS = ManifestKind("platform", "platforms/*", "platform.yaml", "Platforms")
AREAS = ManifestKind("area", "terrain/areas/*", "area.yaml", "Areas")


class ExportError(Exception):
    """A manifest could not be exported."""


def default_repo_root() -> Path:
    """Repository root: this file lives at <root>/scripts/ue5/."""
    return Path(__file__).resolve().parents[2]


def manifest_id(kind: ManifestKind, data: dict[str, Any]) -> str:
    """Return the declared id (identity.id for platforms, id for areas)."""
    if kind is PLATFORMS:
        identity = data.get("identity")
        value = identity.get("id") if isinstance(identity, dict) else None
    else:
        value = data.get("id")
    if not isinstance(value, str) or not value:
        raise ExportError(f"{kind.name} manifest has no id")
    return value


def load_manifest(path: Path) -> dict[str, Any]:
    """Load one YAML manifest; it must be a mapping."""
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ExportError(f"{path}: top level is not a mapping")
    return data


def render_json(data: dict[str, Any], source: str) -> str:
    """Serialise with a provenance header. Unknown YAML scalars become strings."""
    document: dict[str, Any] = {
        "_generated_by": GENERATOR,
        "_source": source,
        **data,
    }
    return json.dumps(document, indent=2, ensure_ascii=False, default=str) + "\n"


def display(path: Path, root: Path) -> str:
    """Path relative to the repo root when possible, for messages."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def discover(root: Path, kind: ManifestKind) -> list[Path]:
    """All manifests of a kind, skipping directories that start with '_'."""
    found: list[Path] = []
    for directory in sorted(root.glob(kind.source_glob)):
        if not directory.is_dir() or directory.name.startswith("_"):
            continue
        manifest = directory / kind.manifest_name
        if manifest.is_file():
            found.append(manifest)
    return found


def export_kind(
    root: Path, out_root: Path, kind: ManifestKind, check: bool
) -> tuple[int, list[str]]:
    """Export (or check) every manifest of one kind. Returns (count, problems)."""
    problems: list[str] = []
    out_dir = out_root / kind.out_subdir
    count = 0
    for manifest in discover(root, kind):
        relative = manifest.relative_to(root).as_posix()
        try:
            data = load_manifest(manifest)
            ident = manifest_id(kind, data)
        except (ExportError, yaml.YAMLError) as exc:
            problems.append(f"{relative}: {exc}")
            continue
        if ident != manifest.parent.name:
            problems.append(
                f"{relative}: id '{ident}' does not match directory '{manifest.parent.name}'"
            )
            continue

        target = out_dir / f"{ident}.json"
        text = render_json(data, relative)
        if check:
            current = target.read_text(encoding="utf-8") if target.is_file() else None
            if current != text:
                problems.append(f"{display(target, root)} is missing or stale")
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            print(f"  {kind.name:<8} {relative} -> {display(target, root)}")
        count += 1
    return count, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--repo-root", type=Path, default=default_repo_root(), help="repository root"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output Config directory (default: <repo-root>/sim/Config)",
    )
    parser.add_argument(
        "--check", action="store_true", help="do not write; exit 1 if output is stale"
    )
    args = parser.parse_args(argv)

    root: Path = args.repo_root.resolve()
    out_root: Path = (args.out or root / "sim" / "Config").resolve()

    total = 0
    problems: list[str] = []
    for kind in (PLATFORMS, AREAS):
        count, kind_problems = export_kind(root, out_root, kind, args.check)
        total += count
        problems.extend(kind_problems)

    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if problems:
        return 1
    verb = "up to date" if args.check else "exported"
    print(f"{total} manifest(s) {verb}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
