# ADR 0006: PostgreSQL + TimescaleDB for events and telemetry

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-29 |
| Deciders | CDPL founding engineering |
| Supersedes | — |
| Superseded by | — |

## Context

Every session records world events, instructor injects, control inputs and
vehicle state (50 Hz) on the unified clock ([0015](0015-unified-sim-time-base.md)).
The assessment engine needs to query a session's rows **in sim-time order**
and join responses to stimuli; the console needs session metadata and trainee
records (relational); retention must be enforceable (old sessions expire).
It must run offline on a single box. The founding brief fixes
"PostgreSQL + TimescaleDB".

## Decision

We use **PostgreSQL 16 with the TimescaleDB extension**, image
`timescale/timescaledb:2.16.1-pg16`, as the system of record for session
metadata, events and time-series.

Schema: `services/recorder/db/001_init.sql`, applied on first container start
via `/docker-entrypoint-initdb.d`. Later changes are new numbered files
(`002_*.sql`) plus a `docs/CHANGELOG.md` note.

| Table | Kind | Key columns |
|---|---|---|
| `sessions` | plain | `session_id` PK, kind, area/scenario/rubric ids, `manifest` JSONB |
| `events` | hypertable | `session_id`, `sim_time_us`, `seq`, `event_id`, family, code, `body` JSONB |
| `vehicle_state` | hypertable | `session_id`, `vehicle_id`, `sim_time_us`, `seq`, lat/lon/alt, `body` |
| `control_input` | hypertable | `session_id`, `vehicle_id`, `sim_time_us`, `seq`, `body` |

**Partition on `recorded_at`, order on `sim_time_us`.** Hypertables are
partitioned (chunked) on `recorded_at`, the wall-clock ingest time. This is
used **only** so TimescaleDB can chunk data and drop old chunks for retention;
`sim_time_us` restarts at 0 in every session and so cannot serve as a global
partition key. All reads order by `(sim_time_us, seq)` via the indexes
`(session_id[, vehicle_id], sim_time_us, seq)`. **No query may order or join
by `recorded_at` or `wall_time_us`.**

Other rules:

- `sim_time_us >= 0` is a `CHECK` constraint.
- Full messages are stored as proto3-JSON in `body`; extracted columns exist
  only for filtering and indexing.
- Event ingest must be idempotent on `event_id`. TimescaleDB requires the
  partition column in every unique index, so the index is
  `(event_id, recorded_at)` and the recorder inserts with `ON CONFLICT DO
  NOTHING`. That de-duplicates within one batch/transaction, **but not a
  retry arriving later** (different `recorded_at`). Closing this gap is a
  Phase 1 recorder task (see Risks).
- **Telemetry is disabled** (`TIMESCALEDB_TELEMETRY=off`) — offline-first,
  no phone-home.
- Host port bound to `127.0.0.1` only.

## Status (Phase 0)

- Schema exists and was applied by the container under `make dev`; the
  recorder round-trip (POST events → TimescaleDB → GET ordered by
  `(sim_time_us, seq)`) was verified locally by `tests/test_integration_stack.py`.
- `vehicle_state` and `control_input` tables exist but nothing writes them
  yet (Phase 1).
- Retention and compression policies are **not configured** yet; they arrive
  with session management (Phase 3/4). Backup/restore is Phase 8.

## Consequences

### Positive

- One database for relational and time-series data; SQL joins between
  sessions, events and telemetry.
- Chunk-based retention drops whole partitions cheaply.
- PostgreSQL is familiar; tooling and backups are well understood.

### Negative

- `recorded_at` is a second timestamp that engineers may be tempted to use;
  guarded by comments, code review and [0015](0015-unified-sim-time-base.md).
- A replayed or re-imported session gets new `recorded_at` values; retention
  counts from import, not from the original run.
- JSONB `body` duplicates some extracted columns.

### Risks

| Risk | Mitigation |
|---|---|
| Someone orders by `recorded_at` | SQL comments; review checklist; tests assert sim-time order with shuffled ingest |
| Write volume at many vehicles × 50 Hz | Move to COPY-based batched ingest; compression policy; measure in Phase 5 |
| Extension licence terms change | Only community features used; revisit trigger below |
| Unique index includes `recorded_at` (hypertable requirement), so the DB cannot enforce global `event_id` uniqueness; a client retry in a later request can duplicate a row | Known Phase 0 gap: the in-memory store test covers duplicates, the Postgres path does not. Phase 1: check existence per `(session_id, event_id)` before insert, or de-duplicate on read |

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Plain PostgreSQL | Works initially, but loses cheap chunk retention and compression for telemetry. |
| A dedicated time-series database | Second datastore to operate; weak relational joins to sessions/trainees. |
| Partition on `sim_time_us` | Resets every session; chunks would mix sessions and never age out. |
| Files only (session protobuf files in MinIO) | Kept as the export/replay format, but assessment and console need indexed queries. |

## Revisit when

- Measured ingest at Phase 5 fleet load (4 clients) cannot keep up.
- Retention requirements need per-session deletion that chunk drops cannot
  express (then add explicit delete jobs or partition by session).
- TimescaleDB community licensing or image availability changes.
