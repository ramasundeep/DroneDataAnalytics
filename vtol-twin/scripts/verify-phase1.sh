#!/usr/bin/env bash
# Phase 1 acceptance: publish telemetry over MQTT, read it back from the Thing via REST.
. "$(dirname "$0")/common.sh"
AUTH=(-u "${DITTO_USER}:${DITTO_PASSWORD}")
PUB="docker compose exec -T mosquitto mosquitto_pub -h 127.0.0.1 -q 1"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RPM=$(( 5000 + RANDOM % 900 ))

log "1) single-feature publish: vtol/$TAIL_NUMBER/telemetry/engine"
$PUB -t "vtol/$TAIL_NUMBER/telemetry/engine" \
  -m "{\"ts\":\"$TS\",\"rpm\":$RPM,\"egtC\":612.4,\"chtC\":181.0,\"fuelFlowLph\":4.7,\"throttlePct\":68,\"running\":true}"

log "2) multi-feature publish: vtol/$TAIL_NUMBER/telemetry"
$PUB -t "vtol/$TAIL_NUMBER/telemetry" \
  -m "{\"ts\":\"$TS\",\"power\":{\"busVoltageV\":27.9,\"busCurrentA\":6.2},\"vibration\":{\"rmsX\":0.42,\"rmsY\":0.39,\"rmsZ\":0.55,\"rmsTotal\":0.79},\"navigation\":{\"gpsFixType\":3,\"gpsSatellites\":14,\"gpsHdop\":0.8,\"insAligned\":true}}"

log "3) read back from Ditto"
for i in 1 2 3 4 5 6; do
  got=$($CURL "${AUTH[@]}" "$DITTO_BASE/api/2/things/$THING_ID/features/engine/properties/rpm" || true)
  [ "$got" = "$RPM" ] && break; sleep 2
done
[ "$got" = "$RPM" ] || fail "engine.rpm on the Thing is '$got', expected $RPM"
log "engine.rpm = $got (matches published value)"
bus=$($CURL "${AUTH[@]}" "$DITTO_BASE/api/2/things/$THING_ID/features/power/properties/busVoltageV")
[ "$bus" = "27.9" ] || fail "power.busVoltageV is '$bus', expected 27.9"
log "power.busVoltageV = $bus (multi-feature merge works)"

echo; log "Thing features after the publishes:"
$CURL "${AUTH[@]}" "$DITTO_BASE/api/2/things/$THING_ID?fields=thingId,features/engine,features/power,features/vibration,features/navigation" | jq .
echo; log "PHASE 1 VERIFIED"
