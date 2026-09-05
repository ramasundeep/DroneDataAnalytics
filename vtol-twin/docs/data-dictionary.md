# VTOL-1 data dictionary

Conventions: MQTT topic `vtol/VTOL-1/telemetry/<feature>`; property names are camelCase with the unit
as suffix where one applies; timestamps are ISO-8601 UTC strings. "Source" is the originating
system for real flights, with the PX4 uORB topic used by the SITL bridge / ulog ingester in brackets.
Rates are the *published* rates; the bridge decimates higher-rate MAVLink streams.

Every telemetry feature carries `ts` (source timestamp of the last update). Ditto adds `_modified`
on the Thing itself.

## Feature `engine` - 2 Hz

| Property | Unit | Type | Source | Notes |
|---|---|---|---|---|
| `rpm` | rev/min | number | engine ECU via FCU [`internal_combustion_engine_status`, fallback `esc_status`] | ducted-fan shaft speed |
| `egtC` | °C | number | ECU exhaust-gas thermocouple | drift indicator (Phase 3) |
| `chtC` | °C | number | ECU cylinder-head thermocouple | |
| `fuelFlowLph` | L/h | number | ECU fuel flow / injector duty | |
| `throttlePct` | % | number | FCU actuator output [`actuator_motors`] | 0-100 |
| `oilPressureKpa` | kPa | number | ECU | 0 when engine off |
| `running` | - | bool | ECU / derived from rpm > 500 | |

## Feature `vibration` - 1 Hz (RMS over the last second)

| Property | Unit | Type | Source | Notes |
|---|---|---|---|---|
| `rmsX`, `rmsY`, `rmsZ` | m/s² | number | FCU IMU [`vehicle_imu_status.accel_vibration_metric`, `sensor_accel`] | body axes |
| `rmsTotal` | m/s² | number | derived: sqrt(x²+y²+z²) | trend input for ducted-fan/engine RUL |
| `clipCount` | count | integer | FCU [`vehicle_imu_status.accel_clipping`] | cumulative per sortie |

## Feature `actuation` - 2 Hz

| Property | Unit | Type | Source | Notes |
|---|---|---|---|---|
| `servo1CurrentA` .. `servo4CurrentA` | A | number | servo bus telemetry (smart servos) [SITL: synthesized from `actuator_outputs` load] | creep indicator |
| `servo1PositionDeg` .. `servo4PositionDeg` | deg | number | servo bus / FCU [`actuator_outputs`] | servo1 elevon-left, servo2 elevon-right, servo3 thrust-vane-A, servo4 thrust-vane-B |

## Feature `power` - 1 Hz

| Property | Unit | Type | Source | Notes |
|---|---|---|---|---|
| `busVoltageV` | V | number | power distribution [`battery_status`/`system_power`] | 28 V main bus |
| `busCurrentA` | A | number | power distribution | |
| `batteryVoltageV` | V | number | BMS [`battery_status.voltage_v`] | |
| `batteryCurrentA` | A | number | BMS [`battery_status.current_a`] | positive = discharge |
| `batteryRemainingPct` | % | number | BMS [`battery_status.remaining`] | 0-100 |
| `batteryTempC` | °C | number | BMS [`battery_status.temperature`] | |

## Feature `navigation` - 1 Hz

| Property | Unit | Type | Source | Notes |
|---|---|---|---|---|
| `gpsFixType` | - | integer | GNSS [`sensor_gps.fix_type`] | 0 none, 2 2D, 3 3D, 4 DGPS, 5/6 RTK |
| `gpsSatellites` | count | integer | GNSS [`sensor_gps.satellites_used`] | |
| `gpsHdop` | - | number | GNSS [`sensor_gps.hdop`] | |
| `insStatus` | - | string | FCU estimator [`estimator_status`] | `ok`, `degraded`, `failed`, `unknown` |
| `insAligned` | - | bool | FCU estimator | attitude + position valid |

## Feature `flightState` - 1 Hz

| Property | Unit | Type | Source | Notes |
|---|---|---|---|---|
| `sortieId` | - | string | bridge / ingester | `YYYYMMDD-VTOL-1-NN`; null on ground |
| `armed` | - | bool | FCU [`vehicle_status.arming_state`] | |
| `flightMode` | - | string | FCU [`vehicle_status.nav_state`] | PX4 nav state name |
| `vtolState` | - | string | FCU [`vehicle_status.vehicle_type`, `vtol_vehicle_status`] | `hover`, `transition-forward`, `fixed-wing`, `transition-back` |
| `lat`, `lon` | deg | number | FCU [`vehicle_global_position`] | WGS-84 |
| `altMslM` | m | number | FCU [`vehicle_global_position.alt`] | |
| `altAglM` | m | number | FCU [`vehicle_local_position.dist_bottom` or alt - home] | |
| `airspeedMps` | m/s | number | FCU [`airspeed_validated`] | true airspeed |
| `groundspeedMps` | m/s | number | FCU [`vehicle_global_position` velocity norm] | |
| `headingDeg` | deg | number | FCU [`vehicle_attitude` yaw] | 0-360 |
| `flightTimeS` | s | number | derived since arming | |

## Feature `lifeCounters` - after each ingested sortie (Phase 2)

| Property | Unit | Type | Source | Notes |
|---|---|---|---|---|
| `<component>.hours` | h | number | ingester | cumulative, advanced by sortie flight time |
| `<component>.cycles` | count | integer | ingester | engine/fan: starts; servos: flights; battery: charge cycles |
| `airframe.hours`, `airframe.cycles` | h, count | | ingester | cycles = landings |
| `lastSortieId` | - | string | ingester | |
| `updatedAt` | - | string | ingester | ISO-8601 |

## Feature `health` - on schedule and after each sortie (Phase 3/4)

| Property | Unit | Type | Source | Notes |
|---|---|---|---|---|
| `<component>.healthScore` | 0-100 | number | analytics | 100 = nominal |
| `<component>.rulHours` | h | number | analytics | min(life-limit remaining, trend projection) |
| `<component>.alertLevel` | - | string | analytics | `normal` < `advisory` < `caution` < `warning`; `caution`+ opens a work order |
| `aircraft.releaseStatus` | - | string | maintenance | `serviceable`, `unserviceable`, `limited` |
| `aircraft.openWorkOrders` | count | integer | maintenance | |

## Attributes (static, `attributes.components.<id>`)

`name`, `position` (servos), `partNumber`, `serial`, `installDate` (ISO date), `lifeLimitHours`,
`lifeLimitCycles`, `hoursConsumed`, `cyclesConsumed` (values at last maintenance-record update).

## InfluxDB schema (Phase 2)

Bucket `flight_telemetry`; measurement = feature name; fields = the properties above; tags `tail`,
`sortie`, `source` (`live` | `ulog` | `sitl`).
