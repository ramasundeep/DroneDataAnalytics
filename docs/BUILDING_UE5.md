# Building the CD Sim UE5 project

> **Verification status: UNVERIFIED — this code has never been compiled.**
> Everything under `sim/`, `scripts/ue5/build.sh`, `scripts/ue5/build.ps1` and
> `.github/workflows/ue5-build.yml` was written against the Unreal Engine 5.4
> API **without an engine available**. No build, cook, PIE session or SITL
> flight has been run. The first engineer with UE 5.4 should build it, fix
> what breaks, and then **replace this banner** with what was actually
> verified (engine version and changelist, OS, compiler, date, what ran).
> Until then, do not describe any part of the UE5 client as working.
>
> Only `scripts/ue5/export_platform_json.py` has been run (it passes `ruff`
> and `mypy --strict` and exports the current manifests).

This guide takes a Windows or Linux engineer from a clean machine to the
editor, a PIE session on the flat test area, a dedicated server and headless
runs. Project layout and class map: `sim/README.md`.

---

## 1. What you need

| | Windows 10/11 x64 | Linux x86-64 (Ubuntu 22.04 recommended) |
|---|---|---|
| Engine | UE **5.4** from the Epic Games Launcher (editor + game), **or** a source build (needed for the dedicated server target) | UE **5.4** source build (Epic Games does not ship a Linux launcher build) |
| Compiler | Visual Studio 2022 17.8+ with "Game development with C++", MSVC v143, a Windows 10/11 SDK, .NET 6+ | Bundled clang toolchain (installed by `Setup.sh`) |
| Disk | ~150 GB free (engine + DDC) | ~250 GB free for a source build |
| Other | Git, **Git LFS**, Python 3.11 with PyYAML (`make setup` provides it) | same |
| GPU | DX12-capable; for VR, an OpenXR runtime + headset | Vulkan-capable; `-nullrhi` for servers |

The engine version is pinned at **5.4** (`CLAUDE.md`, docs/ADR/0002). Ask
before using any other version.

## 2. Install Unreal Engine 5.4

### Windows (launcher build)

1. Install the Epic Games Launcher, sign in, **Unreal Engine → Library → +**,
   choose **5.4.x**, install. Under *Options* keep "Editor symbols for
   debugging" if you have the disk space.
2. Set `UE_ROOT` to the install folder, e.g.
   `setx UE_ROOT "C:\Program Files\Epic Games\UE_5.4"`.
3. The launcher build **cannot build `CDSimServer`** (Server targets require a
   source build). Everything else in this guide works.

### Linux (and Windows, if you need the server target): source build

1. Get access to the engine source: link your GitHub account to your Epic
   Games account (Epic account settings → *Apps and Accounts* → GitHub) and
   accept the invitation to the `EpicGames` GitHub organisation. Access is
   personal and governed by the Unreal Engine EULA.
2. Clone the 5.4 release and build:

   ```bash
   git clone --depth 1 -b 5.4 https://github.com/EpicGames/UnrealEngine.git ~/UE_5.4
   cd ~/UE_5.4
   ./Setup.sh                  # downloads dependencies + toolchain (internet: build time only)
   ./GenerateProjectFiles.sh
   make                        # builds UnrealEditor and tools; takes hours
   export UE_ROOT=~/UE_5.4     # add to your shell profile
   ```

   Windows source build: `Setup.bat`, `GenerateProjectFiles.bat`, then build
   the `UE5` solution's *Development Editor | Win64* configuration.

Internet is only needed here, at build time. CD Sim itself never needs it at
runtime (offline-first).

## 3. Get the repository with its LFS content

```bash
git lfs install            # once per machine
git clone <repo-url> DroneDataAnalytics
cd DroneDataAnalytics
git lfs pull               # fetch binary assets (.uasset, .umap, meshes, ...)
make setup                 # Python venv with PyYAML etc.
```

If a `.uasset` opens as "unknown file" or is ~130 bytes, it is an LFS pointer:
run `git lfs pull` again.

## 4. Export platform and area manifests

UE has no YAML parser. `platforms/<id>/platform.yaml` and
`terrain/areas/<id>/area.yaml` are converted to JSON with the same tree:

```bash
.venv/bin/python scripts/ue5/export_platform_json.py
#  platform platforms/cdpl_quad_01/platform.yaml -> sim/Config/Platforms/cdpl_quad_01.json
#  area     terrain/areas/flat_test/area.yaml    -> sim/Config/Areas/flat_test.json
```

`--check` exits 1 if the JSON is missing or stale. The build scripts run the
export automatically. Re-run it after editing any manifest (and run
`make schemas` to validate the YAML first). The JSON is gitignored.

## 5. Generate project files and build the editor target

**Windows**

```powershell
# Project files (Visual Studio solution sim\CDSim.sln):
& "$env:UE_ROOT\Engine\Build\BatchFiles\Build.bat" -projectfiles -project="$PWD\sim\CDSim.uproject" -game -progress
# or right-click sim\CDSim.uproject -> "Generate Visual Studio project files"

# Editor binaries:
.\scripts\ue5\build.ps1 -Target editor
```

**Linux**

```bash
"$UE_ROOT/GenerateProjectFiles.sh" -project="$PWD/sim/CDSim.uproject" -game   # optional: IDE files
scripts/ue5/build.sh --target editor
```

Both run `CDSimEditor <Win64|Linux> Development` through UnrealBuildTool,
which compiles the `CDSim` module and the `CDSimPlatform_cdpl_quad_01` plugin.

## 6. Open the project and play on the flat test area

```bash
# Linux
"$UE_ROOT/Engine/Binaries/Linux/UnrealEditor" "$PWD/sim/CDSim.uproject" -Platform=cdpl_quad_01 -Area=flat_test -log
# Windows
& "$env:UE_ROOT\Engine\Binaries\Win64\UnrealEditor.exe" "$PWD\sim\CDSim.uproject" -Platform=cdpl_quad_01 -Area=flat_test -log
```

Press **Play (PIE)**. PIE runs in the editor process, so it reads the
**editor's** command line — that is why the options go on the editor launch
above. (For *Standalone Game* launches from the editor, put them in *Editor
Preferences → Level Editor → Play → Additional Launch Parameters* instead.)

Expected on the placeholder content (none of this has been observed yet):
the engine's empty Entry map, a flat grey ground plane, a sun, two pads
(`pad_home` at the origin, `pad_target` 50 m north) and the placeholder quad
on `pad_home`. The Output Log (`LogCDSim`) shows the session id, loaded
platform/area and "ArduPilot JSON: listening on UDP 9002".

Launch options (all optional):

| Option | Default | Meaning |
|---|---|---|
| `-Platform=<id>` | `cdpl_quad_01` | platform to spawn (`platforms/<id>`) |
| `-Area=<id>` | `flat_test` | area package (`terrain/areas/<id>`) |
| `-Session=<uuid>` | generated | session id from the API service |
| `-RecorderUrl=<url>` | `http://127.0.0.1:8001` | recorder service (local box) |
| `-SitlPort=<port>` | `9002` | ArduPilot JSON backend UDP port |
| `-NoSitl` | off | no autopilot binding (visual / replay only) |
| `-vr` | off | VR configuration (§9) |

### Flying it with ArduPilot SITL

With the editor in PIE (listening on 9002), start unmodified ArduCopter SITL
with the JSON backend pointed at the machine running UE:

```bash
sim_vehicle.py -v ArduCopter -f JSON:127.0.0.1 \
  --add-param-file=platforms/cdpl_quad_01/ardupilot.parm --console --map
```

The containerised SITL service and MAVLink routing are described in
`docs/05_SITL_INTEGRATION.md`. Phase 1 acceptance (scripted
takeoff–waypoint–land, headless, deterministic replay) is in
`docs/10_ROADMAP.md`.

## 7. Dedicated server (fleet mode)

Requires a **source-built** engine (§2).

```bash
scripts/ue5/build.sh --target server                     # Linux
.\scripts\ue5\build.ps1 -Target server                   # Windows
```

Run it headless and join from clients on the LAN:

```bash
build/ue5/LinuxServer/CDSimServer.sh -log -nullrhi -Area=flat_test -Platform=cdpl_quad_01 -port=7777
# client (packaged or editor -game):
CDSim 192.168.1.10:7777?Trainee=t01 -game -log
```

The server logs a 6-character session code; joining by code (LAN discovery)
is Phase 5 — join by address until then.

## 8. Headless and offscreen runs

| Use | Flags |
|---|---|
| Dedicated server | `-nullrhi -log` (no renderer at all) |
| RL / CI client that needs cameras | `-game -RenderOffscreen -unattended -nosound -log` — renders on the GPU with no window |
| RL / CI client without cameras | `-game -nullrhi -unattended -nosound -log` |
| Fixed frame pacing for benchmarks | add `-benchmark -fps=<n>` (sim time is still fixed-step, see below) |

Physics is always stepped at a fixed 2500 µs (400 Hz) by
`UCDSimClockSubsystem` regardless of frame rate. Lock-step RL control of the
clock over gRPC and multi-instance runs are Phase 7.

## 9. VR configuration

VR is a **configuration of the same build**, not a fork (docs/ADR/0011). The
OpenXR plugin is enabled in `CDSim.uproject` (excluded from the server target)
but XR stays inactive on the desktop. Turn it on with either:

```bash
CDSim -vr                                        # engine VR switch; CD Sim mirrors it into the cvar
CDSim -DPCVars=cdsim.XR.Enable=1                 # or the console variable directly
```

or set `cdsim.XR.Enable=1` under `[ConsoleVariables]` in a local
`Saved/Config/<Platform>/Engine.ini` for a VR seat. Requires an OpenXR runtime
(installed with the headset's PC software) and a connected headset. The VR
pawn and motion-controller input are Phase 5.

## 10. Packaging

`build.sh` / `build.ps1` produce **developer** builds under `build/ue5/`.
Installers, the Windows client package and the air-gapped `make deploy-box`
bundle are Phase 8 (`docs/10_ROADMAP.md`, docs/ADR/0014). Known gap for that
phase: the generated `sim/Config/Platforms|Areas/*.json` must be staged into
packaged builds (UAT stages `.ini` files from `Config/`, not arbitrary JSON).

## 11. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `No platform JSON in .../Config/Platforms` | Run `scripts/ue5/export_platform_json.py` (§4). |
| `unknown platform 'x'` | Wrong `-Platform=` or the YAML failed export; run the export with `--check`. |
| UBT: plugin module `CDSimPlatform_cdpl_quad_01` "should not reference" / cannot find module `CDSim` | The platform plugin depends on the project's primary module. If your UBT rejects that, move `CDSimPlatformVisualsComponent`, `CDSimPlatformSpec` and `CDSimFrames.h` into a small `CDSimCore` project plugin that both the game module and platform plugins depend on. |
| Includes like `"Vehicle/CDSimVehiclePawn.h"` not found | `CDSim.Build.cs` adds `ModuleDirectory` to `PublicIncludePaths`; check it survived edits. |
| Server target fails on OpenXR | The `.uproject` excludes OpenXR from Server via `TargetDenyList`; if UBT ignores it, disable OpenXR for server builds with `-DisablePlugins=OpenXR` in UAT. |
| `-Platform=` clashes with an engine switch | Unconfirmed risk. If the editor or cooker misreads it, rename the option in `UCDSimGameInstance::ParseCommandLine` (e.g. `-CDPlatform=`) and update this guide. |
| Black screen in PIE | The placeholder Entry map has no sky; the area loader spawns a sun only. A proper `L_FlatTest` map is Phase 1 content. |
| `cannot bind UDP port 9002` | Another UE instance or SITL-side tool holds it; use `-SitlPort=`. |
| Recorder warnings `POST /v1/events failed` | Recorder service not running (`make dev`) or wrong `-RecorderUrl=`. Events are re-queued, not dropped (up to a cap). |
| `.uasset` looks corrupt | Git LFS pointer — `git lfs pull`. |

### Known API risks to check first (written without an engine)

These are the places most likely to need a fix on the first compile:

- `UTickableWorldSubsystem` overrides (`Tick`, `GetStatId`) and `UWorldSubsystem::DoesSupportWorldType` visibility.
- `FJsonObject::TryGet*Field` overloads (5.4 moved keys to `FStringView`; `TCHAR*` literals should still bind).
- `FUdpSocketBuilder::BoundToEndpoint`, `FSocket::RecvFrom/SendTo`, `FInternetAddr::Clone`.
- `IHttpRequest::OnProcessRequestComplete().BindWeakLambda` with a mutable, move-capturing lambda.
- `TScriptInterface<ICDSimPhysicsBinding>` as a `UPROPERTY` assigned from a `UObject*`.
- `AGameModeBase::InitNewPlayer` / `SpawnDefaultPawnAtTransform_Implementation` signatures.
- `.uproject` plugin field `TargetDenyList`.
- A project plugin depending on the project's game module (see table above).

## 12. CI

`.github/workflows/ue5-build.yml` is **manual only** (`workflow_dispatch`) and
runs on a **self-hosted runner labelled `ue5`** with UE 5.4 at `$UE_ROOT`,
Git LFS and Python + PyYAML. It checks out with LFS and runs
`scripts/ue5/build.sh`. No such runner exists yet, so the workflow has never
run.
