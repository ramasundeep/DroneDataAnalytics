# sim/Content

UE content root (`/Game/`). **No assets are committed yet.**

- Everything binary here (`.uasset`, `.umap`, textures, meshes, audio) is stored
  through **Git LFS** (root `.gitattributes`). Run `git lfs install` once and
  `git lfs pull` after cloning. Never commit UE binaries as plain git blobs.
- Phase 1 runs on the engine's empty `/Engine/Maps/Entry` map: the ground
  plane, sun and landing pads for `flat_test` are spawned from
  `Config/Areas/flat_test.json` by `UCDSimAreaLoader`, and the vehicle's
  placeholder look is built from `/Engine/BasicShapes` by the platform plugin.
- Planned layout (create folders as content arrives):

  | Path | Contents | Phase |
  |---|---|---|
  | `CDSim/Maps/L_FlatTest` | first real map, replaces `/Engine/Maps/Entry` | 1 |
  | `CDSim/UI/` | HUD / menus — every screen carries the Chakravyuha Dynamics logo placeholder | 4 |
  | `CDSim/Input/` | Enhanced Input actions + mapping contexts (manual flight) | 4 |
  | `CDSim/VR/` | VR pawn, motion-controller mappings | 5 |
  | `CDSim/Markers/` | AprilTag pad materials | 7 |

Platform-specific assets live in their plugin (`sim/Plugins/CDSimPlatform_<id>/Content/`),
never here. See `docs/BUILDING_UE5.md` and `docs/10_ROADMAP.md`.
