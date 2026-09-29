# CD Sim — build the UE 5.4 project (Windows PowerShell).
# UNVERIFIED BUILD — this script has never been run against a real engine
# install; see docs/BUILDING_UE5.md.
#
# Usage (PowerShell 5.1+ or 7):
#   $env:UE_ROOT = "C:\Program Files\Epic Games\UE_5.4"
#   .\scripts\ue5\build.ps1 [-Target editor|game|server|all] [-Config Development|Shipping] [-NoCook]
#
# Step 1 always runs scripts/ue5/export_platform_json.py (UE has no YAML parser).
#
# Headless runs:
#   Dedicated server : CDSimServer.exe -log -nullrhi -Area=flat_test -Platform=cdpl_quad_01
#   RL / CI headless : CDSim.exe -game -RenderOffscreen -unattended -nosound -log ...
#
# Note: the Server target needs a source-built engine; the launcher build of
# UE 5.4 cannot build dedicated servers. Packaging for field boxes is Phase 8.

[CmdletBinding()]
param(
    [ValidateSet("editor", "game", "server", "all")]
    [string]$Target = "all",
    [ValidateSet("DebugGame", "Development", "Shipping")]
    [string]$Config = "Development",
    [switch]$NoCook
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Project = Join-Path $RepoRoot "sim\CDSim.uproject"
$ArchiveDir = Join-Path $RepoRoot "build\ue5"

if (-not $env:UE_ROOT) {
    throw "UE_ROOT is not set. Point it at your Unreal Engine 5.4 root (the folder containing Engine\)."
}
$RunUAT = Join-Path $env:UE_ROOT "Engine\Build\BatchFiles\RunUAT.bat"
$UbtBuild = Join-Path $env:UE_ROOT "Engine\Build\BatchFiles\Build.bat"
foreach ($Tool in @($RunUAT, $UbtBuild)) {
    if (-not (Test-Path $Tool)) { throw "Not found: $Tool (is UE_ROOT correct?)" }
}

function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe failed with exit code $LASTEXITCODE" }
}

# --- 1. Export platform/area manifests to JSON ---------------------------------
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
Write-Host "==> Exporting platform/area manifests to sim\Config (PyYAML required)"
Invoke-Checked $Python @((Join-Path $RepoRoot "scripts\ue5\export_platform_json.py"))

# --- 2. Editor -----------------------------------------------------------------
if ($Target -in @("editor", "all")) {
    Write-Host "==> Building CDSimEditor (Win64 Development)"
    Invoke-Checked $UbtBuild @("CDSimEditor", "Win64", "Development", "-Project=$Project", "-WaitMutex")
}

if ($NoCook) {
    $CookFlags = @("-skipcook", "-stage", "-archive", "-archivedirectory=$ArchiveDir")
} else {
    $CookFlags = @("-cook", "-stage", "-pak", "-archive", "-archivedirectory=$ArchiveDir")
}

# --- 3. Game client ------------------------------------------------------------
if ($Target -in @("game", "all")) {
    Write-Host "==> BuildCookRun CDSim client (Win64 $Config)"
    Invoke-Checked $RunUAT (@("BuildCookRun", "-project=$Project", "-noP4", "-utf8output", "-unattended",
        "-platform=Win64", "-clientconfig=$Config", "-build") + $CookFlags)
}

# --- 4. Dedicated server ---------------------------------------------------------
if ($Target -in @("server", "all")) {
    Write-Host "==> BuildCookRun CDSimServer (Win64 $Config)"
    Invoke-Checked $RunUAT (@("BuildCookRun", "-project=$Project", "-noP4", "-utf8output", "-unattended",
        "-server", "-noclient", "-serverplatform=Win64", "-serverconfig=$Config",
        "-build") + $CookFlags)
}

Write-Host "==> Done. Archives (if any) in $ArchiveDir. UNVERIFIED BUILD: report results in docs/BUILDING_UE5.md."
