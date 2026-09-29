#!/bin/sh
# Launch unmodified ArduCopter SITL against the CD Sim JSON physics backend.
#
# Environment:
#   SIM_HOST        host running UE5 physics (receives servo packets on :9002)
#   SIM_RATE        --speedup factor, 0.1 .. 10 (docs/05_SITL_INTEGRATION.md)
#   INSTANCE        -I instance number (one container per vehicle; ports offset by 10*I)
#   HOME            lat,lon,alt_msl,heading of the spawn point
#   PARAM_FILE      platform ArduPilot params (mounted from platforms/<id>/)
#   GCS_TARGET      host:port for SERIAL1 UDP MAVLink to a GCS
set -eu

SIM_HOST="${SIM_HOST:-host.docker.internal}"
SIM_RATE="${SIM_RATE:-1}"
INSTANCE="${INSTANCE:-0}"
HOME_LOC="${HOME_LOC:-17.4000,78.5000,500,0}"
PARAM_FILE="${PARAM_FILE:-/platform/ardupilot.parm}"
GCS_TARGET="${GCS_TARGET:-127.0.0.1:14550}"

exec arducopter \
    --model "JSON:${SIM_HOST}" \
    --speedup "${SIM_RATE}" \
    -I "${INSTANCE}" \
    --home "${HOME_LOC}" \
    --defaults "${PARAM_FILE}" \
    --serial0 tcp:0 \
    --serial1 "udpclient:${GCS_TARGET}"
