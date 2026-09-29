# cdsim-common

Shared Python library for every CD Sim service. Install editable with
`make setup`; Docker images copy it in and `pip install` it first.

| Module | What |
|---|---|
| `simclock` | `SimClock` — the unified `sim_time_us` clock (REALTIME scaled 0.1–10×, or STEPPED for lock-step/replay). |
| `events` | Pydantic models mirroring `schemas/events.proto` (proto-JSON compatible). |
| `config` | `Settings` from `CDSIM_*` env vars; secrets as `SecretStr`. |
| `health` | `health_router()` → `/health` (liveness) and `/ready` (dependency checks, 503 on failure). |
| `manifests` | Schema + semantic validation of platform / area / rubric / scenario YAML. |
| `paths` | Locate the repo root when running from a checkout. |

Tests: `make test-py` (or `.venv/bin/pytest services/common`).
