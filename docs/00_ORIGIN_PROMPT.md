# 00 — Origin Prompt

> This is the founding brief for CD Sim, preserved verbatim so every engineer can see the original intent. It was given to an AI coding assistant (Claude Code) as the opening instruction for the repository. Decisions made since are recorded in `docs/ADR/`; where the codebase departs from this brief, an ADR explains why.
>
> Two clarifications were given when the Phase 0 plan was approved: (1) the pre-existing flight-log analyser in this repository was moved to `tools/flight-log-analyser/` rather than deleted; (2) Unreal Engine is pinned at 5.4 as written.

---

# CD Sim Platform — Claude Code Build Prompt

> Paste everything below the line into Claude Code as the opening message. Run it in **plan mode first** (`/plan`), approve the plan, then let it execute phase by phase. Save this file as `docs/00_ORIGIN_PROMPT.md` in the repo so hires can see the founding intent.

---

## Role and mission

You are the founding engineer building **CD Sim**, the mission-rehearsal, training and simulation platform of Chakravyuha Dynamics Private Limited (CDPL), Hyderabad. CD Sim is CDPL's flagship product line: simulators fielded to Indian Army units and under contract for the Indian Air Force. Everything you build will be handed to a newly hired simulation-engineering team, so **documentation, modularity and reproducibility are first-class deliverables, not afterthoughts.** Assume the reader of every file is a competent engineer who has never spoken to the founder.

Build this as a single GitHub monorepo named `cd-sim`. Initialise git, commit in small, well-described commits, and keep `main` always buildable.

## What CD Sim is

CD Sim is an **offline-first, modular simulation platform** whose single core serves five use cases through the same world, physics, vehicle and assessment layers:

1. **SITL testing** — autopilot-in-the-loop (unmodified ArduPilot SITL, later PX4) against the CD Sim world, for engineering validation of CDPL platforms and mission scripts.
2. **Autonomy training** — generating labelled data, running scripted scenario sweeps and reinforcement-learning episodes so a drone learns a precise action (first target: **precision landing** on a marked pad / moving platform), with the trained policy exportable to the real vehicle.
3. **Pilot / operator training** — immersive single-seat and networked **fleet** training (many pilots, one shared world), desktop and VR, with instructor station.
4. **Mission rehearsal** — rehearsing a specific task on a digital terrain twin of the actual area.
5. **Maintainer training** — digital-twin-based Explore / Rehearse / Improve procedures on the airframe (the **Fleet Focus** programme).

**Digital terrain twins are the foundation.** Terrain, imagery, elevation, 3D tiles, weather and scenario data for an area of operations are packaged and served from **Docker containers that run fully offline** on a laptop, a lab server or a ruggedised field box. No cloud dependency anywhere. Internet is used only at build time to fetch open data; a deployed CD Sim box must work air-gapped.

**Platform-agnostic and modular.** A "platform" (a specific drone, rover, helicopter, mortar, etc.) is a self-contained plugin: geometry, mass/inertia, propulsion and aero model, autopilot binding, sensors, failure modes and maintenance procedures. Adding a new platform must require no changes to the core. We start with **one CDPL multirotor drone** (placeholder geometry now; real CAD files — STEP/FBX — will be supplied later, so design the asset pipeline to swap them in cleanly).

**Assessment engine.** Every session is recorded: full telemetry, control inputs, world events, instructor injects, and **trainee audio** (microphone), all on one time base. The engine derives temporal metrics — reaction time from stimulus to first control input, decision latency, hesitation, procedure-step timing, error recovery time — and produces scores against a rubric. This is what makes CD Sim a training *system* rather than a game; treat it as a core module, not a feature.

## Tech decisions (fixed unless you find a hard blocker — then stop and ask)

| Layer | Choice | Notes |
|---|---|---|
| Visual / physics client | **Unreal Engine 5.4+** (C++ project, Blueprints only for glue) | Pin engine version in `docs/`. Store the `.uproject` and C++ source in git; binary assets via **Git LFS**. |
| Autopilot | **ArduPilot SITL**, unmodified, over MAVLink + ArduPilot JSON physics interface | UE5 owns physics; SITL receives sensor JSON, returns PWM. Design the binding so PX4 can be added later. |
| Terrain twins | Docker services: tile server (raster + terrain-RGB), 3D tiles/mesh server, elevation query API, weather/scenario store | Build from open data (SRTM/Copernicus DEM, OSM, Sentinel imagery) and from CDPL-flown photogrammetry when supplied. One `docker compose up` per area package. |
| Platform services | **Python 3.11 / FastAPI** backend, **PostgreSQL + TimescaleDB** for telemetry and events, **MinIO** for recordings, **Redis** for live pub/sub | All in Docker. Offline by default. |
| Instructor / LMS UI | **React + TypeScript** web app served by the backend | Scenario authoring, session control, live monitoring, replay, scoring, trainee records. |
| Multiplayer | UE5 replication with a dedicated server container | Fleet training = N clients + 1 instructor + 1 dedicated server on a LAN. |
| VR | OpenXR via UE5 | Desktop first; VR as a project configuration, not a fork. |
| RL / autonomy | **Python gym-style environment** wrapping the UE5 sim via gRPC/ZeroMQ; PyTorch; headless UE5 render at N× real-time | Policy export to ONNX. |
| Audio | Client-side capture in UE5, streamed as Opus chunks with sim-time stamps into MinIO; optional offline transcription (Whisper, CPU) | Consent prompt and per-session retention setting. |
| Packaging | Docker Compose profiles; installers for Windows (client) and Linux (services); one `make deploy-box` that produces an air-gap bundle (images + area packages + client build) | |
| Licensing / branding | CDPL proprietary. Every screen carries the Chakravyuha Dynamics logo placeholder. Never reference any third-party company or client by name in code or docs. | |

## Repository layout to create

```
cd-sim/
├── README.md                     # what CD Sim is, 5-minute quickstart, links to docs
├── CLAUDE.md                     # conventions for AI-assisted work in this repo (see below)
├── CONTRIBUTING.md               # branching, commit style, review checklist, DoD
├── LICENSE                       # proprietary notice
├── Makefile                      # single entry: make setup / dev / test / package / deploy-box
├── docker-compose.yml            # profiles: core, terrain, lms, multiplayer, rl
├── .github/workflows/            # lint + unit tests + doc build; UE5 build as manual job
├── docs/
│   ├── 00_ORIGIN_PROMPT.md       # this prompt, verbatim
│   ├── 01_VISION_AND_USECASES.md
│   ├── 02_ARCHITECTURE.md        # C4 diagrams (Mermaid), data flow, time-base design
│   ├── 03_DIGITAL_TERRAIN_TWINS.md   # area package format, build pipeline, offline serving
│   ├── 04_PLATFORM_PLUGIN_SPEC.md    # how to add a new drone/vehicle — the most important doc
│   ├── 05_SITL_INTEGRATION.md
│   ├── 06_ASSESSMENT_ENGINE.md   # event schema, metrics definitions, rubric format
│   ├── 07_TRAINING_MODES.md      # single, fleet, VR, instructor station, maintainer
│   ├── 08_AUTONOMY_TRAINING.md   # RL env, precision-landing task, policy export
│   ├── 09_DEPLOYMENT_OFFLINE.md  # air-gap bundle, hardware specs, field-box setup
│   ├── 10_ROADMAP.md             # phased plan with acceptance criteria
│   ├── ADR/                      # Architecture Decision Records, one file per decision
│   └── ONBOARDING.md             # day-1 to day-5 plan for a new engineer
├── sim/                          # Unreal Engine 5 project
│   ├── CDSim.uproject
│   ├── Source/CDSim/             # C++: Core, World, Vehicle, Sensors, Recording, Net, XR
│   ├── Plugins/                  # CDSimPlatform_<name>/ — one plugin per platform
│   └── Content/                  # LFS; minimal placeholder assets only
├── platforms/                    # platform definitions (data, not code)
│   └── cdpl_quad_01/             # YAML spec, mass/inertia, motors, params, mesh refs, maintenance procedures
├── terrain/                      # digital terrain twin tooling
│   ├── builder/                  # Python: fetch, process, tile, package an area
│   ├── services/                 # Dockerfiles for tile/mesh/elevation/weather servers
│   └── areas/                    # area package manifests (data itself in MinIO/LFS)
├── services/
│   ├── api/                      # FastAPI: sessions, scenarios, trainees, scoring, replay
│   ├── assessment/               # metrics pipeline, rubric evaluation, report generation
│   ├── recorder/                 # telemetry/event/audio ingest on unified sim-time
│   ├── sitl/                     # ArduPilot SITL container + bridge
│   └── rl/                       # gym env, training scripts, precision-landing task
├── apps/
│   └── instructor-console/       # React + TS
├── schemas/                      # protobuf/JSON schemas: telemetry, events, session, platform, area package
├── scripts/                      # dev helpers, data seeding, smoke tests
└── tests/                        # unit + integration; fixtures include a recorded golden session
```

## `CLAUDE.md` must contain

- Repo purpose in three sentences; the five use cases.
- Fixed tech decisions above, and "ask before changing".
- Conventions: Python (ruff, mypy, pytest), C++ (Unreal style, clang-format), TS (eslint, prettier), Conventional Commits, one ADR per non-trivial decision.
- Definition of done: code + unit test + doc update + `make test` green.
- Ground truth to protect: CD Sim is UE5-based and platform-agnostic; offline-first; RAVEN is the only delivered programme, everything else is under build — never claim otherwise in docs or READMEs.
- Where secrets live (never in git), where large data lives (LFS/MinIO), how to add a platform, how to add an area.

## Core design requirements

**Unified time base.** One monotonic sim clock (`sim_time_us`) stamps every telemetry frame, event, control input, audio chunk and video keyframe. Wall-clock is recorded alongside for reference only. Replay must reproduce a session deterministically from recordings.

**Event schema** (`schemas/events.proto`): `stimulus` (instructor inject, system failure, target appearance, alarm), `response` (control input, mode change, voice command, menu action), `outcome` (landing touchdown with position/velocity error, collision, geofence breach, procedure step complete/fail), `annotation` (instructor free text). Every event carries `sim_time_us`, `session_id`, `actor_id`, `source`, typed payload.

**Assessment metrics v1**: reaction time (stimulus → first meaningful response), decision latency (stimulus → correct response), control smoothness (input jerk), procedure adherence (ordered checklist), landing precision (radial error, vertical speed at touchdown, attitude at touchdown), recovery time after injected failure, communication timeliness (audio energy onset after stimulus; transcription optional). Rubrics are YAML; scores are per-metric with weights and pass/fail bands; reports export to PDF and JSON.

**Platform plugin spec**: a platform is `platforms/<id>/platform.yaml` + a UE5 plugin. YAML declares: identity, class (multirotor/fixed-wing/VTOL/rover/helicopter/weapon), mass properties, propulsion map, aero coefficients, sensor suite, ArduPilot param file, failure modes, maintenance procedures (step list with 3D anchor points for the maintainer module), and mesh references. The core loads any platform by id; a `make new-platform id=<x>` scaffolder creates the skeleton. Document the CAD → FBX → UE5 asset pipeline so the real CDPL drone CAD can be dropped in later, including LOD and collision generation.

**Area package spec**: `areas/<id>/area.yaml` describing bounds, CRS, source data, tile layers, elevation, 3D mesh, no-fly volumes, named landing pads/targets, default weather. `terrain/builder` produces a versioned tarball; `docker compose --profile terrain up` serves it. Include one small demo area built from open data around Hyderabad (public data only).

**SITL binding**: one SITL container per vehicle; UE5 sends sensor JSON at 400 Hz-equivalent sim rate, receives PWM; MAVLink exposed to the instructor console and to a ground-control-station port so real GCS software can connect. Support sim-rate scaling (0.1× to 10×) for RL and soak tests.

**Fleet mode**: dedicated UE5 server container; clients join by session code on LAN; instructor sees all vehicles; per-trainee recording and scoring; shared stimuli (one inject hits all trainees simultaneously for comparative reaction-time analysis).

**Maintainer module (Fleet Focus)**: Explore (walk the twin, part identification), Rehearse (guided procedure with anchors, tool selection, step timing), Improve (after-action review from the assessment engine). Procedures come from the platform YAML.

**Precision-landing RL task**: observation = downward camera + IMU + estimated pad pose; action = velocity setpoints via MAVLink guided mode; reward shaped on radial error, descent rate, attitude, time; curriculum from static pad → wind → moving pad. Export policy to ONNX and document how it would run onboard.

## Delivery phases (put these in `docs/10_ROADMAP.md` with acceptance criteria and build them in order)

**Phase 0 — Skeleton (do this first, completely):** repo layout, all docs as complete drafts (not stubs), schemas, Docker Compose skeleton with health checks, CLAUDE.md, CI, ONBOARDING.md, ADRs for every table row above. Acceptance: a new engineer can clone, run `make setup && make dev`, see all services healthy, and read their way to understanding the system in one day.

**Phase 1 — Core loop:** one placeholder quad in UE5 flies under ArduPilot SITL on a flat test area with MAVLink exposed; recorder captures telemetry + events on the unified clock; replay works. Acceptance: scripted takeoff–waypoint–land runs headless and produces a session file that replays deterministically.

**Phase 2 — Terrain twins:** area builder + offline services; the Hyderabad demo area renders in UE5 with correct elevation; landing pads defined in `area.yaml` appear in-world.

**Phase 3 — Assessment engine v1:** instructor injects, event pipeline, audio capture, metrics, rubric scoring, PDF report. Acceptance: a golden test session scores identically on every run; reaction-time test with a synthetic stimulus verified to within 20 ms.

**Phase 4 — Instructor console + single-seat training mode** with scenario authoring and live monitoring.

**Phase 5 — Fleet mode** (dedicated server, 4 clients on LAN) and **VR configuration**.

**Phase 6 — Maintainer module** on the placeholder airframe, ready to receive real CAD.

**Phase 7 — Autonomy training**: gym env, precision-landing curriculum, ONNX export, headless multi-instance runs.

**Phase 8 — Air-gap packaging**: `make deploy-box` bundle, installer, field-box hardware spec document, smoke test on a clean machine with no network.

## How to work

- Start in plan mode. Present the Phase 0 plan; wait for approval; then execute Phase 0 entirely before touching Phase 1.
- After each phase: update docs, add an ADR for anything you decided, write a `docs/CHANGELOG.md` entry, and stop for review.
- Where UE5 cannot be compiled in your environment, still write the full C++ source, `.uproject`, build scripts and a `docs/BUILDING_UE5.md` that a Windows/Linux engineer can follow, and mark unverified builds clearly.
- Never invent test results. If something is not run, say so in the commit and the doc.
- Ask, don't assume, on: engine version if 5.4 is unavailable; any change to the tech table; anything that would require internet at runtime.
- Prefer boring, well-documented choices over clever ones — the team inheriting this will be new to it.
