# terrain/ — digital terrain twins

Full spec: `docs/03_DIGITAL_TERRAIN_TWINS.md`.

| Path | What | Phase 0 status |
|---|---|---|
| `areas/<id>/area.yaml` | Area manifests (data itself is built into packages, never committed) | ✅ `hyd_demo_01`, `flat_test` |
| `builder/` | `cdsim-area validate | plan | package` | ✅ validate, plan · ⏳ package (Phase 2) |
| `services/` | Offline tiles / mesh / elevation / weather services (one image, four entrypoints) | ✅ running in `make dev`; serve built packages; flat elevation; DEM sampling Phase 2 |

```bash
.venv/bin/cdsim-area validate terrain/areas/hyd_demo_01/area.yaml
.venv/bin/cdsim-area plan terrain/areas/hyd_demo_01/area.yaml
make new-area id=my_area
curl "localhost:8103/v1/elevation?lat=17.40&lon=78.50"     # flat_test → 500.0
```

Built packages unpack to `areas/<id>/build/` (gitignored) and are stored in
MinIO bucket `cdsim-areas`. Internet is used only by the builder, never by the
services.
