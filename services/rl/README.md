# services/rl — autonomy training harness

Phase 0 contents (tested, simulator-free):

- `cdsim_rl.landing` — precision-landing reward shaping, touchdown
  classification, action clipping, 4-stage curriculum (static → wind →
  moving pad → moving pad + wind).
- `cdsim_rl.env` — Gymnasium-shaped `PrecisionLandingEnv` + `EnvConfig`.
  `reset`/`step` raise `NotImplementedError` until Phase 7 connects it to the
  UE5 `SimControl` gRPC service (`schemas/control.proto`).

Phase 7 adds: gRPC client, headless multi-instance UE5 launcher, PyTorch
training script, ONNX export and an onboard-inference note. Design:
`docs/08_AUTONOMY_TRAINING.md`.
