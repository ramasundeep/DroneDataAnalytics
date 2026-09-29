# services/

Python 3.11 / FastAPI platform services. One package per service
(`services/<name>/src/cdsim_<name>/`), all sharing `services/common`
(`cdsim_common`). Images are built from the single recipe `services/Dockerfile`
with `PACKAGE=<dir>` (see `docker-compose.yml`).

| Service | Port | Phase 0 scope | README |
|---|---|---|---|
| `common` | — | clock, events, config, health, manifests, bootstrap | `common/README.md` |
| `api` | 8000 | catalogue, aggregate health, 501 stubs for later phases | `api/README.md` |
| `recorder` | 8001 | event ingest + ordered read-back, Redis fan-out | `recorder/README.md` |
| `assessment` | 8002 | rubric scoring + validation; metric definitions | `assessment/README.md` |
| `sitl` | 5760 | ArduPilot SITL image (UNVERIFIED) + JSON-physics codec | `sitl/README.md` |
| `rl` | — | precision-landing reward/curriculum, env interface | `rl/README.md` |

Every HTTP service exposes `/health` (liveness), `/ready` (dependency checks;
503 when degraded) and `/openapi.json`. Swagger/ReDoc pages are disabled
because they load from a CDN (offline-first).

Run one service outside Docker against the `make dev` infrastructure:

```bash
.venv/bin/uvicorn --factory cdsim_api.main:create_app --reload --port 8010
```
