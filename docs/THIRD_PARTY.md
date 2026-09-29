# Third-party software and data

CD Sim is proprietary (see `LICENSE`) but builds on open-source software and
open data. This list covers what Phase 0 uses or plans to use; it must be
kept current — add an entry in the same PR that adds a dependency. Exact
versions are pinned in `pyproject.toml` files, `package-lock.json`,
`docker-compose.yml` and Dockerfiles. A full SBOM is generated per air-gap
bundle from Phase 8 (docs/09_DEPLOYMENT_OFFLINE.md).

## Runtime and build software

| Component | Used for | Licence (summary) | Notes |
|---|---|---|---|
| Unreal Engine 5.4 | Visual/physics client, dedicated server | Unreal Engine EULA | Commercial terms apply to distributed builds |
| ArduPilot (unmodified) | Autopilot in SITL | GPLv3 | Run as a separate process, communicating over network protocols only; never linked into CD Sim code |
| PostgreSQL | Relational store | PostgreSQL Licence | |
| TimescaleDB | Time-series extension | Timescale Licence (TSL) / Apache-2.0 | Community edition; review TSL terms before redistribution |
| MinIO | Object storage (S3 API) | AGPLv3 | Used unmodified as a separate service over its network API; see ADR 0007 |
| Redis | Live pub/sub | See the pinned version's licence | Review licence of the pinned version before redistribution |
| Python, FastAPI, Uvicorn, Pydantic, psycopg, jsonschema, PyYAML, httpx | Services | PSF / MIT / BSD / LGPL (psycopg) | |
| protobuf, grpcio-tools | Contracts | BSD-3 / Apache-2.0 | |
| React, React Router, Vite, TypeScript | Instructor console | MIT / Apache-2.0 | |
| nginx | Console web server | BSD-2 | |
| MkDocs, Material for MkDocs | Docs site | BSD-2 / MIT | |
| OpenXR runtime (via UE5 plugin) | VR (Phase 5) | Apache-2.0 (loader) | |
| PyTorch, Gymnasium, ONNX, ONNX Runtime | Autonomy training (Phase 7) | BSD / MIT / Apache-2.0 | |
| Whisper (offline, CPU) | Optional transcription (Phase 3) | MIT | Model weights shipped in the bundle, never downloaded at runtime |
| Opus codec | Audio chunks (Phase 3) | BSD-3 | |

## Open data (build time only; attribution required where noted)

| Dataset | Used for | Terms |
|---|---|---|
| Copernicus DEM GLO-30 | Elevation | Free, attribution required ("produced using Copernicus WorldDEM-30 …") |
| SRTM 1 arc-second | Elevation fallback | Public domain |
| Sentinel-2 L2A | Imagery | Copernicus Sentinel data terms, attribution required |
| OpenStreetMap | Roads, water, buildings | ODbL 1.0 — attribution and share-alike for derived databases |

Attribution text for every dataset used by an area package is written into its
`package.json` (Phase 2) and shown in the console's area view.

Licence summaries here are for orientation only; the licence texts shipped with
each component govern. Legal review is required before any external distribution.
