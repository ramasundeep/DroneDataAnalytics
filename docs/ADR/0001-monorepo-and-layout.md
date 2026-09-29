# ADR 0001: One `cd-sim` monorepo and its directory layout

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-29 |
| Deciders | CDPL founding engineering |
| Supersedes | — |
| Superseded by | — |

## Context

CD Sim spans very different kinds of artefact: an Unreal Engine 5 C++ project
(`sim/`), Python services (`services/`, `terrain/`), a React + TypeScript web
app (`apps/instructor-console/`), protobuf and JSON Schema contracts
(`schemas/`), human-edited YAML data (platforms, areas, scenarios, rubrics)
and Docker packaging. The founding brief ([00_ORIGIN_PROMPT.md](../00_ORIGIN_PROMPT.md))
asks for "a single GitHub monorepo named `cd-sim`" with a prescribed layout,
and requires that a change to a contract, its producers and its consumers can
land together while `main` stays buildable.

This repository already contained a small Streamlit flight-log analyser at its
root (ArduPilot / PX4 / MAVLink log parsing and plotting). It is useful to the
team but is not part of the CD Sim runtime. When the Phase 0 plan was approved
the founder decided it should be **moved, not deleted**.

## Decision

We will build CD Sim as **one monorepo — this repository is `cd-sim`** — with
the layout of the founding brief, plus the deliberate differences below.

| Path | Holds | Rule |
|---|---|---|
| `sim/` | UE5 project (`CDSim.uproject`, `Source/CDSim/{Core,World,Vehicle,Sensors,Recording,Net,XR}`) | C++ first; binaries via LFS ([0002](0002-unreal-engine-5-4-and-git-lfs.md)) |
| `sim/Plugins/CDSimPlatform_<id>/` | per-platform UE5 **code and assets** | one plugin per platform |
| `platforms/<id>/` | per-platform **data**: `platform.yaml`, `ardupilot.parm`, mesh refs | no code; validated by `schemas/json/platform.schema.json` |
| `terrain/{builder,services,areas}/` | area builder CLI, offline terrain services, area manifests | package data never in git ([0004](0004-offline-terrain-twins-in-docker.md)) |
| `services/<name>/` | one Python package per service: `api`, `recorder`, `assessment`, `sitl`, `rl` | layout `services/<name>/src/cdsim_<name>/` |
| `services/common/` | the only shared Python code (`cdsim_common`: sim clock, events, config, health, manifests) | services never import each other |
| `scenarios/` | scenario YAML + missions (`scenarios/missions/*.waypoints`) | **added** — see below |
| `apps/instructor-console/` | React + TS console | [0009](0009-react-typescript-console.md) |
| `schemas/` | protobuf + JSON Schema contracts | [0016](0016-schema-contracts-protobuf-and-json-schema.md) |
| `tools/flight-log-analyser/` | the relocated legacy analyser | standalone; not built, tested or shipped with CD Sim |

**Platforms: data vs code.** A platform is split into `platforms/<id>/` (what
the vehicle *is*: mass, actuators, sensors, failure modes, procedures) and
`sim/Plugins/CDSimPlatform_<id>/` (how it *looks and binds* in UE5). The
Python services, the assessment engine and the SITL container read only the
data half and never need a UE5 toolchain. `make new-platform id=<x>`
(`scripts/new_platform.py`) scaffolds both halves from `platforms/_template`.

**One Python package per service, one shared package.** Each service is its
own installable package with its own `pyproject.toml` and tests, built into
its own image by the shared `services/Dockerfile` (`PACKAGE` build arg).
Shared code lives only in `services/common`; if two services need the same
function it moves there. This keeps dependency graphs shallow and lets
`mypy --strict` and `ruff` run over every package from one `Makefile`.

**`scenarios/` at the top level.** The brief's layout has no home for
scenarios. They are neither platform data, nor area data, nor service code:
a scenario *references* an area, a platform, a rubric and injects, and is read
by the API, the scenario runner, the assessment engine and (later) UE5. We
therefore added `scenarios/` as a peer of `platforms/` and `terrain/areas/`,
validated by `schemas/json/scenario.schema.json` and mounted read-only into the
services by `docker-compose.yml`. Rubrics stay beside their only consumer in
`services/assessment/rubrics/`.

**Legacy analyser.** Moved to `tools/flight-log-analyser/` in commit
"chore: relocate flight-log analyser" with its own README and requirements.
`tools/` is excluded from the CD Sim lint, typecheck and test targets.

## Status (Phase 0)

- Layout exists as above; `make setup` installs every Python package editable
  into one virtualenv (`PY_PACKAGES` in the `Makefile`).
- Lint, `mypy --strict` and unit tests across all Python packages, and the
  console's lint/typecheck/tests/build, were run locally and pass. The GitHub
  Actions workflows in `.github/workflows/` exist but have not yet run.
- `sim/` is UNVERIFIED BUILD (never compiled). `tools/flight-log-analyser/`
  was moved unchanged and was not re-tested.

## Consequences

### Positive

- Contract, producer and consumer change in one PR; `make schemas` validates
  every manifest in the repository at once.
- One `Makefile` and one CI workflow give one definition of "green".
- Adding a platform or area is a data change in a known place, not a core change.

### Negative

- The repository mixes a large LFS-backed UE5 tree with small text trees;
  clones without `git lfs` skip binaries (`make setup` warns).
- Anyone touching one service still clones the whole repository.
- `tools/` holds code that follows none of the CD Sim conventions.

### Risks

| Risk | Mitigation |
|---|---|
| Services start importing each other | Code review; shared code only in `services/common` (`CLAUDE.md`) |
| UE5 assets bloat the repo | LFS patterns in `.gitattributes`; area data and recordings in MinIO |
| Legacy analyser mistaken for product | README banner in `tools/flight-log-analyser/`; excluded from builds |

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Polyrepo (sim, services, console, schemas separately) | Cross-repo contract changes need coordinated releases; the brief asks for one repo; a small new team gains nothing from the overhead. |
| Delete the flight-log analyser | Founder asked to keep it; it is useful for looking at real-vehicle logs. |
| Keep the analyser at the repo root | Would confuse the layout and the tooling (ruff/pytest would pick it up). |
| Platform data inside the UE5 plugin | Python services would need to parse a UE plugin tree; the SITL image would depend on UE assets. |
| Scenarios under `services/api/` | Several consumers, including UE5; data should not live inside one service. |
| One shared Python package for all services | Couples release and dependency sets of unrelated services. |

## Revisit when

- A clone (with LFS) exceeds roughly 20 GB or CI checkout time dominates CI.
- More than one team owns disjoint parts and review routing (`CODEOWNERS`)
  becomes painful.
- The flight-log analyser is either adopted into the product (then it gets a
  service and an ADR) or unused for two phases (then propose removal).
- A second consumer of rubrics outside `services/assessment` appears (then
  move rubrics to a top-level directory like `scenarios/`).
