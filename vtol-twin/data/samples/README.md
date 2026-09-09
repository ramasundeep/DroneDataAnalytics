Synthetic sortie logs for offline testing: 20 PX4-style `.ulg` files plus `manifest.json`, produced by
`generate_samples.py` (deterministic). Degraded sorties: 07 EGT drift, 12-14 vibration rising, 18 servo 3 current creep.
Regenerate with `make gen-samples`; ingest with `make ingest-samples` (or `--dry-run` via `make ingest-dry-run`).
