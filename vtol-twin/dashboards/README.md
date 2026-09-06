# Grafana dashboards (provisioned as code)

Mounted read-only into Grafana and loaded by `grafana/provisioning/dashboards/dashboards.yml` (folder "VTOL-1").
All queries are Flux against the provisioned datasource `influxdb-flight-telemetry`, bucket `flight_telemetry`.

| File | UID | Purpose |
|---|---|---|
| `fleet-health-overview.json` | `vtol-fleet-health` | Sorties / hours / landings in range, peak EGT-vibration-servo current, component health score (fed by the Phase 3 analytics `health` measurement), life used %, per-sortie peaks, sortie log table |
| `sortie-engine-trends.json` | `vtol-sortie-engine` | Pick a sortie (`sortie` variable): RPM/throttle, EGT/CHT with limit lines, fuel/oil, vibration RMS per axis, servo currents, flight profile, power, GPS |
| `component-life.json` | `vtol-component-life` | Hours remaining, hours used %, cycles used % per component (bar gauges) and cumulative hours over time |

Edit the JSON directly (Grafana's "Save as JSON" output is compatible) and keep the `uid`s stable, since the maintenance service links work
orders to `/d/vtol-sortie-engine?var-sortie=<id>&from=<t0>&to=<t1>` (Phase 4).
