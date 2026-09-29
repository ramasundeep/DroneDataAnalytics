# ADR 0011: OpenXR VR as a project configuration, not a fork

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-29 |
| Deciders | CDPL founding engineering |
| Supersedes | — |
| Superseded by | — |

## Context

Pilot and operator training (use case 3) must run on desktop (monitor,
joystick/RC transmitter) and in VR (head-mounted display). The maintainer
module (Fleet Focus, Phase 6) benefits from VR for walking around the airframe
twin. The founding brief says "OpenXR via UE5 — desktop first; VR as a
project configuration, not a fork", with VR delivered in Phase 5.

The risk being avoided is the common one: a separate VR project or branch
that drifts from the desktop build, doubling maintenance and making
assessment results incomparable between the two.

## Decision

**One project, one binary, two configurations.**

- The **OpenXR** plugin is enabled in `sim/CDSim.uproject` for every client
  target and **denied for the `Server` target** (`TargetDenyList`), so the
  dedicated fleet server ([0010](0010-ue5-replication-dedicated-server.md))
  never loads XR.
- XR is **inactive by default**. It switches on only when:
  - the process is started with `-vr` (the engine's own switch), or
  - the console variable `cdsim.XR.Enable` is `1` (set in
    `sim/Config/DefaultEngine.ini` `[ConsoleVariables]`, which ships `0`, or
    on the command line via `-DPCVars=cdsim.XR.Enable=1`).
- `UCDSimXRSettings` (`sim/Source/CDSim/XR/CDSimXRSettings.h`) resolves both
  switches at game start (`ApplyStartupXRMode()`, called from the game
  instance) into one place gameplay code asks: `IsXREnabled()`. It must be
  safe with no headset attached.
- **Only presentation and input differ.** Physics, clock, recording, events,
  scenarios and scoring are identical in both modes. VR-specific pieces — a VR
  pawn/camera rig, motion-controller Enhanced Input mappings, comfort options
  and a VR scalability profile — are additional classes and config selected at
  runtime, never `#if` branches in shared logic.
- Each session must record which configuration it ran in, so assessment can
  report desktop and VR sessions separately. `SessionManifest`
  (`schemas/session.proto`) has **no such field yet**; it will be added in
  Phase 5 as a new optional field, following the evolution rules in
  [0016](0016-schema-contracts-protobuf-and-json-schema.md).
- **OpenXR only** — the vendor-neutral runtime API. No vendor-specific HMD SDK
  plugins in the core project. Runtimes must work offline (no account sign-in
  or cloud service at runtime); this is a hardware-selection criterion for
  Phase 8.

## Status (Phase 0)

- Written, **UNVERIFIED BUILD** (never compiled): the `.uproject` plugin
  entry, the `cdsim.XR.Enable` cvar in `DefaultEngine.ini`, and
  `UCDSimXRSettings`.
- Not implemented: VR pawn, motion-controller input, comfort settings, VR
  scalability profile (Phase 5); VR maintainer interactions (Phase 6).
- No headset has been tested; no VR performance numbers exist.

## Consequences

### Positive

- Every desktop fix and feature is automatically in VR; one build to test,
  package and ship ([0014](0014-compose-profiles-and-air-gap-bundle.md)).
- Assessment metrics are comparable between modes because the simulation is
  literally the same code.
- Operators switch mode with a launch flag, no reinstall.

### Negative

- Desktop builds carry the OpenXR plugin even when unused (small size cost).
- Engineers must keep shared code free of mode assumptions (e.g. no
  mouse-only UI in the maintainer module); UI must work in both.
- VR frame-rate targets (typically 72–90 Hz per eye) constrain rendering
  settings for everyone unless the VR scalability profile is kept separate.

### Risks

| Risk | Mitigation |
|---|---|
| VR frame-rate targets unreachable on large terrain twins | VR scalability profile; test on the Phase 2 demo area in Phase 5 |
| Motion sickness in trainees | Comfort options (vignette, snap turn); instructor can switch a trainee to desktop |
| OpenXR runtime behaviour differs across headsets | Pick and document supported headsets in the Phase 8 hardware spec |
| Offline runtimes: some headset runtimes expect online sign-in | Hardware-selection criterion; verify air-gapped in Phase 8 |

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Separate VR project or long-lived VR branch | Drift and double maintenance; the brief forbids a fork. |
| Vendor-specific HMD SDK | Locks CDPL to one hardware vendor; OpenXR is the standard. |
| Compile-time VR flag (separate VR build) | Two binaries to test and ship; runtime switch is cheap. |
| VR later, desktop-only architecture now | Retrofitting input/camera abstractions later is costly; the switch costs little now. |

## Revisit when

- A required headset has no conformant OpenXR runtime that works offline.
- Phase 5 shows VR needs simulation-side changes (e.g. different control
  laws) — that would challenge "only presentation and input differ".
- The engine's OpenXR support changes materially in an engine upgrade.
