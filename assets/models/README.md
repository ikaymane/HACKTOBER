# Vehicle 3D models (for the inspector)

| File | What |
|---|---|
| `truck.glb` | Rigid truck, 3 axles (6 wheels), ~8.5 m, 46 nodes |
| `ambulance.glb` | Ambulance van, 4 wheels, ~6.2 m, 45 nodes |
| `road.glb` | Straight 2-lane road tile, 60 m along X, sand shoulders. Vehicles drive +X in the right lane at z=0, y=0. Tile it along X. |
| `anim_truck.mp4`, `anim_ambulance.mp4` | 14 s showcase (good for the README / demo video): drives a curved desert road with a chase camera, eases to a stop in its lane, the body turns to glass, the mechanics turn see-through grey, and the camera eases in on the broken part (water pump / alternator) glowing red |
| `anim_truck.blend`, `anim_ambulance.blend` | The same scenes, to play or re-render in Blender (`assets/blender/animate_scene.py` builds them) |
| `preview_*.png` | Renders: assembled + exploded (exploded previews hide the body shell) |
| `vehicles.blend` | Blender source (both side by side) |

Rebuild after editing `assets/blender/build_vehicles.py`:
```bash
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python assets/blender/build_vehicles.py
```
Re-render a showcase video (`--preview` renders 5 check frames instead):
```bash
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python assets/blender/animate_scene.py -- truck
```
The showcase motion is computed, not hand-keyed:
- the vehicle follows its lane with a cruise → eased braking → stop speed profile
- heading comes from the path, and the front wheels steer from the path curvature
- wheel spin matches the distance travelled
- the sprung body pitches and rolls through a spring-damper driven by acceleration

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

## Animations baked in the GLBs
| Clip | Vehicles | Length | What |
|---|---|---|---|
| `drive` | both | 1 s, loop | Wheels + brake discs roll forward, body bobs slightly. Play while the vehicle moves on the map / road. |
| `explode` | both | 1 s, once | Every part slides from rest to `rest + explode_dir`. Play forward to open the exploded view, `timeScale = -1` to reassemble. Same motion as the `explode_dir` metadata, so pick either the clip or your own lerp. |
| `siren` | ambulance | 0.5 s, loop | Red/blue beacons pulse alternately. Play on emergency missions. |

```tsx
const { scene, animations } = useGLTF(`/models/${type}.glb`);
const { actions } = useAnimations(animations, scene);
actions.drive?.setLoop(THREE.LoopRepeat, Infinity).play();
const boom = actions.explode!; boom.setLoop(THREE.LoopOnce, 1); boom.clampWhenFinished = true;
boom.timeScale = exploded ? 1 : -1; boom.paused = false; boom.play();
// stop "drive" while exploded: both clips move body parts
```

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
