"""Predictive-maintenance analytics for the VTOL-1 twin.

features.py  per-sortie feature extraction (engine / actuation / power signal groups)
sources.py   where sorties come from: InfluxDB (live stack) or .ulg files (offline)
anomaly.py   rolling robust baseline + IsolationForest per signal group
rul.py       life-limit RUL, trend projection to threshold, health score, alert level
engine.py    orchestration: records -> per-sortie anomaly results + per-component health
service.py   FastAPI service (schedule + after-ingest trigger) writing to Ditto and InfluxDB
run.py       CLI for offline runs over the sample set
"""
