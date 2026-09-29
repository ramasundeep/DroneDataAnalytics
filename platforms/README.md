# platforms/

One directory per vehicle platform. **Data, not code** — the UE5 side lives
in `sim/Plugins/CDSimPlatform_<id>/`. Full spec:
[docs/04_PLATFORM_PLUGIN_SPEC.md](../docs/04_PLATFORM_PLUGIN_SPEC.md).

| id | class | status |
|---|---|---|
| `cdpl_quad_01` | multirotor | placeholder geometry & mass (awaiting CAD) |

```bash
make new-platform id=my_new_vehicle   # copies _template/, creates UE plugin skeleton
make schemas                          # validates every platform.yaml
```

`_template/` is the scaffold source; it is excluded from validation.
