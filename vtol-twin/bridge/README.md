Telemetry bridge: MQTT -> InfluxDB ingester (`mqtt_ingest.py`), PX4 `.ulg` batch ingester (`ulog_ingest.py`),
uORB <-> feature mapping (`mapping.py`), synthetic ULog writer (`ulog_writer.py`). Phase 5 adds the MAVLink -> MQTT bridge.
See docs/architecture.md and docs/data-dictionary.md.
