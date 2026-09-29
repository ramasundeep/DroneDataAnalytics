# Glossary

| Term | Meaning in CD Sim |
|---|---|
| **ADR** | Architecture Decision Record — `docs/ADR/NNNN-*.md`, one per non-trivial decision. |
| **Anchor** | A 3D point on a platform (UE mesh socket or body-frame offset) used by the maintainer module to highlight a part or step. |
| **Area / area package** | A digital terrain twin of an area of operations: manifest `terrain/areas/<id>/area.yaml` plus a built, versioned tarball (tiles, elevation, mesh, weather). |
| **Assessment engine** | The services and rules that turn recorded sessions into metrics and rubric scores (`services/assessment`). |
| **Band** | One scoring bracket of a rubric metric (label, limit, score, pass). |
| **broadcast_id** | Identifier shared by one stimulus delivered to every trainee at the same sim time in fleet mode, for comparative reaction analysis. |
| **COG** | Cloud-Optimised GeoTIFF — the elevation format inside area packages (works fine offline; the name is historical). |
| **Critical metric** | A rubric metric whose fail band fails the whole session regardless of the weighted total. |
| **Curriculum** | Ordered stages of increasing difficulty for RL training (static pad → wind → moving pad). |
| **Dedicated server** | Headless UE5 server process that owns the shared world in fleet mode. |
| **ENU / NED / FRD** | East-North-Up and North-East-Down world frames; Forward-Right-Down body frame. Platform geometry is FRD; ArduPilot JSON uses NED/FRD; UE5 uses a left-handed centimetre frame. |
| **Event** | A discrete recorded occurrence: stimulus, response, outcome or annotation (`schemas/events.proto`). |
| **Failure mode** | A platform-declared fault (e.g. motor out, GPS loss) that scenarios and instructors can inject. |
| **Fleet Focus** | The maintainer-training programme: Explore / Rehearse / Improve on the airframe twin. |
| **Fleet mode** | Networked training: N trainee clients + instructor + dedicated server on one LAN. |
| **GCS** | Ground-control station software speaking MAVLink. |
| **Golden session** | A recorded reference session whose score must be identical on every run (Phase 3 acceptance). |
| **Inject** | An instructor- or scenario-triggered stimulus. |
| **JSON physics interface** | ArduPilot SITL's backend where an external simulator receives servo PWM and returns vehicle state as JSON. |
| **Lock-step** | Simulation advanced explicitly N physics ticks at a time (RL, deterministic tests), rather than paced by wall-clock. |
| **MAVLink** | The autopilot messaging protocol used between SITL, GCS, console and RL harness. |
| **Platform** | A vehicle type (drone, rover, helicopter, …): `platforms/<id>/platform.yaml` + UE5 plugin `CDSimPlatform_<id>`. |
| **Procedure** | An ordered list of maintenance steps with parts, tools, anchors and expected durations, declared in platform.yaml. |
| **RAVEN** | CDPL's only delivered programme. Nothing in this repository is RAVEN or claims its status. |
| **Readiness (`/ready`)** | HTTP endpoint that returns 200 only if all of a service's dependency checks pass (503 otherwise). |
| **Rubric** | YAML mapping metrics to weighted, banded scores and a pass threshold. |
| **Scenario** | YAML describing area, vehicles, spawn points, timed injects and end conditions. |
| **Session** | One continuous simulator run, recorded on one sim clock. |
| **seq** | Producer-local sequence number; tie-breaker after `sim_time_us`. |
| **sim_time_us** | The unified simulation clock: integer microseconds since session start. The only ordering key. |
| **Sim rate** | Multiplier of sim time over wall time, 0.1× to 10×. |
| **SITL** | Software-in-the-loop: the real autopilot firmware compiled for a PC, flying a simulated vehicle. |
| **Stimulus / response / outcome** | Event families: what the trainee should react to, what they did, what resulted. |
| **Terrain-RGB** | Elevation encoded into RGB raster tiles for fast client-side decoding. |
| **UNVERIFIED BUILD** | Marker on code that has never been compiled/run (currently `sim/` and the SITL image). |
