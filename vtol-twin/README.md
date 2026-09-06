# VTOL-1 digital twin

Prototype digital twin for a tail-sitter VTOL UAS (single ducted fan, heavy-fuel engine, EO/IR payload):
mission simulation / what-if analysis, and predictive maintenance with work-order automation.

* `docs/architecture.md` - layers, data flow, topic scheme, Thing model design
* `docs/runbook.md` - cold start to demo on one page
* `docs/data-dictionary.md` - every telemetry field, units, source, update rate
* `VERSIONS.md` - pinned versions

Demo mode, no Docker needed (Python 3.11+):

```bash
pip install -r demo/requirements.txt
make demo-ui              # open http://localhost:8090, pick a fault, "Start sortie"
```

Full stack (Docker Compose v2, curl, jq on the host):

```bash
cp .env.example .env      # review passwords/ports
make demo                 # up + wait for health + create Thing/policy/connection + verify
make demo-ui-live         # demo UI as a container, telemetry mirrored into Mosquitto -> Ditto
make verify-phase2        # MQTT->Influx ingester + 20 sample .ulg sorties into Influx/Thing, dashboards
```
