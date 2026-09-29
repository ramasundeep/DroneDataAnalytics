# Golden session fixture

**Empty on purpose in Phase 0.** No simulator exists yet to record a real
session, and a fabricated "golden" session would defeat its purpose.

Plan:

- **Phase 1** records the first real session: `scenarios/sitl_core_loop.yaml`
  flown headless by ArduPilot SITL in UE5. Its session directory
  (`session.json`, `events.pb`, `telemetry.pb`, `controls.pb`; layout in
  `schemas/session.proto`) is committed here via Git LFS together with the
  build ids that produced it. A test replays it and checks deterministic
  re-emission.
- **Phase 3** adds its expected assessment output (`expected_score.json`); the
  golden test asserts the engine scores it byte-identically on every run, and a
  synthetic-stimulus test checks reaction time to within 20 ms.
