# ADR 0012: Gym-style RL environment over gRPC; PyTorch; ONNX export

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-29 |
| Deciders | CDPL founding engineering |
| Supersedes | — |
| Superseded by | — |

## Context

Autonomy training (use case 2, Phase 7) must teach a drone a precise action —
first **precision landing** on a marked, possibly moving pad — and export the
trained policy to the real vehicle. The founding brief fixes: a **Python
gym-style environment** wrapping the UE5 sim via **gRPC or ZeroMQ**,
**PyTorch**, headless UE5 rendering at N× real time, and **ONNX** export.
Observation: downward camera + IMU + estimated pad pose; action: velocity
setpoints via MAVLink guided mode; shaped reward on radial error, descent
rate, attitude and time; curriculum static pad → wind → moving pad.

RL needs **lock-step** control: the learner must see exactly the state that
resulted from its action, and runs must be reproducible from a seed
([0015](0015-unified-sim-time-base.md)). The brief left the transport open.

## Decision

**Transport: gRPC** (not ZeroMQ), service `SimControl` in
`schemas/control.proto` (package `cdsim.v1`):

| RPC | Purpose |
|---|---|
| `SetClock(ClockCommand) → ClockStatus` | start/pause/resume/stop, sim rate 0.1–10 |
| `Inject(Event) → Event` | stimulus injection, server stamps `sim_time_us` |
| `Reset(ResetRequest) → ResetResponse` | new episode: scenario, `random_seed`, curriculum `params` |
| `Step(StepRequest) → StepResponse` | **lock-step**: apply ENU velocity setpoint + yaw rate, advance `ticks` physics steps, return state, events, camera frame key |
| `StreamState(StreamRequest) → stream VehicleState` | live monitoring |

Why gRPC: the contract is **typed and versioned in one `.proto`**, and code
is generated for both sides — C++ for the UE5 server, Python for the env —
so neither side hand-parses messages. It also reuses the message types
(`Event`, `VehicleState`, `Header`) that the recorder already stores. The
same service serves the scenario runner and the API's session control, so it
is not RL-only plumbing.

**Stepping.** `Step` runs the UE5 clock in **Stepped** mode: the server
advances exactly `ticks × 2500 µs` and replies. The env
(`services/rl/src/cdsim_rl/env.py`, `PrecisionLandingEnv`) controls at
**20 Hz** with **20 physics ticks per step** (enforced: ticks × control rate
= 400 Hz). The velocity setpoint in `StepRequest` is forwarded by the
sim side to the vehicle's autopilot as a **MAVLink guided-mode setpoint**
(SITL, [0003](0003-ardupilot-sitl-json-physics.md)), exactly as a companion
computer would on the real vehicle — so the policy learns against the real
autopilot's control loops. With no wall-clock pacing, headless runs go as fast as the host
allows; the rate cap of 10× applies only to real-time mode.

**Env contract.** Gymnasium-compatible signatures
(`reset(seed) → (obs, info)`, `step(action) → (obs, reward, terminated,
truncated, info)`), without importing Gymnasium in Phase 0. Task definition
in `services/rl/src/cdsim_rl/landing.py`: action = ENU velocity + yaw rate,
clipped to (2, 2, 1.5 m/s, 0.5 rad/s); reward = −w·radial error −w·excess
descent (> 0.7 m/s) −w·tilt −w·time, terminal +100 success, −100 crash or
hard landing, −25 off pad; curriculum `static_calm` → `static_wind` (4 m/s,
gust 2) → `moving_linear` (1 m/s pad) → `moving_circular_wind` (1.5 m/s, wind 5).

**Learning and export.** Training uses **PyTorch** in `rl` profile workers.
Policies are exported to **ONNX** (stored in MinIO, LFS if committed) so they
can run onboard through an ONNX runtime independent of PyTorch. Onboard
deployment is documented in `docs/08_AUTONOMY_TRAINING.md`; it is a design,
not a delivered capability.

## Status (Phase 0)

- `schemas/control.proto` exists and compiles with `make schemas` (Python
  codegen). C++ server implementation: not written (Phase 1 session control,
  Phase 7 stepping).
- `cdsim_rl.landing` (reward, action clipping, curriculum) is unit-tested.
  `PrecisionLandingEnv` constructs and validates config; `reset`/`step` raise
  `NotImplementedError` naming Phase 7.
- The `rl` compose profile is a placeholder whose entry point exits with a
  "not implemented" message. No policy has been trained or exported.

## Consequences

### Positive

- One typed contract for control across RL, scenario runner and console.
- Lock-step makes episodes reproducible from `(scenario, seed, actions)`.
- ONNX decouples onboard inference from the training framework.

### Negative

- gRPC adds a codegen step and a C++ dependency to the UE5 build.
- Per-step RPC overhead at 20 Hz × many parallel instances; camera frames go
  by object key, not inline, to keep messages small.

### Risks

| Risk | Mitigation |
|---|---|
| gRPC C++ integration with UE5 build is awkward | Isolate in one module; fall back to a thin C shim if needed (Phase 1 spike) |
| Sim-to-real gap for the learned policy | Sensor noise from `platform.yaml`, domain randomisation, SITL validation before any flight |
| Camera observation throughput limits headless speed | Down-sampled frames; measure in Phase 7 |

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| ZeroMQ (allowed by the brief) | Transport only; we would hand-define framing and schemas and hand-write parsers on both sides. gRPC gives the contract and codegen. |
| Driving UE5 via MAVLink only | MAVLink controls the autopilot, not the sim clock, resets or scenario injects. |
| Real-time (non-lock-step) RL | Non-reproducible; wasted wall time. |
| Framework-native model export only | Onboard would need the training framework; ONNX is portable. |

## Revisit when

- Phase 7 profiling shows RPC overhead, not simulation, limits steps/second.
- The onboard compute target cannot run ONNX models (then add a converter
  step, keep ONNX as the interchange format).
- A second learning task needs observations the `Step` response cannot carry.
