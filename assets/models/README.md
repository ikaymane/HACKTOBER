# Vehicle 3D models (for the inspector)

| File | What |
|---|---|
| `truck.glb` | Rigid truck, 3 axles (6 wheels), ~8.5 m, 46 nodes |
| `ambulance.glb` | Ambulance van, 4 wheels, ~6.2 m, 45 nodes |
| `preview_*.png` | Renders: assembled + exploded (exploded previews hide the body shell) |
| `vehicles.blend` | Blender source (both side by side) |

Rebuild after editing `assets/blender/build_vehicles.py`:
```bash
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python assets/blender/build_vehicles.py
```

Copy the GLBs to `frontend/public/models/`.

## Node metadata (three.js `object.userData`)
Each part is one direct child node of the root (`Truck` / `Ambulance`). Read **`userData`**, not node names: names can get suffixes like `.001`.

| key | values |
|---|---|
| `zone` | `engine` `cooling` `electrical` `brakes` `transmission` `tires` `fuel` `body` |
| `part_id` | catalog id matching backend `parts.json` (`P-WPUMP`, `P-ALT`, `P-BCAL`, ...) or `""` for structure |
| `label_fr` | display name, e.g. "Pompe à eau" |
| `explode_dir` | `[x, y, z]` in three.js space (Y up, +X = vehicle front). Exploded position = `base + explode_dir * t`, t ≈ 0 → 1 |

Parts with a `part_id`, per vehicle:
- **engine:** `P-OILP` block, `P-TURBO` turbo, `P-EGR` EGR valve, `P-DPF` particulate filter
- **cooling:** `P-RAD` radiator, `P-WPUMP` water pump, `P-THERM` thermostat
- **electrical:** `P-ALT` alternator, `P-STARTER` starter, `P-BATT` battery
- **brakes:** `P-BCAL` caliper ×wheels, `P-BPAD` disc/pads ×wheels
- **transmission:** `P-CLUTCH` gearbox (driveshaft has no id)
- **tires:** `P-TIRE` each wheel (tire + rim + hub merged)
- **fuel:** `P-INJ` injector rail (tank has no id)
- **body:** shell (cab, cargo/patient box, windows, lights, stripes). Fade to `opacity 0.12` when exploded; the chassis rails can stay visible.

## How the frontend should use it
```ts
const { scene } = useGLTF(`/models/${vehicle.type}.glb`);   // "truck" | "ambulance"
scene.traverse((o) => {
  const u = o.userData;
  if (!u.zone) return;
  o.userData.base = o.position.clone();
  // clone material per mesh before recoloring: zones share materials (zone_cooling, ...)
});
// each frame: o.position.copy(base).addScaledVector(new Vector3(...u.explode_dir), t)
// color: health.zones[u.zone].status → ok/warn/fail; the exact failed part = u.part_id === incident.diagnosis.part_id (pulse red)
// click: e.object (walk up parents until userData.zone) → open the part popup with incident for that zone
```
Materials are named `zone_<zone>` (neutral colors). Glass, lights and the ambulance beacons have emission.
