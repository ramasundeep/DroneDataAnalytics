# cdpl_quad_01 — meshes

No real geometry yet. The UE5 plugin uses an engine-primitive placeholder
(`SM_Quad01_Placeholder`, built from cubes/cylinders in C++; see
`sim/Plugins/CDSimPlatform_cdpl_quad_01`).

When CDPL CAD arrives, place files here (all tracked by Git LFS via
`.gitattributes`):

| File | Purpose |
|---|---|
| `cdpl_quad_01.step` | authoritative CAD (source of truth) |
| `SM_Quad01.fbx` | exported render mesh, LOD0, metres, X-forward Z-up |
| `UCX_SM_Quad01.fbx` | convex collision hulls (optional; UE can auto-generate) |

Then follow docs/04_PLATFORM_PLUGIN_SPEC.md §"Swapping in real CAD":
update `meshes.visual` / `meshes.collision` in `platform.yaml`, set
`placeholder: false`, re-import in UE5, and name sockets exactly as the
`maintenance.parts[].anchor.socket` entries (`SOCKET_Prop_M1`, …).
