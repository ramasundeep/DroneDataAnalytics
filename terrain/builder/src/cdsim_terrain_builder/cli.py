"""``cdsim-area`` — area package command line.

cdsim-area validate terrain/areas/hyd_demo_01/area.yaml
cdsim-area plan     terrain/areas/hyd_demo_01/area.yaml
cdsim-area package  terrain/areas/hyd_demo_01/area.yaml   # Phase 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cdsim_common.config import get_settings
from cdsim_common.manifests import ManifestError, ManifestKind, validate_file
from cdsim_terrain_builder.plan import plan_area

EXIT_INVALID = 1
EXIT_NOT_IMPLEMENTED = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cdsim-area", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "plan", "package"):
        p = sub.add_parser(name)
        p.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)

    try:
        area = validate_file(args.manifest, ManifestKind.AREA, get_settings().schemas_dir)
    except ManifestError as exc:
        print(f"INVALID {exc.path}", file=sys.stderr)
        for e in exc.errors:
            print(f"  - {e}", file=sys.stderr)
        return EXIT_INVALID

    if args.cmd == "validate":
        print(f"ok {area['id']} {area['version']}")
        return 0

    plan = plan_area(area)
    if args.cmd == "plan":
        print(f"Area package plan: {plan.package_name}")
        for i, step in enumerate(plan.steps, 1):
            status = "ready" if step.phase_available == 0 else f"Phase {step.phase_available}"
            print(f"  {i:2d}. [{status:>7}] {step.name}: {step.detail}")
        print(f"  total tiles: {plan.total_tiles}")
        print("  outputs:")
        for out in plan.outputs:
            print(f"    - {out}")
        return 0

    print(
        "cdsim-area package: not implemented — scheduled for Phase 2 "
        "(docs/03_DIGITAL_TERRAIN_TWINS.md)",
        file=sys.stderr,
    )
    return EXIT_NOT_IMPLEMENTED


if __name__ == "__main__":
    sys.exit(main())
