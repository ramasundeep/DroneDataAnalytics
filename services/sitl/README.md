# services/sitl — ArduPilot SITL container + bridge

> **UNVERIFIED BUILD.** The Docker image below has been written but not yet
> built or run in any environment. It is outside `make dev` (opt-in `sitl`
> profile) until Phase 1 wires it to the UE5 physics binding.

## What is here

| Path | What |
|---|---|
| `docker/Dockerfile` | Builds **unmodified** ArduPilot (`Copter-4.5.7` tag, overridable with `ARDUPILOT_REF`) for the SITL board. Internet needed only at image build. |
| `docker/entrypoint.sh` | Runs `arducopter --model JSON:$SIM_HOST` with the platform's param file, home location, sim-rate (`--speedup`) and MAVLink ports. |
| `docker/healthcheck.py` | Healthy when MAVLink TCP accepts connections. |
| `src/cdsim_sitl_bridge/protocol.py` | Reference Python codec for the JSON physics wire format (servo packet in, state JSON out) + frame-loss tracker. **Tested.** |

## Ports (instance `I`, one container per vehicle)

| Port | Protocol | Use |
|---|---|---|
| `5760 + 10·I` | TCP | MAVLink SERIAL0 — console, scripted tests, RL harness |
| `GCS_TARGET` | UDP | MAVLink SERIAL1 — any MAVLink ground-control station |
| `SIM_HOST:9002` | UDP | JSON physics exchange with the UE5 client (SITL initiates) |

## Run (after Phase 1)

```bash
docker compose --profile sitl up -d --build sitl
```

Full design, timing and sim-rate scaling: `docs/05_SITL_INTEGRATION.md`.
