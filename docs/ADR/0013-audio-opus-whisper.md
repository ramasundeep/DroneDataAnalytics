# ADR 0013: Trainee audio as sim-time-stamped Opus chunks; optional offline Whisper

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-29 |
| Deciders | CDPL founding engineering |
| Supersedes | — |
| Superseded by | — |

## Context

The assessment engine measures **communication timeliness**: how quickly a
trainee speaks after a stimulus (audio energy onset), optionally what they
said (transcription). The founding brief fixes: client-side capture in UE5,
streamed as **Opus** chunks with **sim-time stamps** into **MinIO**; optional
**offline transcription (Whisper, CPU)**; a **consent prompt** and a
**per-session retention setting**. Voice recordings of service personnel are
personal data; they must be handled with explicit consent, minimal retention
and no transmission off the box.

## Decision

**Capture and encoding.** `UCDSimAudioCaptureComponent`
(`sim/Source/CDSim/Recording/CDSimAudioCaptureComponent.h`) captures the
trainee microphone in the UE5 client at 48 kHz mono, encodes **20 ms Opus
frames**, and batches them into roughly **1 s `AudioChunk`** messages
(`schemas/telemetry.proto`).

**Stamping.** Each chunk's `Header.sim_time_us` is the sim time of the
**first sample** in the chunk; `duration_us` gives its length. Any sample's
sim time is therefore `sim_time_us + index / sample_rate`. Chunks also carry
`rms_dbfs` so voice-onset detection can run cheaply without decoding. Audio
is thus on the same clock as the stimulus it responds to
([0015](0015-unified-sim-time-base.md)).

**Storage.** Chunks go to the recorder and are stored in MinIO bucket
`cdsim-recordings` under `recordings/<session>/audio/<trainee>/<seq>.opus`;
the `AudioChunk` message carries either inline bytes (small, live path) or
that `object_key`. Session exports place them in `audio/<trainee>/` with an
index (`schemas/session.proto`).

**Consent — no consent, no capture.**

- `Participant.audio_consent` in `SessionManifest` records an explicit
  decision per trainee per session, captured by the API/console **before**
  recording starts.
- The UE5 component refuses to start without consent (`SetConsent(true)`
  must have been called) and **stops immediately** if consent is revoked.
- The recorder must reject audio for participants without consent (Phase 3).
- Without audio, the communication-timeliness metric is reported as "not
  available", not as a fail.

**Retention.** `SessionManifest.audio_retention_days` (default 14;
`0` = delete at session close; `-1` = keep) is set per session. A retention
job deletes expired audio objects and their index entries; transcripts, if
any, follow the same retention. Scores and event metadata remain.

**Transcription — optional, offline, CPU.** If enabled for a session, a
worker runs **Whisper** on CPU from a model file shipped in the air-gap bundle
([0014](0014-compose-profiles-and-air-gap-bundle.md)). Output becomes
`voice_command` response events / annotations stamped in sim time. Nothing is
ever sent to an online service. Metrics that need only onset use `rms_dbfs`
and never require transcription.

## Status (Phase 0)

- Schema: `AudioChunk`, `Participant.audio_consent`,
  `audio_retention_days` exist and are compiled/tested as part of the schema tests.
- `UCDSimAudioCaptureComponent` is a skeleton, **UNVERIFIED BUILD**: consent
  gating logic is written; `StartCapture()` logs and returns false because
  capture/encoding is Phase 3.
- Not implemented: recorder audio ingest, consent capture UI, retention job,
  Whisper worker, communication-timeliness metric (all Phase 3/4).

## Consequences

### Positive

- Audio aligns with stimuli to within one chunk's first-sample stamp plus
  per-sample offset — well inside the Phase 3 20 ms reaction-time target in
  principle (to be verified).
- Opus gives good speech quality at low bitrates; chunks are small.
- Consent and retention are data in the manifest, auditable per session.

### Negative

- Capture latency (device buffer) offsets the first-sample stamp; it must be
  measured and compensated.
- Whisper on CPU is slow; transcription is post-session, not live.
- Retention deletion must reach every copy (MinIO, exports, bundles).

### Risks

| Risk | Mitigation |
|---|---|
| Recording without valid consent | Double gate: UE5 component and recorder; consent recorded in manifest |
| Audio retained longer than allowed | Retention job + audit log; default 14 days |
| Transcripts expose sensitive content | Same retention and access rules as audio; transcription off by default |
| Device latency biases timeliness metric | Calibrate per hardware in Phase 3; record the offset in the manifest |

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Uncompressed WAV | 10× larger; wasteful for hours of sessions. |
| Stamp audio with wall-clock | Cannot be aligned with sim-time stimuli, especially at non-1× rates. |
| Online speech-to-text | Violates offline-first and privacy. |
| Mandatory transcription | Slow on CPU and more sensitive data; onset energy is enough for v1. |
| Capture on a separate recording device | Separate clock; alignment and consent become manual. |

## Revisit when

- Phase 3 measurements show capture latency variance too large for the
  timeliness metric.
- Policy on voice data retention or consent changes (update defaults).
- CPU transcription is too slow for the session volume on a field box.
