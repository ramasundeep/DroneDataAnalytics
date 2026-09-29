# ADR 0002: Unreal Engine 5.4, C++ first, Git LFS for binaries

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-29 |
| Deciders | CDPL founding engineering |
| Supersedes | — |
| Superseded by | — |

## Context

CD Sim needs photoreal large-terrain rendering, desktop and VR clients,
networked multiplayer with a dedicated server, headless rendering for
autonomy training, and a vehicle model that is **deterministic** so sessions
replay exactly and golden sessions score identically
([0015](0015-unified-sim-time-base.md)). The founding brief fixes
"Unreal Engine 5.4+ (C++ project, Blueprints only for glue)" and asks us to
pin the version. At plan approval the founder confirmed **5.4 as written**.

UE projects contain large binary assets (`.uasset`, `.umap`) that git handles
badly, and real CDPL CAD (STEP/FBX) will arrive later.

## Decision

1. **Engine pinned to UE 5.4.** `sim/CDSim.uproject` sets
   `"EngineAssociation": "5.4"`. Build scripts and `docs/BUILDING_UE5.md`
   target 5.4. Moving to another engine version is a tech-table change that
   needs founder approval and a superseding ADR.
2. **C++ first.** All simulation, gameplay and recording logic is C++ in
   `sim/Source/CDSim/` (modules by folder: `Core`, `World`, `Vehicle`,
   `Sensors`, `Recording`, `Net`, `XR`) and per-platform plugins in
   `sim/Plugins/CDSimPlatform_<id>/`. Blueprints may only wire assets
   (meshes, materials, input mappings) to C++ classes. Reason: C++ diffs,
   reviews and merges; Blueprint graphs do not, and the team is new.
3. **Deterministic vehicle physics in plain C++, not Chaos.** The flight
   vehicle is integrated by `FCDSimRigidBody`
   (`sim/Source/CDSim/Vehicle/CDSimRigidBody.h/.cpp`): 6-DOF, NED/FRD, SI,
   double precision, semi-implicit Euler at a fixed **2500 µs step (400 Hz)**
   driven by `UCDSimClockSubsystem` (`sim/Source/CDSim/Core/CDSimClockSubsystem.h`)
   — never by UE's variable frame `DeltaTime`. It has no `UObject` or engine
   state, so it is unit-testable. Chaos remains in use for visuals-only
   effects (debris, cloth) and scene queries. Frame conversion NED ↔ UE
   (cm, left-handed, Z up) happens only when placing actors
   (`sim/Source/CDSim/Core/CDSimFrames.h`).
4. **Git LFS for binaries.** `.gitattributes` routes Unreal
   (`*.uasset`, `*.umap`, `*.ubulk`), CAD/mesh (`*.fbx`, `*.step`, `*.stp`,
   `*.obj`, `*.glb`, `*.gltf`, `*.b3dm`), raster (`*.png`, `*.jpg`, `*.tif`,
   `*.exr`, `*.mbtiles`, `*.pmtiles`, `*.laz`), audio/video (`*.wav`,
   `*.opus`, `*.mp4`) and ML (`*.onnx`, `*.pt`) through LFS. SVG logos stay
   text. Built area packages and recordings never enter git; they go to MinIO
   ([0007](0007-minio-object-storage.md)). `sim/Content/` holds only minimal
   placeholder assets.

## Status (Phase 0)

- `sim/` contains the `.uproject`, targets (`CDSim`, `CDSimEditor`,
  `CDSimServer`), config and C++ source for clock, rigid body, physics
  binding, sensors, recording, fleet state and area loading. **UNVERIFIED
  BUILD: none of it has been compiled.** No UE5 toolchain was available in
  the Phase 0 environment; the engine build is a manual CI job.
- `.gitattributes` LFS patterns are in place; no large assets are committed yet.
- The determinism of `FCDSimRigidBody` is a design property, not a measured
  one: the Phase 1 acceptance test (headless replay reproduces a session) is
  where it is first checked.

## Consequences

### Positive

- Determinism is under our control; replay, golden scoring and RL lock-step
  all depend on it.
- The vehicle model is shared semantics with the Python sim clock
  (`services/common/src/cdsim_common/simclock.py`) and can be unit-tested
  without an engine.
- Reviews are text diffs; Blueprint surface is small.

### Negative

- We maintain our own dynamics (contact, drag, ground effect) instead of
  using the engine's; ground contact is simple (flat ground height from the
  area loader) until Phase 2 terrain.
- UE5 builds need a large workstation and the engine source or launcher
  install; CI cannot build it on standard runners.
- Contributors must install `git-lfs` or they get pointer files.

### Risks

| Risk | Mitigation |
|---|---|
| 5.4 becomes hard to obtain or unsupported on new OS/GPU drivers | Archive the engine install in CDPL storage; revisit trigger below |
| Semi-implicit Euler too coarse for stiff dynamics (e.g. fixed-wing, rotor wake) | Integrator is isolated in one class; can move to RK4 at the same step |
| Floating-point differences across compilers/CPUs break cross-machine replay | Replay compares on the same build; cross-machine determinism is a goal, verified in Phase 1 |
| LFS bandwidth / storage limits | Mirror LFS to CDPL-owned storage; keep terrain out of git |

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Latest UE 5.x | Founder pinned 5.4; newer versions change APIs mid-project. |
| Blueprint-heavy development | Not diffable or reviewable; brief says Blueprints only for glue. |
| Chaos rigid body for the flight vehicle | Variable/async stepping; not guaranteed deterministic run-to-run or machine-to-machine. |
| External flight-dynamics process | Extra process and network hop per 400 Hz tick; UE5 must own physics per [0003](0003-ardupilot-sitl-json-physics.md). |
| Another game engine | Brief fixes UE5; large-terrain, VR and replication support weighed heavily. |
| Plain git for assets | Repository bloat, slow clones. |

## Upgrade path

A move to a newer 5.x is done on a branch: bump `EngineAssociation`, rebuild,
run the Phase 1 replay test and the golden-session scoring test, and compare
recorded trajectories bit-for-bit against the previous engine. A supersede ADR
records the result.

## Revisit when

- The Phase 1 deterministic-replay acceptance test fails because of engine
  behaviour we cannot control.
- A required capability (OpenXR runtime, platform SDK, GPU driver) is only
  supported on a newer engine version.
- A platform class needs dynamics our integrator cannot represent credibly
  (e.g. rotorcraft blade flapping) — consider a pluggable dynamics model.
