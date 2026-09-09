"""VTOL-1 demo mode: synthetic sorties, in-memory twin, live web UI.

Runs with no Docker at all (python -m demo) and, when the compose stack is up, mirrors the same
telemetry onto the real MQTT topics so Ditto / InfluxDB / Grafana receive it too.
"""
