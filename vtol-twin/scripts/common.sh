# Shared shell helpers. Source from scripts/*.sh; expects to be run from vtol-twin/.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi
: "${DITTO_EXTERNAL_PORT:=8080}"
: "${DITTO_USER:=ditto}"
: "${DITTO_PASSWORD:=ditto}"
: "${DITTO_DEVOPS_PASSWORD:?DITTO_DEVOPS_PASSWORD missing - copy .env.example to .env}"
: "${THING_ID:=vtol.fleet:VTOL-1}"
: "${POLICY_ID:=vtol.fleet:vtol-policy}"
: "${TAIL_NUMBER:=VTOL-1}"
DITTO_BASE="http://localhost:${DITTO_EXTERNAL_PORT}"
CURL="curl -sS --max-time 20"
log()  { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { log "ERROR: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "$1 is required"; }
need curl; need jq; need docker
