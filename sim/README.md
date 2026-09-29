# sim/ — CD Sim Unreal Engine 5.4 project

> **UNVERIFIED BUILD.** Nothing under `sim/` has ever been compiled or run.
> It was written against the UE 5.4 API without an engine available. The first
> engineer with UE 5.4 installed should build it, fix what breaks, and then
> update the "Verification status" section of
> [`docs/BUILDING_UE5.md`](../docs/BUILDING_UE5.md). Every source file carries
> the same banner in its header.

This is the visual / physics client of CD Sim: the one UE5 project that serves
all five use cases (SITL testing, autonomy training, pilot/operator training,
mission rehearsal, maintainer training). Vehicles and areas are **data**; the
core never changes to add one (see `CLAUDE.md`).

How to build and run: [`docs/BUILDING_UE5.md`](../docs/BUILDING_UE5.md).

## Layout

```
sim/
├── CDSim.uproject                  project: module CDSim + plugins OpenXR, EnhancedInput, CDSimPlatform_cdpl_quad_01
├── Config/
│   ├── DefaultEngine.ini           maps, game mode/instance classes, [ConsoleVariables] cdsim.XR.Enable=0
│   ├── DefaultGame.ini             project name "CD Sim", company, version, bStartInVR=False
│   ├── DefaultInput.ini            Enhanced Input as the default input classes
│   ├── Platforms/<id>.json         GENERATED from platforms/<id>/platform.yaml (gitignored)
│   └── Areas/<id>.json             GENERATED from terrain/areas/<id>/area.yaml (gitignored)
├── Content/                        /Game content — Git LFS only; empty for now
├── Plugins/
│   └── CDSimPlatform_cdpl_quad_01/ platform plugin: placeholder visuals + part anchors
└── Source/
    ├── CDSim.Target.cs             Game target (desktop / VR configuration / headless RL)
    ├── CDSimEditor.Target.cs       Editor target
    ├── CDSimServer.Target.cs       Dedicated server target (fleet mode)
    └── CDSim/                      the core game module (flat per-folder layout, no Public/Private split)
```

### Source/CDSim — what each class does

| Folder | Class | Role |
|---|---|---|
| (root) | `CDSim.h/.cpp` | Primary game module, `LogCDSim` log category |
| Core | `UCDSimClockSubsystem` | **Authoritative sim clock.** `int64 SimTimeUs` advanced only in fixed 2500 µs (400 Hz) steps; rate 0.1–10×; pause/resume; Realtime or Stepped mode; `OnPhysicsStep` delegate. Mirrors `services/common/src/cdsim_common/simclock.py`. |
| Core | `CDSimTypes.h` | `FCDSimHeader` (mirrors `cdsim.v1.Header`), `ECDSimSource`, stimulus/response kinds, proto-JSON helpers |
| Core | `CDSimFrames.h` | NED/FRD ↔ UE (cm, left-handed X fwd, Y right, Z up) conversions — read before touching maths |
| Core | `CDSimJson.h` | Forgiving JSON readers for the exported manifests |
| Core | `ACDSimGameMode` | Loads the area, spawns one vehicle per seat on the home pad, starts the clock |
| Core | `UCDSimGameInstance` | Parses `-Platform= -Area= -Session= -RecorderUrl= -SitlPort= -NoSitl` |
| World | `UCDSimAreaLoader` | Reads `Config/Areas/<id>.json`, lat/lon → local NED (flat-earth, < 20 km), spawns ground, sun and pads |
| World | `CDSimGeo.h` | The documented equirectangular approximation |
| World | `ACDSimLandingPadActor` | One `landing_pads[]` entry (placeholder slab) |
| Vehicle | `UCDSimPlatformRegistry` | Loads every `Config/Platforms/*.json` into `FCDSimPlatformSpec` |
| Vehicle | `FCDSimPlatformSpec` (+ actuator/sensor/failure/part specs) | In-engine view of `platform.yaml` |
| Vehicle | `ACDSimVehiclePawn` | Generic vehicle configured from the spec; owns physics, sensors, SITL binding, failures |
| Vehicle | `FCDSimRigidBody`, `FCDSimMultirotorModel` | Deterministic 6-DOF rigid body + motor model in plain C++ at 400 Hz (**not Chaos** — see header for why) |
| Vehicle | `ICDSimPhysicsBinding` | Autopilot SITL interface (ArduPilot now, PX4 later) |
| Vehicle | `UArduPilotJsonBinding` | ArduPilot JSON physics backend over UDP 9002 (16/32-channel servo packets in, JSON state out) |
| Vehicle | `UCDSimPlatformVisualsComponent`, `FCDSimPlatformVisualsRegistry` | Generic placeholder visuals + registry that platform plugins register into |
| Sensors | `UCDSimSensorComponent` → `UCDSimImuComponent`, `UCDSimGpsComponent`, `UCDSimDownCameraComponent` | Rate-gated, deterministic-noise sensors from `sensors[]` |
| Recording | `UCDSimRecorderComponent` | Stamps events with sim time, batches, `POST {RecorderUrl}/v1/events` in proto-JSON (same aliases as `cdsim_common.events`) |
| Recording | `UCDSimAudioCaptureComponent` | Consent-gated voice capture skeleton (Opus: Phase 3) |
| Net | `ACDSimFleetGameState`, `ACDSimPlayerState` | Replicated session id/code/area/sim time; trainee + vehicle id per seat |
| Net | `UCDSimSessionCode` | 6-character LAN join codes (discovery: Phase 5) |
| XR | `UCDSimXRSettings` | `cdsim.XR.Enable` / `-vr` → HMD on or off |

Unimplemented behaviour is marked `TODO(Phase N)` pointing at
`docs/10_ROADMAP.md`, and logs a warning at runtime rather than failing silently.

## Platform and area JSON export (UE has no YAML parser)

`platforms/<id>/platform.yaml` and `terrain/areas/<id>/area.yaml` are the
source of truth (validated by `make schemas`). UE cannot read YAML, so a build
step converts them to JSON with the **same tree**:

```bash
python scripts/ue5/export_platform_json.py
#  platforms/cdpl_quad_01/platform.yaml   -> sim/Config/Platforms/cdpl_quad_01.json
#  terrain/areas/flat_test/area.yaml      -> sim/Config/Areas/flat_test.json
#  (directories starting with "_" such as platforms/_template are skipped)
```

`scripts/ue5/build.sh` / `build.ps1` run it automatically; run it by hand
before opening the editor and after editing any manifest. The output is
gitignored by `sim/.gitignore` — never edit or commit it.

## VR is a configuration, not a fork

The `.uproject` enables the **OpenXR** plugin for every client build (it is
excluded from the dedicated server target). JSON cannot carry comments, so the
explanation lives here: **OpenXR being enabled does not make CD Sim a VR app.**
The same binary starts on the desktop with XR inactive unless:

- it is launched with `-vr`, or
- the console variable `cdsim.XR.Enable` is `1` (e.g. `-DPCVars=cdsim.XR.Enable=1`,
  `-ini:Engine:[ConsoleVariables]:cdsim.XR.Enable=1`, or the in-game console).

`UCDSimXRSettings::ApplyStartupXRMode()` resolves this at game start and turns
the HMD on or off. `DefaultEngine.ini` ships with `cdsim.XR.Enable=0` and
`DefaultGame.ini` with `bStartInVR=False`. See docs/ADR/0011.

## Frames and units (summary)

Physics is SI in aerospace frames — local **NED** about the area origin, body
**FRD** — exactly as ArduPilot and `platform.yaml` use them. UE is centimetres,
left-handed X fwd / Y right / Z up, with UE +X = North, +Y = East and the world
origin at the area origin: `UE_cm = 100 · (N, E, −D)`. Quaternions map as
`(w, x, y, z) → (w, −x, −y, z)`. Full derivation in `Source/CDSim/Core/CDSimFrames.h`.
