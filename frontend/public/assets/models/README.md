# Vehicle models

The inspector includes a complete procedural truck and ambulance. No model download is required.
To replace either, place `truck.glb` and `ambulance.glb` in this directory (served as `/assets/models/...`). The app checks for model files and uses the procedural vehicle if they are absent. Only enable map Scenegraph models when both files are present.

Use metres, Y-up, and a centered origin. Every clickable part or zone group should have Blender custom properties exported as glTF extras:

- `zone`: engine, cooling, electrical, brakes, transmission, tires, fuel
- `part_id`: a unique identifier, e.g. water_pump
- `label_fr`: e.g. Pompe à eau
- `explode_dir`: a three-number array, e.g. [-1.6, 0.15, 1.3]

Use one zone group per system, and assign extras on either that group or every mesh. Body-shell parts may use `is_shell: true` for translucent exploded rendering. Export separate wheels (6 for trucks, 4 for ambulances). Map models should be low-poly; Kenney Car Kit assets are CC0, but no external Kenney assets are included in this project.
