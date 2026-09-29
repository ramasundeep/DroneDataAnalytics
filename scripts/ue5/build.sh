#!/usr/bin/env bash
# CD Sim — build the UE 5.4 project (Linux / macOS shell).
# UNVERIFIED BUILD — this script has never been run against a real engine
# install; see docs/BUILDING_UE5.md.
#
# Usage:
#   UE_ROOT=/opt/UnrealEngine scripts/ue5/build.sh [--target editor|game|server|all] [--config Development|Shipping] [--no-cook]
#
#   editor  build CDSimEditor (to open the project / PIE)
#   game    BuildCookRun the CDSim client (desktop; VR is the same build, see -vr)
#   server  BuildCookRun the CDSimServer dedicated server (fleet mode)
#   all     editor + game + server (default)
#
# Step 1 always runs scripts/ue5/export_platform_json.py, because UE has no
# YAML parser: platforms/*/platform.yaml and terrain/areas/*/area.yaml become
# sim/Config/Platforms/*.json and sim/Config/Areas/*.json.
#
# Running the results headless (documented here and in docs/BUILDING_UE5.md):
#   Dedicated server : CDSimServer -log -nullrhi -Area=flat_test -Platform=cdpl_quad_01
#                      (the Server target has no renderer anyway; -nullrhi is belt and braces)
#   RL / CI headless : CDSim -game -RenderOffscreen -unattended -nosound -log ...
#                      (-RenderOffscreen keeps the GPU so cameras still render; use
#                       -nullrhi only if no camera sensor is needed)
#
# Packaging for field boxes / air-gap bundles is Phase 8 (docs/10_ROADMAP.md);
# the archive written here is a developer build only.

# UAT picks the Game target (CDSim.Target.cs) and the Server target
# (CDSimServer.Target.cs) automatically because there is exactly one of each.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT="${REPO_ROOT}/sim/CDSim.uproject"
ARCHIVE_DIR="${REPO_ROOT}/build/ue5"

TARGET="all"
CONFIG="Development"
COOK=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    --config) CONFIG="$2"; shift 2 ;;
    --no-cook) COOK=0; shift ;;
    -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$TARGET" in editor|game|server|all) ;; *) echo "bad --target: $TARGET" >&2; exit 2 ;; esac

if [[ -z "${UE_ROOT:-}" ]]; then
  echo "UE_ROOT is not set. Point it at your Unreal Engine 5.4 root (the folder containing Engine/)." >&2
  exit 2
fi

case "$(uname -s)" in
  Linux) HOST_PLATFORM="Linux" ;;
  Darwin) HOST_PLATFORM="Mac" ;;
  *) echo "unsupported host $(uname -s); use scripts/ue5/build.ps1 on Windows" >&2; exit 2 ;;
esac

RUN_UAT="${UE_ROOT}/Engine/Build/BatchFiles/RunUAT.sh"
UBT_BUILD="${UE_ROOT}/Engine/Build/BatchFiles/${HOST_PLATFORM}/Build.sh"
for tool in "$RUN_UAT" "$UBT_BUILD"; do
  [[ -x "$tool" ]] || { echo "not found or not executable: $tool (is UE_ROOT correct?)" >&2; exit 2; }
done

# --- 1. Export platform/area manifests to JSON --------------------------------
PYTHON="${REPO_ROOT}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"
echo "==> Exporting platform/area manifests to sim/Config (PyYAML required)"
"$PYTHON" "${REPO_ROOT}/scripts/ue5/export_platform_json.py"

# --- 2. Editor ------------------------------------------------------------------
if [[ "$TARGET" == "editor" || "$TARGET" == "all" ]]; then
  echo "==> Building CDSimEditor (${HOST_PLATFORM} Development)"
  "$UBT_BUILD" CDSimEditor "$HOST_PLATFORM" Development -Project="$PROJECT" -WaitMutex
fi

COOK_FLAGS=(-cook -stage -pak -archive -archivedirectory="$ARCHIVE_DIR")
[[ "$COOK" -eq 1 ]] || COOK_FLAGS=(-skipcook -stage -archive -archivedirectory="$ARCHIVE_DIR")

# --- 3. Game client ---------------------------------------------------------------
if [[ "$TARGET" == "game" || "$TARGET" == "all" ]]; then
  echo "==> BuildCookRun CDSim client (${HOST_PLATFORM} ${CONFIG})"
  "$RUN_UAT" BuildCookRun -project="$PROJECT" -noP4 -utf8output -unattended \
    -platform="$HOST_PLATFORM" -clientconfig="$CONFIG" \
    -build "${COOK_FLAGS[@]}"
fi

# --- 4. Dedicated server --------------------------------------------------------------
if [[ "$TARGET" == "server" || "$TARGET" == "all" ]]; then
  echo "==> BuildCookRun CDSimServer (${HOST_PLATFORM} ${CONFIG})"
  "$RUN_UAT" BuildCookRun -project="$PROJECT" -noP4 -utf8output -unattended \
    -server -noclient -serverplatform="$HOST_PLATFORM" -serverconfig="$CONFIG" \
    -build "${COOK_FLAGS[@]}"
fi

echo "==> Done. Archives (if any) in ${ARCHIVE_DIR}. UNVERIFIED BUILD: report results in docs/BUILDING_UE5.md."
