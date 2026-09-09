#!/usr/bin/env bash
# Phase 3 acceptance: the analytics service flags the degraded sample sorties and the Thing carries health.
. "$(dirname "$0")/common.sh"
: "${ANALYTICS_PORT:=8092}"
AUTH=(-u "${DITTO_USER}:${DITTO_PASSWORD}")
AURL="http://localhost:${ANALYTICS_PORT}"

log "1) analytics service health"
for i in $(seq 1 20); do
  $CURL -fs "$AURL/health" >/dev/null 2>&1 && break; sleep 3
done
$CURL "$AURL/health" | jq -c .

log "2) run analytics now (over everything in InfluxDB for $TAIL_NUMBER)"
res=$($CURL -X POST "$AURL/run")
echo "$res" | jq -r '"sorties scored: \(.sorties|length)  worst alert: \(.worstAlert)"'
echo "$res" | jq -r '.flaggedSorties[]' | sed 's/^/  flagged: /'
n=$(echo "$res" | jq '.flaggedSorties|length')
[ "$n" -ge 4 ] || fail "expected the degraded sample sorties to be flagged, got $n"
for idx in 7 12 13 14 18; do
  echo "$res" | jq -e --argjson i "$idx" '.sorties[$i-1].flagged' >/dev/null || fail "sample sortie $idx not flagged"
done
echo "$res" | jq -r '.sorties[] | select(.flagged) | "  \(.sortieId): " + ([.groups | to_entries[] | select(.value.flagged) | "\(.key) z=\(.value.zmax) top=\(.value.top[0][0] // "limit")"] | join(", "))'

log "3) Thing health feature"
h=$($CURL "${AUTH[@]}" "$DITTO_BASE/api/2/things/$THING_ID/features/health/properties")
echo "$h" | jq '{lastRun, servo3: .servo3 | {healthScore, rulHours, alertLevel}, ductedFan: .ductedFan | {healthScore, rulHours, alertLevel}, engine: .engine | {healthScore, rulHours, alertLevel}}'
[ "$(echo "$h" | jq -r '.lastRun.sortiesScored')" -ge 20 ] || fail "Thing health.lastRun does not reflect the run"
[ "$(echo "$h" | jq -r '.servo3.alertLevel')" = "caution" ] || fail "servo3 should be at caution after the sortie-18 exceedance"

log "4) health points in InfluxDB"
echo; log "PHASE 3 VERIFIED"
