# CLAUDE.md — working conventions for CD Sim

This file is read by AI coding assistants (and should be read by humans too)
before changing anything in this repository. It is short on purpose; details
live in `docs/`.

## What this repo is

CD Sim is Chakravyuha Dynamics Private Limited's (CDPL) offline-first,
platform-agnostic mission-rehearsal, training and simulation platform, built
on Unreal Engine 5 with Python services, packaged in Docker to run air-gapped.
One core — world, physics, vehicle and assessment layers — serves every use
case; vehicles ("platforms") and areas of operations ("area packages") are
data-driven plugins that never require core changes. Every session is
recorded on a single simulation clock and scored by the assessment engine,
which is what makes CD Sim a training system rather than a game.

**The five use cases** (docs/01_VISION_AND_USECASES.md):

1. SITL testing — unmodified ArduPilot SITL (later PX4) flying against the CD Sim world.
2. Autonomy training — labelled data, scenario sweeps, RL (first task: precision landing), ONNX policy export.
3. Pilot / operator training — single-seat and networked fleet, desktop and VR, instructor station.
4. Mission rehearsal — rehearse a task on a digital terrain twin of the real area.
5. Maintainer training (Fleet Focus) — Explore / Rehearse / Improve on the airframe twin.

## Ground truth — never contradict in code, docs or READMEs

- CD Sim is **UE5-based** and **platform-agnostic**.
- CD Sim is **offline-first**: nothing may need the internet at runtime. Internet is allowed only at build time to fetch open data and images.
- **RAVEN is the only delivered programme.** Everything else in this repo is under build. Never describe any other capability as fielded, delivered, validated or operational.
- Never name any third-party company or client in code or docs. Open-source projects and open-data programmes are named only where a licence requires attribution (docs/THIRD_PARTY.md).
- Every UI screen carries the Chakravyuha Dynamics logo placeholder.
- Never invent test results. If something was not run, say so (commit message, CHANGELOG, PR).

## Fixed tech decisions — ask before changing

| Layer | Choice | ADR |
|---|---|---|
| Visual / physics client | Unreal Engine **5.4** (C++; Blueprints only for glue), Git LFS for binaries | 0002 |
| Autopilot | ArduPilot SITL, unmodified, MAVLink + JSON physics interface (UE5 owns physics); PX4 later | 0003 |
| Terrain twins | Offline Docker services: tiles (raster + terrain-RGB), mesh/3D tiles, elevation API, weather/scenario store | 0004, 0017 |
| Platform services | Python 3.11 / FastAPI; PostgreSQL + TimescaleDB; MinIO; Redis | 0005–0008 |
| Instructor / LMS UI | React + TypeScript | 0009 |
| Multiplayer | UE5 replication, dedicated server container | 0010 |
| VR | OpenXR via UE5 — a project configuration, not a fork | 0011 |
| RL / autonomy | Python gym-style env over gRPC; PyTorch; ONNX export | 0012 |
| Audio | UE5 capture → Opus chunks stamped with sim time → MinIO; optional offline Whisper (CPU); consent + retention | 0013 |
| Packaging | Compose profiles; Windows client + Linux services installers; `make deploy-box` air-gap bundle | 0014 |

Changing any row requires asking the founder/tech lead first and writing a
new ADR that supersedes the old one. Also ask before: changing the engine
version; adding anything that needs internet at runtime.

## Conventions

- **Python** — 3.11, `ruff` (lint + format, config in root `pyproject.toml`), `mypy --strict`, `pytest`. One package per service under `services/<name>/src/cdsim_<name>/`, shared code only in `services/common` (`cdsim_common`).
- **C++** — Unreal coding standard (`F`/`U`/`A`/`I`/`E` prefixes, PascalCase, tabs), formatted with the root `.clang-format`. Gameplay logic in C++; Blueprints only wire assets to C++.
- **TypeScript** — React + Vite, `eslint` + `prettier`, `vitest`. Strict TS.
- **Commits** — [Conventional Commits](https://www.conventionalcommits.org/): `feat(scope): …`, `fix: …`, `docs: …`, `chore: …`, `ci: …`, `build: …`, `test: …`. Small and self-describing.
- **ADRs** — one Markdown file per non-trivial decision in `docs/ADR/NNNN-kebab-title.md` (template: `docs/ADR/0000-template.md`). Never edit an accepted ADR's decision — supersede it.
- **Schemas first** — cross-process data is defined in `schemas/` before code uses it.
- **Time** — every recorded datum carries `sim_time_us` from the unified clock; wall-clock is reference only. Never order or join by wall-clock.
- **Boring over clever** — the team inheriting this is new to it.

## Definition of done

A change is done when **all** of these hold:

1. Code is written and follows the conventions above.
2. Unit tests cover it (or the PR explains why not, e.g. UE5 code pending an engine build).
3. Relevant docs are updated in the same PR (spec docs, READMEs, ADR if a decision was made, `docs/CHANGELOG.md` for user-visible changes).
4. `make lint`, `make typecheck` and `make test` are green locally and in CI.

## Where things live

- **Secrets** — never in git. Local: `.env` (copied from `.env.example` by `make setup`, gitignored). Field boxes: generated at bundle time (Phase 8). Code reads them via `cdsim_common.config.Settings` as `SecretStr`.
- **Large data** — binary assets (UE `.uasset/.umap`, CAD `.step/.fbx`, rasters, audio, ONNX) via **Git LFS** (`.gitattributes`). Built area packages and session recordings live in **MinIO** (`cdsim-areas`, `cdsim-recordings` buckets), never in git.
- **Contracts** — `schemas/` (protobuf + JSON Schema).
- **Platforms** — `platforms/<id>/platform.yaml` + `sim/Plugins/CDSimPlatform_<id>/`.
- **Areas** — `terrain/areas/<id>/area.yaml` (manifest only in git).
- **Scenarios / rubrics** — `scenarios/*.yaml`, `services/assessment/rubrics/*.yaml`.

## How to add a platform

```bash
make new-platform id=my_vehicle     # scaffolds platforms/my_vehicle + UE plugin skeleton
# edit platforms/my_vehicle/platform.yaml and ardupilot.parm
make schemas                         # schema + semantic validation
```

Full procedure including the CAD → FBX → UE5 pipeline: `docs/04_PLATFORM_PLUGIN_SPEC.md`.
The core must not need edits — if it does, that is a core bug; fix the core generically.

## How to add an area

```bash
make new-area id=my_area            # scaffolds terrain/areas/my_area/area.yaml
# edit bounds, origin, sources, pads, no-fly volumes, weather
make schemas
```

Building and serving the package offline: `docs/03_DIGITAL_TERRAIN_TWINS.md`.

## Useful commands

`make help` · `make setup` · `make dev` · `make status` · `make test` · `make lint` · `make typecheck` · `make schemas` · `make docs` · `make down`

## Honesty markers

- Code that has never been compiled/run is marked **UNVERIFIED BUILD** in its header and README (currently: everything under `sim/`, the SITL image).
- Unimplemented behaviour returns HTTP 501 or raises `NotImplementedError` with the roadmap phase that will deliver it. No silent stubs.
