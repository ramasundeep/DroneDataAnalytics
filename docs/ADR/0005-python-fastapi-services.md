# ADR 0005: Python 3.11 + FastAPI for platform services

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-29 |
| Deciders | CDPL founding engineering |
| Supersedes | — |
| Superseded by | — |

## Context

Around the UE5 simulator CD Sim needs a set of back-end services: the
session/catalogue API behind the instructor console, the recorder that
ingests events and telemetry on the unified clock, the assessment engine that
scores sessions against rubrics, the terrain services, the SITL bridge
tooling and the RL harness. These services are I/O-bound (database, object
store, pub/sub, HTTP), must run offline in Docker, and must be maintainable
by a newly hired team. The RL stack (PyTorch, Gymnasium-style env, ONNX) and
the geospatial tooling for area building are Python ecosystems. The founding
brief fixes "Python 3.11 / FastAPI".

## Decision

All CD Sim platform services are **Python 3.11** packages built on
**FastAPI** (pinned `fastapi==0.115.0`, `uvicorn[standard]==0.30.6`,
`pydantic==2.9.2`), each started as `uvicorn --factory <pkg>.main:create_app`.

Rules every service follows:

1. **Layout** — `services/<name>/src/cdsim_<name>/` with its own
   `pyproject.toml` and `tests/`; shared code only in `services/common`
   (`cdsim_common`) ([0001](0001-monorepo-and-layout.md)).
2. **App factory** — `create_app(settings=None)` so tests build an app with
   injected settings and fakes; no module-level global app state.
3. **Configuration** — `cdsim_common.config.Settings` (pydantic-settings, `CDSIM_*`
   environment variables); secrets are `SecretStr`, read from `.env`, never
   committed.
4. **Health contract** — `cdsim_common.health` gives every service
   `GET /health` (liveness, always 200) and `GET /ready` (every dependency
   check passes within 2 s → 200, else 503 with per-check detail). Compose
   health checks call `/ready`; the API's `/v1/system/health` aggregates all
   services for the console.
5. **Versioned routes** — `/v1/...`. Unimplemented endpoints return
   **HTTP 501 naming the roadmap phase** that will deliver them, never a
   silent stub.
6. **Contracts** — request/response bodies that cross process boundaries
   mirror `schemas/` ([0016](0016-schema-contracts-protobuf-and-json-schema.md));
   events use the Pydantic mirror in `cdsim_common/events.py`.
7. **Quality gates** — `ruff` (lint + format), `mypy --strict`, `pytest`;
   `make lint typecheck test` must be green.
8. **One image recipe** — `services/Dockerfile` with build arg `PACKAGE`,
   non-root user, contracts baked in, manifests mounted read-only.

| Service | Port | Package |
|---|---|---|
| api | 8000 | `services/api` (`cdsim_api`) |
| recorder | 8001 | `services/recorder` (`cdsim_recorder`) |
| assessment | 8002 | `services/assessment` (`cdsim_assessment`) |
| terrain ×4 | 8101–8104 | `terrain/services` (`cdsim_terrain`) |

## Status (Phase 0)

- api, recorder, assessment and the four terrain services exist, pass
  unit tests, `ruff` and `mypy --strict`, and ran healthy under `make dev`
  with `scripts/smoke_dev.sh` passing (verified locally).
- Implemented: catalogue endpoints (`/v1/platforms`, `/v1/areas`,
  `/v1/scenarios`, `/v1/rubrics`), event ingest and query in the recorder,
  deterministic band scoring and rubric validation in assessment.
- Not implemented (501 or `NotImplementedError` with phase): sessions,
  replay, trainees, most assessment metrics (Phase 3), live monitoring (Phase 4).

## Consequences

### Positive

- One language for services, RL and area tooling; one toolchain to learn.
- FastAPI + Pydantic give typed validation and a generated OpenAPI
  document (`/openapi.json`) for free. The interactive Swagger/ReDoc pages
  are deliberately disabled (`docs_url=None`) because they load JavaScript
  from a CDN, which would break offline-first.
- Async I/O fits the ingest and aggregation workloads.

### Negative

- Python is slower than compiled languages for hot paths (high-rate
  telemetry decoding, metric computation over long sessions).
- Several processes each hold their own Python runtime (memory on a field box).

### Risks

| Risk | Mitigation |
|---|---|
| Recorder cannot keep up with N vehicles × 50 Hz state + events | Batch ingest (`EventBatch`); move writes to COPY if needed; measure in Phase 1/5 before optimising |
| Dependency drift | Exact pins in each `pyproject.toml`; images built once and mirrored ([0014](0014-compose-profiles-and-air-gap-bundle.md)) |
| Global state sneaks into services | App-factory rule; tests construct fresh apps |

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Go or Rust services | Faster, but splits the team across languages and loses the Python RL/geo ecosystem. |
| Flask / Django | Flask lacks typed validation and async out of the box; Django's ORM/admin are not needed and add weight. |
| Services inside UE5 | Couples back-end availability to a GPU client; services must run on a headless Linux box. |
| One monolithic service | Recorder load and assessment CPU spikes would affect the console API; separate health is clearer. |

## Revisit when

- Profiling in Phase 1 or 5 shows a service cannot sustain the recorded
  rates (e.g. recorder p95 ingest latency grows unbounded at 4 vehicles).
  First response: optimise or move the hot path into a compiled extension;
  replacing FastAPI is a tech-table change.
- Python 3.11 reaches end of security support before the next major release.
