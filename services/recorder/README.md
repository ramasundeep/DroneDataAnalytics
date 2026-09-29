# services/recorder — session recording on the unified sim clock

Ingests everything a session produces and stores it ordered by
`(sim_time_us, seq)` — never wall-clock. Design: `docs/02_ARCHITECTURE.md`
§"Unified time base", `docs/06_ASSESSMENT_ENGINE.md` §"Session file".

| Route | Status |
|---|---|
| `POST /v1/events` (`EventBatch`, proto-JSON) | ✅ validates, stores to TimescaleDB (idempotent on `event_id`), publishes to Redis `cdsim.session.<id>.events` (best-effort) |
| `GET /v1/sessions/{id}/events?family=&from_us=&to_us=` | ✅ ordered read-back — the basis of replay |
| Telemetry / control-input ingest | ⏳ Phase 1 (tables already exist) |
| Audio chunk ingest to MinIO | ⏳ Phase 3 |
| Session-file export (`events.pb`, `telemetry.pb`, …) | ⏳ Phase 1 |

Database schema: `db/001_init.sql` (applied by the TimescaleDB container on
first start). Storage/publisher are protocols (`store.py`) so tests use
in-memory fakes.
