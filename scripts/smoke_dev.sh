#!/usr/bin/env bash
# Smoke test for `make dev`: every Phase-0 service must answer /ready with
# HTTP 200, and the console must reach the API through its /api proxy.
# Reads host ports from .env (falls back to .env.example defaults).
set -uo pipefail

cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
if [[ -f .env ]]; then source .env; else source .env.example; fi
set +a

declare -a CHECKS=(
  "api|http://127.0.0.1:${CDSIM_API_PORT}/ready"
  "recorder|http://127.0.0.1:${CDSIM_RECORDER_PORT}/ready"
  "assessment|http://127.0.0.1:${CDSIM_ASSESSMENT_PORT}/ready"
  "terrain-tiles|http://127.0.0.1:${CDSIM_TILES_PORT}/ready"
  "terrain-mesh|http://127.0.0.1:${CDSIM_MESH_PORT}/ready"
  "terrain-elevation|http://127.0.0.1:${CDSIM_ELEVATION_PORT}/ready"
  "terrain-weather|http://127.0.0.1:${CDSIM_WEATHER_PORT}/ready"
  "console|http://127.0.0.1:${CDSIM_CONSOLE_PORT}/healthz"
  "console→api|http://127.0.0.1:${CDSIM_CONSOLE_PORT}/api/v1/system/health"
)

fail=0
for entry in "${CHECKS[@]}"; do
  name="${entry%%|*}"; url="${entry#*|}"
  code=$(curl -s -o /tmp/cdsim-smoke.$$ -w '%{http_code}' --max-time 5 "$url")
  if [[ "$code" == "200" ]]; then
    printf '  \033[32mOK\033[0m    %-18s %s\n' "$name" "$url"
  else
    printf '  \033[31mFAIL\033[0m  %-18s %s (HTTP %s)\n' "$name" "$url" "$code"
    head -c 400 /tmp/cdsim-smoke.$$ 2>/dev/null; echo
    fail=1
  fi
done
rm -f /tmp/cdsim-smoke.$$

# The aggregate view must report every service ok.
if curl -s --max-time 5 "http://127.0.0.1:${CDSIM_API_PORT}/v1/system/health" | grep -q '"status":"degraded"'; then
  echo "  FAIL  aggregate /v1/system/health reports degraded"; fail=1
fi

if [[ $fail -eq 0 ]]; then
  echo "All CD Sim Phase-0 services healthy. Console: http://localhost:${CDSIM_CONSOLE_PORT}"
else
  echo "Some services are unhealthy — run 'make status' and 'make logs'." >&2
fi
exit $fail
