# ADR 0017: Own lightweight terrain services instead of a third-party tile server (for now)

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-29 |
| Deciders | CDPL founding engineering |
| Supersedes | — |
| Superseded by | — |

## Context

[ADR 0004](0004-offline-terrain-twins-in-docker.md) requires four offline
terrain services — tiles (raster + terrain-RGB, later vector), mesh / 3D
tiles, elevation query, weather/scenario store — serving pre-built area
packages. For each we could adopt an existing open-source server image or
write a small service of our own.

What the services must do in Phases 0–2 is modest: serve static files from a
fixed package layout (`tiles/<layer>/{z}/{x}/{y}.<fmt>`,
`mesh/tileset.json` or `mesh/heightmap.png`, `weather/default.json`), answer
point elevation queries from one COG (`elevation/dem.tif`), and report which
areas are built. What matters more for CD Sim is operational: every image
must be mirrored into the air-gap bundle ([0014](0014-compose-profiles-and-air-gap-bundle.md)),
every service must honour the `/health` + `/ready` contract that compose
health checks and the console's system page rely on
([0005](0005-python-fastapi-services.md)), and the team is small and new.

## Decision

We write the terrain services ourselves as **one small Python/FastAPI
package** (`terrain/services`, `cdsim_terrain`) with **four app factories**
in `terrain/services/src/cdsim_terrain/apps.py` — `tiles_app` (8101),
`mesh_app` (8102), `elevation_app` (8103), `weather_app` (8104) — built into
**one image** (`cdsim/terrain`) and started as four compose services in the
`terrain` profile.

- They read unpacked packages read-only from the areas directory; an
  `AreaRegistry` (`terrain/services/src/cdsim_terrain/registry.py`) loads and
  validates every `area.yaml` and reports whether `build/package.json` exists.
- Every service exposes `/v1/areas` (with a `built` flag), `/health` and
  `/ready` (fails if manifests are invalid or the areas directory is not mounted).
- Tile and mesh endpoints serve files from the package after strict
  identifier validation (`^[a-z][a-z0-9_]*$` for area/layer ids, fixed
  extension set), so no path traversal is possible.
- They share `cdsim_common` for configuration, health and manifest validation
  with every other service.
- The UE5 area loader and the console talk only to these HTTP contracts, not
  to package files directly, so the implementation behind them can be
  replaced without touching clients.

## Status (Phase 0)

- All four services run and were healthy under `make dev` (verified locally),
  list both demo areas as not built, and have unit tests.
- Elevation answers for `flat` areas; DEM-backed queries return **HTTP 501
  naming Phase 2**. Tile and mesh serving is implemented but has no built
  package to serve yet (`cdsim-area package` is Phase 2).
- No performance measurement has been made.

## Consequences

### Positive

- **Fewer images** to build, mirror, scan and ship in the air-gap bundle:
  one image for four services, built with the same `services/Dockerfile` as
  everything else.
- **One language** and toolchain (Python, ruff, mypy, pytest) for the whole
  back end.
- **Uniform health contract** and logging with no adapters.
- Behaviour is exactly what the package format needs, nothing more; no
  configuration language of another server to learn.

### Negative

- We own code that mature projects already provide (caching, on-the-fly
  tile generation, style rendering).
- Python static-file serving is slower than purpose-built servers at high
  request rates.
- Features such as vector-tile styling or dynamic reprojection would have to
  be built.

### Risks

| Risk | Mitigation |
|---|---|
| Throughput insufficient when UE5 streams a large area at high zoom | Measure in Phase 2; the HTTP contract allows swapping in a dedicated server |
| Scope creep turns these into a home-grown GIS server | Keep services to "serve the package"; anything heavier goes to the builder at build time |

## Alternatives considered

| Alternative | Why rejected (for now) |
|---|---|
| An off-the-shelf open-source tile server | Another image per capability to mirror and patch; its own config and health semantics; features we do not yet need. Strong candidate if Phase 2 shows a performance gap. |
| An off-the-shelf open-source 3D-tiles / terrain server | Same trade-off; 3D Tiles output is static files the builder already produces. |
| A generic static web server (e.g. nginx) for tiles and mesh | Good at files, but no elevation queries, no manifest validation, no `/ready` semantics; still need a Python service alongside. |
| One combined terrain service on one port | Simpler still, but the brief names four services and separate ports let them scale and fail independently. |

## Revisit when

- **Phase 2** measurements show UE5 terrain streaming of `hyd_demo_01` is
  limited by tile/mesh serving (for example, tile request latency visibly
  delays level-of-detail loading). Then evaluate an off-the-shelf
  open-source tile server behind the same URLs via a new ADR.
- Vector tiles with server-side styling or on-the-fly generation become a
  requirement.
- Area packages grow so large that serving from individual files (rather
  than an archive format) causes filesystem problems on field boxes.
