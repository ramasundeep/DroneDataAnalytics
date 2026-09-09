# Pinned versions

| Component | Image / package | Version | Notes |
|---|---|---|---|
| Eclipse Ditto | `eclipse/ditto-{policies,things,things-search,connectivity,gateway,ui}` | 3.9.7 | latest stable at time of pinning |
| MongoDB | `mongo` | 7.0.40 | Ditto persistence |
| nginx | `nginx` | 1.27-alpine | basic-auth front for Ditto |
| Eclipse Mosquitto | `eclipse-mosquitto` | 2.0.22 | MQTT 5 broker |
| InfluxDB | `influxdb` | 2.7.12-alpine | time-series store |
| Grafana OSS | `grafana/grafana-oss` | 12.4.3 | dashboards |
| Python | `python` | 3.11-slim (services, Phase 2+) | |
| paho-mqtt | pip | 2.1.0 | demo mirror, MQTT ingester |
| influxdb-client | pip | 1.48.0 | ingesters, analytics |
| pyulog | pip | 1.2.0 | .ulg batch ingester |
| httpx | pip | 0.28.1 | Ditto REST client |
| fastapi / uvicorn / pydantic | pip | 0.115.6 / 0.34.0 / 2.10.4 | demo, analytics, maintenance services |
| scikit-learn / pandas | pip | 1.6.1 / 2.2.3 | analytics |
| pytest | pip | 8.3.4 | dev only |

Python service dependencies (FastAPI, paho-mqtt, pymavlink, pyulog, influxdb-client, scikit-learn, pandas)
are pinned in each service's `requirements.txt` as the services are added in Phases 2-5.

Override any image tag through `.env` (`DITTO_VERSION`, `MONGO_VERSION`, ...); the compose file
falls back to the values above.
