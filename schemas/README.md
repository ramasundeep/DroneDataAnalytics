# schemas/

The contracts every CD Sim component agrees on. If two components disagree,
the schema here is right and the component is wrong.

| File | Kind | What it describes |
|---|---|---|
| `common.proto` | Protobuf | `Header` (sim_time_us, session_id, actor_id, source, seq), geometry types |
| `events.proto` | Protobuf | stimulus / response / outcome / annotation events |
| `telemetry.proto` | Protobuf | vehicle state, control inputs, audio chunks, video keyframes |
| `session.proto` | Protobuf | session manifest and session-file layout |
| `control.proto` | Protobuf (gRPC) | sim control plane: clock, inject, reset, step, state stream |
| `json/platform.schema.json` | JSON Schema | `platforms/<id>/platform.yaml` |
| `json/area.schema.json` | JSON Schema | `terrain/areas/<id>/area.yaml` |
| `json/rubric.schema.json` | JSON Schema | assessment rubrics (`services/assessment/rubrics/*.yaml`) |
| `json/scenario.schema.json` | JSON Schema | scenarios (`scenarios/*.yaml`) |

Why two formats: protobuf for high-rate machine-to-machine streams (compact,
typed, generates C++ for UE5 and Python for services); JSON Schema for
human-edited YAML manifests (readable, validates with good error messages).
See `docs/ADR/0016-schema-contracts.md`.

## Commands

```bash
make schemas     # validate every manifest in the repo + compile all .proto
```

Generated code goes to `schemas/gen/` (gitignored). The Python services use
hand-written Pydantic models in `services/common/src/cdsim_common/events.py`
that mirror `events.proto` 1:1; `services/common/tests/test_events.py` checks
that the field names stay in sync with the compiled descriptor.

## Evolution rules

1. Never renumber or reuse a protobuf field number. Mark removed ones `reserved`.
2. New fields are optional with zero defaults.
3. Breaking change ⇒ new package (`cdsim.v2`) and an ADR.
4. JSON Schemas carry `schema_version`; bump it on a breaking change and
   teach `cdsim_common.manifests` to read both versions during migration.
