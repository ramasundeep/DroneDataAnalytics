# ADR 0016: Schema contracts — protobuf for streams, JSON Schema for human-edited manifests

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-29 |
| Deciders | CDPL founding engineering |
| Supersedes | — |
| Superseded by | — |

## Context

CD Sim has two very different kinds of cross-process data:

1. **Machine-to-machine streams** at high rate — events, vehicle state at
   50 Hz, control inputs, audio chunks, gRPC control — between C++ (UE5) and
   Python (services), stored and replayed years later.
2. **Human-edited manifests** — `platforms/<id>/platform.yaml`,
   `terrain/areas/<id>/area.yaml`, `scenarios/*.yaml`,
   `services/assessment/rubrics/*.yaml` — written by engineers and
   instructors, reviewed in PRs, needing clear error messages.

The founding brief asks for `schemas/` holding "protobuf/JSON schemas" and a
specific `events.proto`. `CLAUDE.md` makes "schemas first" a rule: data that
crosses a process boundary is defined in `schemas/` before code uses it.

## Decision

**Protobuf (proto3, package `cdsim.v1`) for streams and RPC**:
`schemas/common.proto` (`Header`, geometry), `events.proto`,
`telemetry.proto`, `session.proto` (manifest + session-file layout),
`control.proto` (gRPC `SimControl`, [0012](0012-rl-gym-env-grpc-pytorch-onnx.md)).
Compact, typed, generates C++ and Python. Where JSON is needed (HTTP
bodies, JSONB columns, Redis payloads) we use the **standard proto3 JSON
mapping** (camelCase field names), never an ad-hoc JSON shape. Python
services use a hand-written Pydantic mirror
(`services/common/src/cdsim_common/events.py`); a test
(`services/common/tests/test_events.py`) round-trips through the compiled
protobuf descriptor so the two cannot drift.

**JSON Schema for YAML manifests**: `schemas/json/platform.schema.json`,
`area.schema.json`, `scenario.schema.json`, `rubric.schema.json`. YAML is
readable and diffable; JSON Schema gives precise, path-qualified errors.

**A semantic validation layer on top.** Structure alone is not enough.
`cdsim_common.manifests` adds cross-field and cross-file checks, e.g.:
platform `identity.id` equals its directory name; failure-mode targets exist;
maintenance steps reference existing parts and tools; actuator output
channels are unique; scenarios reference existing areas, platforms,
rubrics and pads. `make schemas` (`scripts/validate_manifests.py`) runs both
layers over every manifest in the repository and compiles all `.proto`
files; it is part of `make lint` and CI. Services validate on load and
report invalid manifests through `/ready`.

**Evolution rules.**

| Change | Protobuf | JSON Schema manifests |
|---|---|---|
| Add a field | New field number, optional, zero default; old readers ignore it | Optional property; no version bump |
| Remove a field | Mark number and name `reserved`; never reuse | Deprecate first; remove at next major |
| Rename | Not allowed (breaks JSON mapping); add new, deprecate old | Treat as remove + add |
| Change type/meaning | Breaking: new package `cdsim.v2` + ADR | Bump `schema_version`; `cdsim_common.manifests` reads both during migration |
| Session files | Bump `SessionManifest.format_version` on layout change; replay must read all supported versions | — |

## Status (Phase 0)

- All five `.proto` files and four JSON Schemas exist; every manifest in the
  repository validates (`make schemas`); semantic checks are unit-tested
  (`services/common/tests/test_manifests.py`); the event mirror round-trip
  test passes. Verified locally.
- C++ code generation for UE5 is not wired yet (UE5 C++ currently builds JSON
  by hand in the recorder component — UNVERIFIED BUILD; Phase 1 switches to
  generated types or keeps proto3-JSON at the HTTP boundary).

## Consequences

### Positive

- One source of truth per contract, readable by both languages.
- Manifests fail fast in CI with useful messages instead of at runtime.
- Recorded sessions stay readable as the schema grows.

### Negative

- Two schema technologies to learn.
- The Pydantic mirror is duplicated effort (guarded by the round-trip test).
- Semantic rules live in Python code, not in the schema files.

### Risks

| Risk | Mitigation |
|---|---|
| Pydantic mirror drifts from `.proto` | Round-trip test fails the build |
| Someone reuses a field number | Review checklist; `reserved` entries |
| Old recordings unreadable after a change | `format_version`; golden session fixture in `tests/fixtures/golden_session/`, to be replayed in CI once replay exists (Phase 1) |

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| JSON everywhere | Verbose and untyped for 50 Hz streams; no codegen for C++. |
| Protobuf for manifests too (text format) | Unfriendly for instructors; weaker error messages. |
| Other binary formats (FlatBuffers, Cap'n Proto) | Less familiar; gRPC pairs naturally with protobuf. |
| Python-only validation (no JSON Schema) | Editors and other languages could not validate; schema not self-documenting. |

## Revisit when

- A breaking change is needed (then `cdsim.v2` and a new ADR).
- UE5 C++ codegen for protobuf proves impractical in Phase 1.
- Manifest semantic rules grow large enough to warrant a declarative rule
  format.
