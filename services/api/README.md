# services/api — CD Sim platform API

FastAPI service the instructor console (and later the UE5 client and
scenario runner) talks to. Spec context: `docs/02_ARCHITECTURE.md`.

| Route | Status |
|---|---|
| `GET /health`, `GET /ready` | ✅ `/ready` checks postgres (+timescaledb extension), redis, minio bucket, manifests |
| `GET /v1/version` | ✅ |
| `GET /v1/system/health` | ✅ aggregates every service's `/ready` (`CDSIM_SERVICE_URLS`) |
| `GET /v1/platforms[/{id}]`, `/v1/areas[/{id}]`, `/v1/scenarios[/{id}]`, `/v1/rubrics` | ✅ read-only catalogue from mounted manifests |
| `GET/POST /v1/sessions`, `/v1/sessions/{id}/replay`, `/score`, `/v1/trainees` | ⏳ HTTP 501 naming the delivering phase |

Code: `src/cdsim_api/main.py` (app factory), `catalogue.py`, `system.py`.
Tests: `tests/test_api.py`. Run: `uvicorn --factory cdsim_api.main:create_app --port 8000`.
