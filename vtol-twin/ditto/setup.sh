#!/usr/bin/env bash
# Idempotently creates the VTOL-1 policy, Thing and the Mosquitto<->Ditto connection.
#   ./ditto/setup.sh            # create what is missing, update policy + connection
#   ./ditto/setup.sh --reset    # also overwrite the Thing with the model file (live values are lost)
. "$(dirname "$0")/../scripts/common.sh"
RESET=false; [ "${1:-}" = "--reset" ] && RESET=true
AUTH=(-u "${DITTO_USER}:${DITTO_PASSWORD}")
DEVOPS=(-u "devops:${DITTO_DEVOPS_PASSWORD}")
JSON=(-H "Content-Type: application/json")

# --- policy (always upserted: it is configuration, not state)
code=$($CURL "${AUTH[@]}" "${JSON[@]}" -o /dev/null -w '%{http_code}' -X PUT \
  "$DITTO_BASE/api/2/policies/$POLICY_ID" --data-binary @ditto/policy.json)
[[ "$code" =~ ^20[01]|204$ ]] || fail "policy PUT returned $code"
log "policy $POLICY_ID: HTTP $code"

# --- thing (created once; --reset overwrites)
code=$($CURL "${AUTH[@]}" -o /dev/null -w '%{http_code}' "$DITTO_BASE/api/2/things/$THING_ID")
if [ "$code" = "404" ] || $RESET; then
  code=$($CURL "${AUTH[@]}" "${JSON[@]}" -o /dev/null -w '%{http_code}' -X PUT \
    "$DITTO_BASE/api/2/things/$THING_ID" --data-binary @ditto/thing-VTOL-1.json)
  [[ "$code" =~ ^20[01]|204$ ]] || fail "thing PUT returned $code"
  log "thing $THING_ID: written (HTTP $code)"
elif [ "$code" = "200" ]; then
  log "thing $THING_ID: exists, left untouched (use --reset to overwrite)"
else
  fail "thing GET returned $code"
fi

# --- connection (upserted with the mapper scripts embedded)
CONN_ID=mqtt-telemetry
body=$(jq --rawfile inc ditto/mapping/telemetry-incoming.js --rawfile out ditto/mapping/telemetry-outgoing.js \
  '.mappingDefinitions.telemetryMapping.options.incomingScript = $inc
   | .mappingDefinitions.telemetryMapping.options.outgoingScript = $out' ditto/connection-mqtt.json)
code=$(printf '%s' "$body" | $CURL "${DEVOPS[@]}" "${JSON[@]}" -o /tmp/ditto-conn.out -w '%{http_code}' -X PUT \
  "$DITTO_BASE/api/2/connections/$CONN_ID" --data-binary @-)
[[ "$code" =~ ^20[01]|204$ ]] || { cat /tmp/ditto-conn.out; fail "connection PUT returned $code"; }
log "connection $CONN_ID: HTTP $code"
for i in $(seq 1 12); do
  status=$($CURL "${DEVOPS[@]}" "$DITTO_BASE/api/2/connections/$CONN_ID/status" | jq -r '.liveStatus // "unknown"')
  [ "$status" = "open" ] && break
  log "connection liveStatus=$status, waiting"; sleep 5
done
[ "$status" = "open" ] || fail "connection did not open (liveStatus=$status); check: docker compose logs connectivity"
log "connection $CONN_ID is open"
