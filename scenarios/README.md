# scenarios/

Scenario definitions: area, vehicles and spawn points, timed injects, end
conditions and the rubric used to score them. Schema:
`schemas/json/scenario.schema.json`; semantics: `docs/07_TRAINING_MODES.md`.
Validated by `make schemas` (including cross-references: area and pads exist,
platforms exist, injected failure modes exist on a vehicle).

| Scenario | Use |
|---|---|
| `sitl_core_loop.yaml` | Phase 1 acceptance: headless takeoff → waypoint → land on `flat_test` (`missions/core_loop.waypoints`, QGC WPL 110) |
| `landing_motor_failure_01.yaml` | Single-seat precision landing with a degraded motor on `hyd_demo_01` |

The scenario runner that executes these arrives in Phase 1 (scripted SITL)
and Phase 4 (instructor-driven).
