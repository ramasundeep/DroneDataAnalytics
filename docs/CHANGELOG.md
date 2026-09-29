# Changelog

All notable changes to CD Sim, newest first. One entry per roadmap phase
(plus any out-of-band releases). Format loosely follows
[Keep a Changelog](https://keepachangelog.com/). Every entry states what was
**verified** and what was **not** — never claim untested results.

## [Phase 0 — Skeleton] — 2026-09-29 — pending review

### Added
- Monorepo layout per the founding brief; pre-existing flight-log analyser
  relocated to `tools/flight-log-analyser/` (ADR 0001).
- `CLAUDE.md`, `CONTRIBUTING.md`, proprietary `LICENSE`, editor/format configs,
  Git LFS patterns, `Makefile` single entry point.
- Contracts: protobuf `common`, `events`, `telemetry`, `session`, `control`
  (package `cdsim.v1`); JSON Schemas for platform, area, rubric, scenario.
- Manifests: platform `cdpl_quad_01` (placeholder airframe) + template; areas
  `hyd_demo_01` (open-data demo, manifest only) and `flat_test`; rubrics
  `precision_landing_v1`, `maintainer_procedure_v1`; scenarios
  `landing_motor_failure_01`, `sitl_core_loop`.
- `cdsim_common`: unified `SimClock`, proto-compatible event models, settings,
  health/readiness router, manifest schema + semantic validation, MinIO bootstrap.
- Services: `api` (catalogue, aggregate health, explicit 501s for later
  phases), `recorder` (event ingest → TimescaleDB, ordered read-back, Redis
  fan-out), `assessment` (deterministic rubric scoring and validation),
  `sitl` (ArduPilot SITL image + tested JSON-physics codec), `rl`
  (precision-landing reward/curriculum, env interface).
- Terrain: `cdsim-area` builder CLI (validate, plan) and four offline terrain
  services (tiles, mesh, elevation, weather).
- Instructor console (React + TS) with system status and catalogue pages.
- Docker Compose profiles `core`, `terrain`, `lms`, `sitl`, `multiplayer`,
  `rl` with health checks; `scripts/smoke_dev.sh`.
- UE5 5.4 C++ project skeleton and `CDSimPlatform_cdpl_quad_01` plugin;
  `docs/BUILDING_UE5.md`; UE5 build scripts and manual CI workflow.
- CI: lint/typecheck/unit tests, docs build, manual/weekly stack smoke test.
- Documentation: specs 01–10, ONBOARDING, GLOSSARY, THIRD_PARTY, 17 ADRs.

### Verified (actually run, in the Phase 0 build environment)
- Python: all unit tests pass (`pytest`), `ruff` clean, `mypy --strict` clean.
- Console: lint, format check, typecheck, unit tests, production build pass.
- `make schemas`: all manifests valid; all `.proto` files compile.
- `make dev`: every `core`, `terrain` and `lms` container reached *healthy*;
  `scripts/smoke_dev.sh` passed; an event round-trip through recorder →
  TimescaleDB came back in sim-time order; integration tests passed.
- `make docs`: MkDocs site builds with `--strict`.

### Not verified
- **UE5 project**: never compiled (no engine in the build environment).
- **SITL image**: never built or run.
- **MinIO image tag** pinned in `docker-compose.yml` could not be pulled in the
  build environment; the stack was verified with a locally built MinIO
  stand-in via `CDSIM_MINIO_IMAGE`. The pinned tag must be confirmed.
- GitHub Actions workflows had not run at the time of writing.
