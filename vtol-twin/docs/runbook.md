# VTOL-1 twin - runbook (cold start to demo)

**Host needs:** Docker Engine with Compose v2, `curl`, `jq`, `make`, GNU bash; ~4 GB RAM free for the
stack (Ditto runs five JVMs). Optional: `node` and `python3 -m pytest` for the unit tests. No cloud
access is required after the images are pulled once.

## 0. Demo mode (no Docker)

```bash
cd vtol-twin
pip install -r demo/requirements.txt
make demo-ui                 # http://localhost:8090
```

The demo UI flies synthetic sorties (hover, transition, cruise, transition, land) against an in-memory
copy of the Thing model. Pick a fault (rising vibration, EGT drift, servo current creep), a severity and
a playback speed, press **Start sortie**, and watch the live features, sparklines, component life bars,
health scores and alerts. Wear accumulates across sorties: severity 1 trips an alert in one flight, 0.5
builds up over several. A caution opens a work order with the evidence; sign it off (repaired /
replaced / no fault found) and the release status returns to serviceable. **Reset twin** reloads the
model file.

When the full stack is up, `make demo-ui-live` runs the same service as a container with
`MQTT_HOST=mosquitto`, so every sample also flows through Mosquitto into Ditto (check the Ditto UI or
`GET /api/2/things/vtol.fleet:VTOL-1/features/engine`). Running on the host with `MQTT_HOST=localhost`
in `demo/.env` does the same.

## 1. Configure

```bash
cd vtol-twin
cp .env.example .env        # change the *-change-me values; ports if 8080/1883/8086/3000 are taken
```

## 2. Start and verify (Phase 1)

```bash
make demo                   # = make up && make wait && make setup && make verify-phase1
```

What that does:

| Step | Command | Expect |
|---|---|---|
| start | `make up` | generates `ditto/nginx/nginx.htpasswd` from `.env`, `docker compose up -d` |
| health | `make wait` | every service `healthy` (Ditto takes 1-3 min the first time); Ditto `/health` = 200 |
| twin | `make setup` | policy + Thing created, connection `mqtt-telemetry` `liveStatus: open` |
| verify | `make verify-phase1` | publishes engine + multi-feature telemetry via `mosquitto_pub`, reads the Thing back, prints `PHASE 1 VERIFIED` |

## 3. Look around

| What | Where | Login |
|---|---|---|
| Ditto explorer UI | http://localhost:8080/ui/ | `DITTO_USER` / `DITTO_PASSWORD` |
| Thing via REST | `curl -u ditto:ditto http://localhost:8080/api/2/things/vtol.fleet:VTOL-1 \| jq .` | same |
| One property | `.../things/vtol.fleet:VTOL-1/features/engine/properties/rpm` | same |
| Connection status | `curl -u devops:$DITTO_DEVOPS_PASSWORD http://localhost:8080/api/2/connections/mqtt-telemetry/status` | devops |
| Grafana | http://localhost:3000 | `GRAFANA_ADMIN_*` |
| InfluxDB | http://localhost:8086 | `INFLUXDB_INIT_*` |

Publish your own telemetry from the host (any MQTT client):

```bash
mosquitto_pub -h localhost -t vtol/VTOL-1/telemetry/engine \
  -m '{"ts":"2026-09-05T12:00:00Z","rpm":5300,"egtC":605.1,"chtC":178.4,"fuelFlowLph":4.6}'
# or without host tools:
docker compose exec mosquitto mosquitto_pub -t vtol/VTOL-1/telemetry/power -m '{"busVoltageV":28.1}'
```

Watch twin events leave Ditto:

```bash
docker compose exec mosquitto mosquitto_sub -t 'vtol/+/events' -v
```

## 4. Everyday operations

```bash
make ps                      # health of every container
make logs SERVICE=connectivity
make setup                   # re-apply policy/connection after editing ditto/*.json or the mapper
make reset-thing             # restore the Thing from ditto/thing-VTOL-1.json (loses live values)
make test                    # mapper (node) + model/compose + demo + bridge + analytics (pytest)
make down                    # stop, keep data
make clean                   # stop and delete all volumes
```

## 5. Troubleshooting

* **`make wait` times out on Ditto services** - first start on a slow disk can exceed the 120 s
  `start_period`; run `make wait` again. Check `docker compose logs gateway` for `Cluster ... is up`.
* **Connection `liveStatus` is `failed`** - `docker compose logs connectivity`; a mapper syntax error
  shows here. `GET /api/2/connections/mqtt-telemetry/logs` (devops auth) lists dropped messages.
* **401 from `/api`** - htpasswd out of date after changing `.env`: `make htpasswd && docker compose restart ditto-nginx`.
* **InfluxDB refuses to start after changing `.env`** - the init variables only apply to an empty
  volume; `make clean` or change them back.
* **Port clash** - change `DITTO_EXTERNAL_PORT`, `MQTT_PORT`, `INFLUXDB_PORT`, `GRAFANA_PORT` in `.env`.

## 6. Telemetry pipeline (Phase 2)

Host needs `pip install -r bridge/requirements.txt` (pyulog, influxdb-client, paho-mqtt, httpx).

```bash
make ingest-dry-run          # parse the 20 sample sorties, print per-sortie peaks (no services needed)
make ingester-up             # MQTT -> InfluxDB ingester container (profile "pipeline"), health on :8091
make ingest-samples          # .ulg -> InfluxDB + lifeCounters on the Thing (idempotent per sortie id)
make verify-phase2           # both of the above + checks: Influx counts, Thing hours, dashboards
make gen-samples             # regenerate data/samples (deterministic)
```

`make verify-phase2` ends with `PHASE 2 VERIFIED` and prints the Thing's engine / airframe hours,
which must exceed the model file's 142.6 h by the 3.25 h of sample sorties. Re-running
`make ingest-samples` rewrites telemetry (idempotent in InfluxDB) but never double-counts hours: the
Thing remembers ingested sortie ids in `lifeCounters.ingestedSorties`.

Dashboards (Grafana, folder "VTOL-1"): `/d/vtol-fleet-health`, `/d/vtol-sortie-engine` (pick a
sortie in the variable bar; set the time range to August 2026 for the samples), `/d/vtol-component-life`.

Ingest your own PX4 logs: `python -m bridge.ulog_ingest --tail VTOL-1 /path/to/log.ulg`. Logs without
the custom topics still yield engine (if an ICE status topic exists), power, navigation and flight
state; hours are booked from `vehicle_status`.

Live telemetry goes through the same ingester: anything published on `vtol/<tail>/telemetry[/<feature>]`
(the demo UI with `MQTT_HOST` set, the Phase 5 SITL bridge, or the aircraft) lands in InfluxDB tagged
`source=live`.

## 7. Predictive maintenance (Phase 3)

Host needs `pip install -r analytics/requirements.txt` (adds scikit-learn, pandas).

```bash
make analytics-run           # offline: score the 20 sample sorties, print per-sortie anomalies + component health
make analytics-up            # analytics service container (profile "pipeline"), API on :8092
make verify-phase3           # POST /run, check the degraded sorties are flagged and the Thing carries health
make analytics-write         # one-off: score from InfluxDB on the host and write to the Thing
```

`make analytics-run` needs nothing running: it prints a table with one row per sortie (anomaly score,
robust z and IsolationForest z per group, flag, injected fault) and one per component (health score,
RUL, trend RUL, alert, indicator level vs limit). Expected: sorties 07, 12, 13, 14 and 18 flagged,
all others clean, servo 3 at caution at the end (recent exceedance), everything else normal.

The service re-scores after every ingested sortie (it listens for `lifeCounters` events on
`vtol/+/events`) and every `ANALYTICS_INTERVAL_S`. Results: `GET http://localhost:8092/latest`,
Thing feature `health` (`.../features/health/properties`), Grafana fleet dashboard (health bars),
InfluxDB measurements `health` and `anomaly`. Method: `docs/analytics.md`.

Later phases add to this page: work-order UI (Phase 4), `sim/` SITL launch (Phase 5).
