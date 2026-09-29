# scripts/

| Script | Used by | What |
|---|---|---|
| `validate_manifests.py` | `make schemas` | Validate JSON Schemas and every platform/area/rubric/scenario manifest |
| `new_platform.py` | `make new-platform id=…` | Scaffold `platforms/<id>/` + `sim/Plugins/CDSimPlatform_<id>/` |
| `new_area.py` | `make new-area id=…` | Scaffold `terrain/areas/<id>/area.yaml` |
| `smoke_dev.sh` | `make dev`, `make smoke` | Check every service's `/ready`, the console and its API proxy |
| `ue5/` | UE5 engineers, `ue5-build.yml` | Export manifests to JSON for UE5; build/cook scripts (see `docs/BUILDING_UE5.md`) |
