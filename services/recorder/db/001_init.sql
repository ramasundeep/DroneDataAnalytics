-- CD Sim recording schema (PostgreSQL 16 + TimescaleDB).
-- Applied automatically on first start of the timescaledb container
-- (mounted into /docker-entrypoint-initdb.d). For later changes add
-- 002_*.sql etc. and a migration note in docs/CHANGELOG.md.
--
-- Ordering rule: rows are ordered by (sim_time_us, seq) — the unified sim
-- clock. `recorded_at` (wall-clock at ingest) exists only so TimescaleDB can
-- partition and apply retention; never order or join by it.
-- See docs/02_ARCHITECTURE.md §"Unified time base".

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    kind            TEXT NOT NULL,
    area_id         TEXT,
    scenario_id     TEXT,
    rubric_id       TEXT,
    manifest        JSONB NOT NULL,          -- cdsim.v1.SessionManifest as JSON
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id      TEXT        NOT NULL,
    sim_time_us     BIGINT      NOT NULL CHECK (sim_time_us >= 0),
    seq             BIGINT      NOT NULL DEFAULT 0,
    wall_time_us    BIGINT      NOT NULL DEFAULT 0,
    event_id        TEXT        NOT NULL,
    related_event_id TEXT       NOT NULL DEFAULT '',
    actor_id        TEXT        NOT NULL,
    source          TEXT        NOT NULL,
    family          TEXT        NOT NULL CHECK (family IN ('stimulus','response','outcome','annotation')),
    code            TEXT        NOT NULL DEFAULT '',
    body            JSONB       NOT NULL     -- full cdsim.v1.Event (proto JSON)
);
SELECT create_hypertable('events', 'recorded_at', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS events_session_time ON events (session_id, sim_time_us, seq);
-- Idempotency on event_id is enforced by the recorder (advisory lock +
-- NOT EXISTS), because TimescaleDB unique indexes must include the
-- partition column and a retry arrives with a different recorded_at.
CREATE INDEX IF NOT EXISTS events_event_id ON events (event_id);

CREATE TABLE IF NOT EXISTS vehicle_state (
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id      TEXT        NOT NULL,
    vehicle_id      TEXT        NOT NULL,
    sim_time_us     BIGINT      NOT NULL CHECK (sim_time_us >= 0),
    seq             BIGINT      NOT NULL DEFAULT 0,
    lat_deg         DOUBLE PRECISION,
    lon_deg         DOUBLE PRECISION,
    alt_msl_m       DOUBLE PRECISION,
    body            JSONB       NOT NULL     -- full cdsim.v1.VehicleState (proto JSON)
);
SELECT create_hypertable('vehicle_state', 'recorded_at', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS vehicle_state_session_time
    ON vehicle_state (session_id, vehicle_id, sim_time_us, seq);

CREATE TABLE IF NOT EXISTS control_input (
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id      TEXT        NOT NULL,
    vehicle_id      TEXT        NOT NULL,
    sim_time_us     BIGINT      NOT NULL CHECK (sim_time_us >= 0),
    seq             BIGINT      NOT NULL DEFAULT 0,
    body            JSONB       NOT NULL
);
SELECT create_hypertable('control_input', 'recorded_at', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS control_input_session_time
    ON control_input (session_id, vehicle_id, sim_time_us, seq);
