# Predictive maintenance analytics (Phase 3)

The analytics service turns telemetry into three numbers per component on the Thing's `health`
feature: `healthScore` (0-100), `rulHours` and `alertLevel` (`normal` < `advisory` < `caution` <
`warning`). `caution` or worse opens a work order in Phase 4. Everything below runs identically over
the InfluxDB bucket (live stack) and over `.ulg` files (offline, `make analytics-run`).

## 1. Per-sortie features (`analytics/features.py`)

Each sortie is reduced to a flat feature vector computed on armed samples, with steady-state
statistics taken on the fixed-wing cruise segment (the engine sits at one operating point there, so
cruise statistics are the cleanest condition indicators). Three signal groups:

| Group | Features | Speaks for |
|---|---|---|
| engine | `egt_cruise_mean/p95`, `egt_max`, `cht_cruise_mean`, `rpm_cruise_std`, `oil_cruise_mean`, `fuel_flow_per_krpm`, `vib_cruise_mean`, `vib_hover_mean`, `vib_max`, `vib_per_rpm2` | engine, ducted fan (`vib_*`), fuel pump (`fuel_*`) |
| actuation | per servo: `servoN_cur_mean`, `servoN_cur_p95`, `servoN_cur_ratio` (mean vs median of the four) | servo 1-4 |
| power | `bus_v_mean/min`, `bus_i_mean`, `batt_v_min`, `batt_v_start_min` (voltage under starter load), `batt_temp_max`, `batt_drop_pct` | avionics bus, battery |

Hard limits (EGT 680 °C, CHT 205 °C, vibration RMS 1.8 m/s², servo current 1.9 A, bus < 24 V,
battery > 55 °C) are checked on every sample and reported as exceedances alongside the features.

## 2. Anomaly detection (`analytics/anomaly.py`)

Sorties are scored in chronological order against a **rolling baseline** of earlier sorties that were
not flagged (up to 30 per group). Two detectors run per group:

* **Robust z-scores**: `(x - median) / spread` per feature, with `spread = max(MAD·1.4826, std, noise
  floor)`. The noise floor (3 °C for EGT, 0.03 m/s² for vibration, 0.03 A for servo current, ...) is
  what stops a handful of near-identical sorties from turning sensor noise into an anomaly. The largest
  |z| and the features behind it are reported, which is what a maintainer needs to see.
* **IsolationForest** (scikit-learn, 200 trees) fitted on the standardised baseline vectors, once at
  least 8 baseline sorties exist. Its score is converted into a z-score against the baseline's own
  scores so both detectors share one scale; it catches multivariate drift where no single feature
  crosses the line.

A group is flagged when `zmax >= 4`, `IF z >= 3.5`, or a hard limit was exceeded. The reported anomaly
score is 0.5 at the flag boundary and saturates at 1. Flagged sorties never enter the baseline. The
first 5 sorties are warm-up: only hard limits can flag them.

On the sample set the detector flags exactly the five degraded sorties (07 EGT drift in the engine
group, attributed to the engine; 12-14 vibration rise, attributed to the ducted fan; 18 servo 3 current
creep in the actuation group, attributed to servo 3) and none of the fifteen nominal ones.

## 3. Remaining useful life (`analytics/rul.py`)

Two estimates, combined by taking the minimum:

1. **Life-limit RUL** from the Thing's `lifeCounters`: hours left to the hour limit, and the
   hour-equivalent of the cycles left (cycles remaining / observed cycles per hour). Linear consumption,
   available from day one, exact by definition.
2. **Trend RUL** for components with a condition indicator (cruise EGT for the engine, cruise vibration
   for the ducted fan, p95 current per servo, fuel flow per kRPM for the pump, starter-load voltage for
   the battery): linear regression of the indicator against cumulative flight hours over the last 6
   sorties, projected to the limit. Only projected when the indicator is elevated (at least 20 % of the
   way from nominal to limit) and moving towards the limit, so nominal noise never produces a spurious
   short RUL; 0 when the indicator is already over the limit.

## 4. Health score and alert level

```
score = 100
      - 35 * min(life ratio, 1)                  hours or cycles used / limit
      - 60 * min(condition ratio, 1.5)           (indicator - nominal) / (limit - nominal)
      - 25 if a limit was exceeded recently      (within the last 3 sorties)
      - up to 15 for an anomaly on this component's features
alert = max(life >= 90 % -> caution, >= 80 % -> advisory;
            exceedance -> caution; anomaly -> advisory;
            score < 50 -> warning, < 65 -> caution, < 80 -> advisory)
```

A limit exceedance holds its component at **caution for three sorties** even if the indicator recovers,
because the condition is evidence for maintenance, not a transient. The evidence block on each
component (`indicator`, `level`, `threshold`, `slopePerHour`, `trendRulHours`, `lastExceedance`
{sortie, signal, peak, limit}) is what the Phase 4 work order carries.

## 5. Where it runs

`analytics/service.py` (compose profile `pipeline`, port 8092) scores every sortie of the tail on a
schedule (`ANALYTICS_INTERVAL_S`, default 15 min) and again whenever Ditto publishes a `lifeCounters`
change on `vtol/+/events`, i.e. right after the batch ingester books a sortie. Results go to the Thing
(`health` feature: per component plus `lastRun`) and to InfluxDB (`health` per component, `anomaly`
per sortie and group), which the fleet dashboard reads. `POST /run` forces a run, `GET /latest` returns
the full result. The demo UI's in-memory scoring (`demo/twin.py`) is a compact preview of the same
formulas.

## 6. From synthetic to real engine data

The pipeline is deliberately model-agnostic at two seams:

* **Features**: `extract()` produces one row per sortie. With real fleets, sortie rows accumulate into
  exactly the run-to-failure / run-to-maintenance matrix that NASA C-MAPSS-style methods consume
  (unit = engine serial, cycle = sortie, sensors = the features here). Once tens of engines and a
  handful of removals exist, a data-driven RUL model (gradient boosting or an LSTM over the sortie
  sequence, trained on hours-to-removal) plugs in beside `trend_rul()` and the minimum rule keeps
  whichever is more conservative.
* **Baselines**: the rolling per-tail baseline becomes a fleet baseline keyed by engine serial and
  operating point (rpm / OAT bins) as soon as there is more than one aircraft, which also lets the
  IsolationForest be trained once per fleet instead of per tail.

Thresholds and nominal levels live in `analytics/features.py` (`LIMITS`, `NOISE_FLOOR`) and
`analytics/rul.py` (`INDICATORS`); replace them with the engine manual's limits when real data arrives.
