# ADR 0007: MinIO (S3 API) for recordings and area packages

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-29 |
| Deciders | CDPL founding engineering |
| Supersedes | — |
| Superseded by | — |

## Context

CD Sim produces and consumes large binary objects that do not belong in a
relational database or in git: trainee audio chunks (Opus,
[0013](0013-audio-opus-whisper.md)), video keyframes, exported session files
(`session.json`, `events.pb`, `telemetry.pb`, `controls.pb`, `audio/`, per
`schemas/session.proto`), downward-camera frames for RL, trained ONNX
policies, and built area packages (`<id>-<version>.tar.zst`,
[0004](0004-offline-terrain-twins-in-docker.md)). Storage must run offline on
one box, be scriptable, and ideally speak a widely supported API so tools and
libraries work without custom code. The founding brief fixes MinIO.

## Decision

We use **MinIO**, a self-hosted server speaking the **S3 API**, as CD Sim's
object store.

- Compose service `minio` in the `core` profile, image
  `${CDSIM_MINIO_IMAGE:-minio/minio:RELEASE.2024-09-22T00-33-43Z}` (pinned
  release tag, overridable), started with `server /data --console-address :9001`,
  `MINIO_UPDATE=off` (no update checks — offline-first), data in the
  `minio-data` volume, ports bound to `127.0.0.1` (9000 API, 9001 console).
- Buckets are created idempotently by the one-shot `minio-init` service
  (`python -m cdsim_common.bootstrap`, `services/common/src/cdsim_common/bootstrap.py`):
  - `cdsim-recordings` — session exports, audio chunks, keyframes, camera frames;
  - `cdsim-areas` — versioned area package tarballs.
- Services talk to it only through the Python `minio` client
  (`minio==7.2.9`) configured from `cdsim_common.config.Settings`
  (`CDSIM_MINIO_*`); credentials are `SecretStr` from `.env`.
- Object keys are the reference stored in the database and in protobuf
  messages (e.g. `AudioChunk` carries either inline bytes or an object key);
  the database never stores large blobs.
- Code depends on S3 semantics (buckets, keys, put/get/list), not on
  MinIO-specific admin APIs, except in bootstrap.

## Status (Phase 0)

- `minio` and `minio-init` are in the `core` profile; both buckets were
  created and the service was healthy under `make dev` — **but with a caveat**:
  the pinned public image tag **could not be pulled** in the Phase 0 build
  environment. The stack was verified using a locally built MinIO stand-in
  supplied through `CDSIM_MINIO_IMAGE`. The pinned tag itself is therefore
  **not yet verified** and must be checked on a machine with normal registry
  access.
- No service writes recordings yet (audio Phase 3, session export Phase 1).

## Consequences

### Positive

- S3 API: every language and many tools can read recordings; the replay and
  export tooling needs no custom storage layer.
- Area packages and recordings share one storage system, one backup story.
- Runs as a single container, fully offline.

### Negative

- Another stateful container to back up and size (Phase 8 field-box spec).
- Object storage has no relational integrity with the database; orphaned
  objects are possible if a session is deleted incorrectly.

### Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Pinned public image cannot be pulled**, or upstream distribution of community images (tags, registries, licence packaging) changes | Observed once in Phase 0; plausible again | CDPL **mirrors every image it uses into its own registry** and into the air-gap bundle (Phase 8, [0014](0014-compose-profiles-and-air-gap-bundle.md)); deployments never pull from public registries. `CDSIM_MINIO_IMAGE` lets an operator point at the mirror or an equivalent build without editing compose. |
| Need to replace MinIO entirely | Low–medium | Code uses the S3 API only, which keeps the door open for an S3-compatible replacement. **Changing the object store is still a tech-table change** requiring founder/tech-lead approval and a superseding ADR. |
| Orphaned objects / retention not enforced | Medium | Retention job driven by `audio_retention_days` and session deletion (Phase 3/4); lifecycle rules per bucket |
| Credentials left at dev defaults on a field box | Medium | Phase 8 bundle generates secrets at install time |

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Local filesystem volume | No API for remote clients (UE5 on another machine, console downloads); ad-hoc paths everywhere. |
| Blobs in PostgreSQL (`bytea` / large objects) | Bloats the database and its backups; poor streaming. |
| Git LFS for recordings / packages | Recordings are runtime data, not source; packages are too large ([0004](0004-offline-terrain-twins-in-docker.md)). |
| Hosted object storage | Violates offline-first. |
| Another S3-compatible server | Viable in principle (the S3 API keeps it open); MinIO was fixed in the founding brief. Would need approval. |

## Revisit when

- The pinned tag cannot be verified on a clean machine with registry access,
  or the upstream project stops publishing images CDPL can mirror under
  acceptable terms.
- Phase 8 field-box sizing shows MinIO's footprint is too large for the
  smallest box.
- A requirement for object-level encryption or WORM retention appears that
  the chosen version does not meet.
