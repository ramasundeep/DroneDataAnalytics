# CD Sim

**Chakravyuha Dynamics Private Limited (CDPL) — mission-rehearsal, training and simulation platform.**

> **Status: Phase 0 (skeleton) — under build.** This repository contains the
> foundations of CD Sim: contracts, services, tooling, documentation and an
> unverified Unreal Engine 5 project skeleton. Nothing in it is fielded or
> validated yet. RAVEN is CDPL's only delivered programme. See
> [docs/10_ROADMAP.md](docs/10_ROADMAP.md) for what exists and what comes next.

CD Sim is an **offline-first, platform-agnostic** simulation platform built on
**Unreal Engine 5**. One core — world, physics, vehicle and assessment layers —
serves five use cases:

1. **SITL testing** — unmodified ArduPilot SITL (later PX4) flying against the CD Sim world.
2. **Autonomy training** — datasets, scenario sweeps and reinforcement learning (first task: precision landing), with ONNX policy export.
3. **Pilot / operator training** — single-seat and networked fleet training, desktop and VR, with an instructor station.
4. **Mission rehearsal** — rehearse a task on a digital terrain twin of the real area.
5. **Maintainer training (Fleet Focus)** — Explore / Rehearse / Improve on the airframe's digital twin.

Every session is recorded on a single simulation clock and scored by the
**assessment engine** — that is what makes CD Sim a training system rather than
a game. Everything runs in Docker on a laptop, lab server or field box with **no
internet at runtime**.

## 5-minute quickstart

Prerequisites (details in [docs/ONBOARDING.md](docs/ONBOARDING.md)): Linux or
WSL2, Docker Engine with Compose v2, Python 3.11, Node.js 22, `make`, Git LFS.

```bash
git clone <this repo> cd-sim && cd cd-sim
make setup      # venv + Python/Node deps + git-lfs + .env
make dev        # build and start core + terrain + lms services, wait until healthy, smoke-test
```

Then open:

| What | URL |
|---|---|
| Instructor console | <http://localhost:8080> |
| API spec (OpenAPI JSON) | <http://localhost:8000/openapi.json> |
| Recorder / assessment specs | <http://localhost:8001/openapi.json>, <http://localhost:8002/openapi.json> |
| MinIO console | <http://localhost:9001> (credentials in `.env`) |

```bash
make test       # unit tests (Python + console)
make status     # container health
make down       # stop everything (volumes kept)
make help       # every target
```

The Unreal Engine 5.4 client is built separately on a machine with the engine
installed — see [docs/BUILDING_UE5.md](docs/BUILDING_UE5.md).

## Repository map

| Path | What |
|---|---|
| `docs/` | Vision, architecture, specs, roadmap, ADRs, onboarding — **start here** |
| `schemas/` | Protobuf + JSON Schema contracts shared by every component |
| `sim/` | Unreal Engine 5.4 C++ project (UNVERIFIED BUILD) and per-platform plugins |
| `platforms/` | Platform definitions (`platform.yaml`, autopilot params, mesh refs) |
| `terrain/` | Area package builder, offline terrain services, area manifests |
| `services/` | Python services: `api`, `recorder`, `assessment`, `sitl`, `rl`, shared `common` |
| `apps/instructor-console/` | React + TypeScript instructor / LMS web app |
| `scenarios/` | Scenario definitions (YAML) |
| `scripts/` | Developer helpers, scaffolders, smoke tests |
| `tests/` | Cross-package and integration tests |
| `tools/flight-log-analyser/` | Pre-existing standalone flight-log analyser (not part of the CD Sim runtime) |

## Documentation

| Doc | Read it for |
|---|---|
| [ONBOARDING](docs/ONBOARDING.md) | Your first five days |
| [01 Vision & use cases](docs/01_VISION_AND_USECASES.md) | What we are building and why |
| [02 Architecture](docs/02_ARCHITECTURE.md) | C4 diagrams, data flow, unified time base |
| [03 Digital terrain twins](docs/03_DIGITAL_TERRAIN_TWINS.md) | Area packages, build pipeline, offline serving |
| [04 Platform plugin spec](docs/04_PLATFORM_PLUGIN_SPEC.md) | Adding a vehicle — the most important doc |
| [05 SITL integration](docs/05_SITL_INTEGRATION.md) | ArduPilot SITL and the JSON physics interface |
| [06 Assessment engine](docs/06_ASSESSMENT_ENGINE.md) | Events, metrics, rubrics, reports |
| [07 Training modes](docs/07_TRAINING_MODES.md) | Single seat, fleet, VR, instructor, maintainer |
| [08 Autonomy training](docs/08_AUTONOMY_TRAINING.md) | RL environment, precision landing, ONNX |
| [09 Offline deployment](docs/09_DEPLOYMENT_OFFLINE.md) | Air-gap bundle, hardware, field boxes |
| [10 Roadmap](docs/10_ROADMAP.md) | Phases 0–8 and acceptance criteria |
| [ADRs](docs/ADR/README.md) | Every architecture decision and its reasoning |
| [CLAUDE.md](CLAUDE.md), [CONTRIBUTING.md](CONTRIBUTING.md) | Conventions, definition of done, workflow |

Build the docs site locally with `make docs` (output in `site/`).

## Licence

Proprietary and confidential — © Chakravyuha Dynamics Private Limited. See
[LICENSE](LICENSE). Third-party components: [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md).
