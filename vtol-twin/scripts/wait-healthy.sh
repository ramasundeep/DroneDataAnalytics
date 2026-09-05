#!/usr/bin/env bash
# Blocks until every compose service with a healthcheck reports healthy (default timeout 420 s).
. "$(dirname "$0")/common.sh"
TIMEOUT="${1:-420}"
deadline=$(( $(date +%s) + TIMEOUT ))
while :; do
  unhealthy=$(docker compose ps --format json 2>/dev/null \
    | jq -rs '[ .[] | (if type=="array" then .[] else . end) | select(.Health != "" and .Health != "healthy") | "\(.Service)=\(.Health)" ] | join(" ")')
  if [ -z "$unhealthy" ]; then log "all services healthy"; break; fi
  if [ "$(date +%s)" -ge "$deadline" ]; then fail "timeout waiting for: $unhealthy"; fi
  log "waiting: $unhealthy"; sleep 10
done
# Ditto's /health only turns 200 once the cluster is fully joined.
until [ "$($CURL -o /dev/null -w '%{http_code}' "$DITTO_BASE/health")" = "200" ]; do
  [ "$(date +%s)" -ge "$deadline" ] && fail "Ditto /health not 200"
  log "waiting for Ditto cluster health"; sleep 10
done
log "Ditto healthy: $($CURL "$DITTO_BASE/health" | jq -c .)"
