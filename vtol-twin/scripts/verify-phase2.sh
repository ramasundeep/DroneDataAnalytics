#!/usr/bin/env bash
# Phase 2 acceptance: sample sorties are in InfluxDB, dashboards are provisioned, Thing hours advanced.
. "$(dirname "$0")/common.sh"
: "${INFLUXDB_PORT:=8086}"; : "${INFLUXDB_ORG:=vtol}"; : "${INFLUXDB_BUCKET:=flight_telemetry}"; : "${INFLUXDB_TOKEN:?}"
: "${GRAFANA_PORT:=3000}"; : "${GRAFANA_ADMIN_USER:=admin}"; : "${GRAFANA_ADMIN_PASSWORD:?}"; : "${INGEST_PORT:=8091}"
AUTH=(-u "${DITTO_USER}:${DITTO_PASSWORD}")
IURL="http://localhost:${INFLUXDB_PORT}"

flux() { $CURL -X POST "$IURL/api/v2/query?org=$INFLUXDB_ORG" -H "Authorization: Token $INFLUXDB_TOKEN" \
  -H "Content-Type: application/vnd.flux" -H "Accept: application/csv" --data-binary "$1"; }

log "1) sorties in InfluxDB"
n=$(flux "from(bucket: \"$INFLUXDB_BUCKET\") |> range(start: -5y) |> filter(fn: (r) => r._measurement == \"sortie_summary\" and r._field == \"flight_hours\") |> group() |> count()" | tail -n +2 | awk -F, 'NF>3{print $NF}' | tr -d '\r' | tail -1)
[ "${n:-0}" -ge 20 ] || fail "expected >= 20 sortie_summary points, found '${n:-0}'"
log "sortie_summary points: $n"
eng=$(flux "from(bucket: \"$INFLUXDB_BUCKET\") |> range(start: -5y) |> filter(fn: (r) => r._measurement == \"engine\" and r._field == \"rpm\") |> group() |> count()" | tail -n +2 | awk -F, 'NF>3{print $NF}' | tr -d '\r' | tail -1)
log "engine.rpm samples: ${eng:-0}"; [ "${eng:-0}" -gt 5000 ] || fail "too few engine samples"

log "2) Thing life counters"
c=$($CURL "${AUTH[@]}" "$DITTO_BASE/api/2/things/$THING_ID/features/lifeCounters/properties")
echo "$c" | jq '{engine, airframe, lastSortieId, lastSortieHours, ingested: (.ingestedSorties|length)}'
[ "$(echo "$c" | jq '.ingestedSorties|length')" -ge 20 ] || fail "Thing has fewer than 20 ingested sorties"
[ "$(echo "$c" | jq '.engine.hours > 142.6')" = "true" ] || fail "engine hours did not advance"

log "3) MQTT ingester health"
$CURL "http://localhost:${INGEST_PORT}/health" | jq -c .

log "4) Grafana dashboards provisioned"
for uid in vtol-fleet-health vtol-sortie-engine vtol-component-life; do
  title=$($CURL -u "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}" "http://localhost:${GRAFANA_PORT}/api/dashboards/uid/$uid" | jq -r '.dashboard.title // "MISSING"')
  [ "$title" != "MISSING" ] || fail "dashboard $uid not provisioned"
  log "  $uid -> $title  http://localhost:${GRAFANA_PORT}/d/$uid"
done
echo; log "PHASE 2 VERIFIED"
