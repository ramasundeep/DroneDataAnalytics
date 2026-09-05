# VTOL-1 digital twin - architecture

## Purpose

One twin, two jobs:

1. **Mission simulation and what-if analysis** - PX4 SITL flights stream through the same pipeline as real
   telemetry, so the twin can be exercised without an aircraft.
2. **Predictive maintenance and workflow automation** - health scores, remaining useful life (RUL) and
   alert levels are written back to the twin; alerts open work orders; scheduled inspections are generated
   from life counters.

The aircraft is referred to only as `VTOL-1` (tail number) and `vtol.fleet:VTOL-1` (Ditto Thing ID).

## Layers

| # | Layer | Technology | Role |
|---|---|---|---|
| 1 | Twin state | Eclipse Ditto 3.9 + MongoDB 7 | The aircraft as a Ditto *Thing*: attributes = configuration, features = live state |
| 2 | Connectivity | Eclipse Mosquitto 2 (MQTT 5) | Single ingress for telemetry (real or simulated) and egress for twin events |
| 3 | Time-series | InfluxDB 2.7 + Grafana 12 | Full-rate telemetry history, dashboards (Phase 2) |
| 4 | Analytics | Python / FastAPI | Anomaly detection + RUL, writes `health` feature back to the Thing (Phase 3) |
| 5 | Maintenance | Python / FastAPI + SQLite | Work orders, release status, scheduled-maintenance rules, web UI (Phase 4) |

Simulation feed (Phase 5): PX4 SITL + Gazebo tail-sitter -> MAVLink -> `bridge/` (pymavlink) -> MQTT.

```
 aircraft / PX4 SITL ──MAVLink──▶ bridge ──MQTT vtol/VTOL-1/telemetry/*──▶ Mosquitto
                                                                             │
                     ┌───────────────────────────────────────────────────────┼──────────────┐
                     ▼                                                       ▼              ▼
              Ditto connectivity (JS mapper → twin MERGE)          MQTT→Influx ingester   (other subscribers)
                     │                                                       │
                     ▼                                                       ▼
        Ditto Thing vtol.fleet:VTOL-1  ◀── health/RUL ── analytics ◀── InfluxDB ◀── ulog batch ingester
                     │ twin events                                           │
                     ▼                                                       ▼
        MQTT vtol/VTOL-1/events ──▶ maintenance service ──▶ work orders    Grafana
```

## Twin state model

Thing `vtol.fleet:VTOL-1`, policy `vtol.fleet:vtol-policy` (`ditto/thing-VTOL-1.json`, `ditto/policy.json`).

**Attributes** (static configuration; changed only by maintenance actions):

* `tailNumber`, `class`, `airframe` (serial, dates, total hours/landings, MTOW, fuel type)
* `components.<id>` for the ten tracked components - `engine`, `ductedFan`, `fuelPump`, `servo1..servo4`
  (positions: elevon-left, elevon-right, thrust-vane-A, thrust-vane-B), `avionics`, `payloadGimbal`,
  `battery`. Each carries `partNumber`, `serial`, `installDate`, `lifeLimitHours`, `lifeLimitCycles`
  and the `hoursConsumed` / `cyclesConsumed` recorded at the last maintenance-record update.
* `maintenance` - last inspection, next due.

**Features** (live values; updated by telemetry, ingesters and the analytics service):

| Feature | Written by | Content |
|---|---|---|
| `engine` | telemetry | RPM, EGT, CHT, fuel flow, throttle, oil pressure |
| `vibration` | telemetry | accelerometer RMS per axis + total, clip count |
| `actuation` | telemetry | servo currents and positions (4 servos) |
| `power` | telemetry | bus voltage/current, battery voltage/current/remaining/temperature |
| `navigation` | telemetry | GPS fix/satellites/HDOP, INS status |
| `flightState` | telemetry | sortie ID, armed, flight mode, VTOL state, position, speeds, flight time |
| `lifeCounters` | ingester (Phase 2) | cumulative hours and cycles per component, last sortie |
| `health` | analytics (Phase 3), maintenance (Phase 4) | per-component `healthScore`, `rulHours`, `alertLevel`; aircraft `releaseStatus` |

Every telemetry feature has a `ts` property (ISO-8601 UTC) carrying the source timestamp of the last
update, distinct from Ditto's own `_modified`.

Why attributes *and* `lifeCounters`: attributes are the maintenance record (what the logbook says at
install / last sign-off); `lifeCounters` is the running total the ingester advances after every sortie.
The difference between the two is the flight time since the last maintenance record.

## MQTT topic scheme

| Topic | Direction | Payload |
|---|---|---|
| `vtol/<tail>/telemetry/<feature>` | in | flat JSON of that feature's properties, optional `ts` |
| `vtol/<tail>/telemetry` | in | `{ "ts": ..., "<feature>": {...}, "<feature>": {...} }` |
| `vtol/<tail>/events` | out | Ditto Protocol twin events (feature/attribute changes) |

The Ditto connection `mqtt-telemetry` (`ditto/connection-mqtt.json`) subscribes to both inbound shapes.
The JavaScript mapper (`ditto/mapping/telemetry-incoming.js`) derives the Thing name from the topic and
emits a **twin MERGE command** on `/features` with a JSON merge patch, so partial messages never clear
properties that were not included. Unparseable messages are dropped (visible in the connection's logs
via `GET /api/2/connections/mqtt-telemetry/logs`).

Ingesters and services publish with the same topics, so real, replayed and simulated data are
indistinguishable downstream.

## Security posture (single-operator prototype)

* Ditto is reached only through nginx. nginx terminates basic auth (users generated from `.env` into a
  git-ignored htpasswd) and forwards `x-ditto-pre-authenticated: nginx:<user>`. The policy grants
  `nginx:ditto` full access, `nginx:analytics` / `nginx:maintenance` feature + attribute write, and the
  connection subject `integration:mqtt-telemetry` feature write only.
* The connections API is protected by Ditto's devops password (`DITTO_DEVOPS_PASSWORD`).
* Mosquitto allows anonymous clients on the compose network / localhost. For a field deployment add a
  `password_file` and TLS listener; the Ditto connection URI then carries the credentials.
* No cloud services; every image and package is pinned (`VERSIONS.md`) and cached locally after the
  first pull.

## Demo mode (`demo/`)

A FastAPI service that stands in for the whole pipeline when no Docker host is available, and doubles
as a synthetic telemetry source when it is:

* `simulator.py` - deterministic sortie profile (preflight, engine start, hover climb, forward
  transition, fixed-wing cruise on a racetrack, back transition, hover descent, landing, shutdown)
  emitting exactly the feature/property names of the Thing model at 1 Hz simulated time. Three
  injectable faults: vibration rise (ducted fan), EGT drift (engine), servo3 current creep. Wear
  accumulates across sorties on a compressed timeline.
* `twin.py` - in-memory Thing with the same JSON-merge-patch semantics the Ditto mapper produces,
  life-counter accrual per sortie, and a compact preview of the Phase 3/4 logic: condition scoring
  from sortie statistics (mean vs nominal/threshold, peak exceedance), least-squares trend
  projection over the cruise segment, alert levels, auto work orders with evidence, sign-off and
  release status. Phases 3 and 4 replace this with the InfluxDB-backed analytics service and the
  SQLite work-order service; the scoring constants are the starting point for those.
* `publisher.py` - optional mirror onto `vtol/<tail>/telemetry` (paho-mqtt) so the real stack
  receives identical data.
* `static/` - single-page UI over Server-Sent Events, no external assets (offline-capable).

## Time-series (Phase 2 onward)

InfluxDB bucket `flight_telemetry`, one measurement per feature group, tagged `tail`, `sortie`,
`source` (`live` / `ulog` / `sitl`). Grafana is provisioned as code from `grafana/provisioning` and
`dashboards/`.

## Persistence

Docker volumes: `mongodb-data` (twin state + connection definitions), `mosquitto-data`,
`influxdb-data`/`influxdb-config`, `grafana-data`. `make clean` removes them all.
Work orders (Phase 4) live in SQLite under `maintenance/data/`; the schema is kept plain SQL so moving
to Postgres is a connection-string change plus `serial` -> `identity` columns.
