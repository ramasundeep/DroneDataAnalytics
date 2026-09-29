# CDSimPlatform_cdpl_quad_01 — Content

**Empty for now.** This folder is mounted in-engine as `/CDSimPlatform_cdpl_quad_01/`.

- All binaries here (`.uasset`, `.umap`, textures, FBX imports) go through
  **Git LFS** (see the root `.gitattributes`). Never commit them as plain git blobs.
- The placeholder airframe is currently built at runtime from engine basic
  shapes by `UCDSimQuad01Visuals` (Source/), so no assets are required.
- `platform.yaml` already names the future asset:
  `/CDSimPlatform_cdpl_quad_01/Meshes/SM_Quad01_Placeholder`. When CAD arrives,
  import it to `Meshes/` following `docs/04_PLATFORM_PLUGIN_SPEC.md`
  ("Swapping in real CAD"), and give the static mesh sockets with exactly the
  names used by `maintenance.parts[].anchor.socket`
  (`SOCKET_Prop_M1..M4`, `SOCKET_Motor_M2`, `SOCKET_Battery`).
