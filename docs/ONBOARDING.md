# Onboarding — your first five days on CD Sim

Welcome. This plan gets a new simulation engineer from "just cloned" to
"shipped a reviewed change" in one week. It assumes you are a competent
engineer who has never spoken to the founder — everything you need is written
down. If something is not, that is a documentation bug: fix it as part of your
day-5 change.

**Ground rules** (from `CLAUDE.md`): CD Sim is UE5-based, platform-agnostic
and offline-first. RAVEN is CDPL's only delivered programme; everything in this
repo is under build — never describe it otherwise. Never invent test results.

---

## Before day 1 — machine setup

| Need | Version | Notes |
|---|---|---|
| OS | Ubuntu 22.04/24.04, or Windows 11 + WSL2 (Ubuntu) | Services are Linux containers. UE5 work on Windows is native. |
| Docker Engine + Compose v2 | 24+ / 2.20+ | `docker compose version` must work without `sudo` |
| Python | 3.11.x | `python3.11 --version`; the Makefile uses `python3.11` (override with `make setup PYTHON=...`) |
| Node.js | 22 LTS | npm 10+ |
| Git + Git LFS | any recent | `git lfs install` once per machine |
| make, curl | — | |
| Unreal Engine | 5.4 | Only if you will work on `sim/` — see [BUILDING_UE5.md](BUILDING_UE5.md) |

Machine: 16 GB RAM minimum for the service stack (32 GB if you will also run
the UE5 editor), 30 GB free disk.

If your network uses a TLS-inspecting proxy, image builds need its CA — see
[09_DEPLOYMENT_OFFLINE.md](09_DEPLOYMENT_OFFLINE.md) §"Building behind a proxy".

---

## Day 1 — run it, then read the "why"

**Morning: get the stack healthy.**

```bash
git clone <repo-url> cd-sim && cd cd-sim
make setup          # ~3-5 min: venv, Python + Node deps, git-lfs hooks, .env
make dev            # first run ~5-10 min: builds images, starts core+terrain+lms, waits, smoke-tests
```

`make dev` ends by printing one `OK` line per service. If anything fails:
`make status`, then `make logs`, then the troubleshooting table below.

Now look around:

- Instructor console: <http://localhost:8080> — the system-status page should be all green.
  Browse *Platforms*, *Areas*, *Scenarios*.
- API: `curl localhost:8000/v1/platforms | python3 -m json.tool`
- Recorder round-trip (this is the heart of replay and assessment):

  ```bash
  curl -s -XPOST localhost:8001/v1/events -H 'content-type: application/json' -d '{"events":[
    {"header":{"simTimeUs":2000,"sessionId":"day1","actorId":"me"},"response":{"kind":"KIND_MODE_CHANGE","code":"mode.LAND"}},
    {"header":{"simTimeUs":1000,"sessionId":"day1","actorId":"me"},"stimulus":{"kind":"KIND_SYSTEM_FAILURE","code":"gps_loss"}}]}'
  curl -s localhost:8001/v1/sessions/day1/events | python3 -m json.tool   # note: ordered by simTimeUs
  ```

- Score some numbers against a rubric:

  ```bash
  curl -s -XPOST localhost:8002/v1/score -H 'content-type: application/json' \
    -d '{"rubric_id":"precision_landing_v1","values":{"landing_radial":0.3,"touchdown_vspeed":0.4}}' | python3 -m json.tool
  ```

- Run the tests: `make test`, `make lint`, `make typecheck`.

**Afternoon: read.** In this order, ~3 hours:

1. `README.md`, `CLAUDE.md`, `CONTRIBUTING.md`
2. [00_ORIGIN_PROMPT.md](00_ORIGIN_PROMPT.md) — the founding brief. Everything traces back to it.
3. [01_VISION_AND_USECASES.md](01_VISION_AND_USECASES.md)
4. [10_ROADMAP.md](10_ROADMAP.md) — what exists, what is next, what "done" means per phase.

**End of day 1 you can:** start/stop the stack, explain the five use cases and
say which phase delivers each.

---

## Day 2 — architecture and the contracts

1. [02_ARCHITECTURE.md](02_ARCHITECTURE.md) — the C4 diagrams and especially
   **"Unified time base"**. Then [ADR 0015](ADR/0015-unified-sim-time-base.md).
2. The contracts in `schemas/`: read `common.proto`, `events.proto`,
   `telemetry.proto`, `session.proto`, `control.proto`, and `schemas/README.md`.
3. The shared library `services/common/src/cdsim_common/`: `simclock.py`,
   `events.py`, `health.py`, `manifests.py`. Read their tests too.
4. Skim every ADR title in [ADR/README.md](ADR/README.md); read 0001, 0003, 0014, 0016 fully.

**Exercise:** in a Python shell (`.venv/bin/python`), create a STEPPED
`SimClock`, advance it 400 physics steps, build an `Event` stamped with it and
print `to_proto_json()`. Then run `make schemas` and find the compiled
`schemas/gen/python/events_pb2.py`.

**End of day 2 you can:** draw the container diagram from memory and explain
why nothing is ever ordered by wall-clock.

---

## Day 3 — vehicles, terrain, autopilot

1. [04_PLATFORM_PLUGIN_SPEC.md](04_PLATFORM_PLUGIN_SPEC.md) — the most important
   spec. Read it alongside `platforms/cdpl_quad_01/platform.yaml`.
2. [03_DIGITAL_TERRAIN_TWINS.md](03_DIGITAL_TERRAIN_TWINS.md) with
   `terrain/areas/hyd_demo_01/area.yaml`. Run
   `.venv/bin/cdsim-area plan terrain/areas/hyd_demo_01/area.yaml`.
3. [05_SITL_INTEGRATION.md](05_SITL_INTEGRATION.md) with
   `services/sitl/src/cdsim_sitl_bridge/protocol.py` and its tests.
4. If you will work on UE5: [BUILDING_UE5.md](BUILDING_UE5.md) and `sim/README.md`.
   Try the build — it has **never been compiled**; your build log is valuable.

**Exercise:** `make new-platform id=scratch_quad_02`, change its mass and a motor
position, break a `tool_id` on purpose and watch `make schemas` catch it. Then
delete the scaffold (`rm -rf platforms/scratch_quad_02 sim/Plugins/CDSimPlatform_scratch_quad_02`).

---

## Day 4 — assessment, training modes, autonomy, deployment

1. [06_ASSESSMENT_ENGINE.md](06_ASSESSMENT_ENGINE.md) — then work the scoring
   example by hand and check it with `POST /v1/score`.
2. [07_TRAINING_MODES.md](07_TRAINING_MODES.md)
3. [08_AUTONOMY_TRAINING.md](08_AUTONOMY_TRAINING.md) with `services/rl/src/cdsim_rl/landing.py`
4. [09_DEPLOYMENT_OFFLINE.md](09_DEPLOYMENT_OFFLINE.md)

**Exercise:** write a rubric YAML for a new metric mix and validate it with
`POST /v1/rubrics/validate` on the assessment service.

---

## Day 5 — ship something small

Pick one (or ask your lead for a starter issue):

- Fix any doc that confused you this week (there will be some).
- Add a unit test for an untested edge case in `cdsim_common.manifests`.
- Add a second placeholder landing pad to `flat_test` and a scenario that uses it.
- UE5 engineers: get `sim/` compiling on your machine and turn your fixes into a PR
  that removes the "UNVERIFIED" banner from whatever you verified.

Follow `CONTRIBUTING.md`: branch, Conventional Commits, draft PR with the
template filled in, `make lint typecheck test` green, docs/ADR/CHANGELOG
updated. Your PR description must say what you ran and what you did not.

---

## Troubleshooting `make dev`

| Symptom | Likely cause | Fix |
|---|---|---|
| `port is already allocated` | Local Postgres/Redis/other on 5432/6379/8000… | Change the port in `.env` (all host ports are configurable) |
| Image pull fails (`429`, `not found`) | Registry rate limit or image not mirrored | Retry later, use CDPL's mirror, or override (e.g. `CDSIM_MINIO_IMAGE`) — see 09 §"Image provenance" |
| `pip`/`npm` TLS errors during build | TLS-inspecting proxy | Set `CDSIM_BUILD_CA` (and possibly `CDSIM_BUILD_NETWORK=host`) in `.env` |
| `api` unhealthy, `/ready` shows `manifests` failed | An invalid YAML manifest | `make schemas` prints the exact error |
| `timescaledb` healthy but tables missing | Volume created before `db/001_init.sql` changed | `make down && docker volume rm cdsim_timescale-data && make dev` (destroys local data) |
| Console shows "API unreachable" | API container down or restarting | `make status`, `docker compose logs api` |

## Who to ask

Until the team page exists, ask the tech lead. Record every answer that
should have been in the docs *in the docs*.
