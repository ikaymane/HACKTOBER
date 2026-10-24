"""Real diesel engine for the vehicles: "Truck Engine" by andreviewport (Sketchfab, CC BY 4.0).
https://sketchfab.com/3d-models/truck-engine-d7ff313ff1e64c4db803e39b600a0fbf

install_engine(root, vehicle) imports assets/models/source/truck_engine.glb, joins it into one steel
mesh, cuts the failure zones (water pump, alternator) out as their own objects, scales/rotates it into
the vehicle's engine bay and removes the simple placeholder parts it replaces.

Source model units are centimetres, long axis +Y (fan at -Y = front), up +Z.
Zones were located on an orthographic front view: water pump pulley + housing at x~110 z~53,
alternator body x~74 z~46 with its pulley at x~81 z~43 (all cm, model space).
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "models", "source", "truck_engine.glb"))

# failure zones in model space: list of (x, z, radius) discs, between the fan and y_max
FAN_BACK_Y = 226.0  # fan blades sit at y 222.7..225.1
ZONES = {
    "P-WPUMP": {"name": "engine__water_pump", "zone": "cooling", "label": "Pompe à eau",
                "discs": [(110.0, 53.5, 6.8)], "y_max": 246.0},
    "P-ALT": {"name": "engine__alternator", "zone": "electrical", "label": "Alternateur",
              "discs": [(81.5, 43.0, 6.5), (74.5, 46.5, 7.0)], "y_max": 268.0},
}

# placement per vehicle (vehicle space, Blender metres): front of the engine (fan) x, bottom z, scale
BAY = {
    "truck": {"front_x": 3.86, "bottom_z": 0.62, "scale": 0.01},
    "ambulance": {"front_x": 2.98, "bottom_z": 0.50, "scale": 0.0055},
}

# placeholder parts the real engine replaces
REPLACED = ("engine__block", "engine__turbo", "engine__egr_valve", "fuel__injector_rail", "cooling__water_pump",
            "cooling__thermostat", "electrical__alternator", "electrical__starter", "transmission__gearbox")


def _steel():
    m = bpy.data.materials.get("engine_steel") or bpy.data.materials.new("engine_steel")
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.30, 0.32, 0.35, 1)
    bsdf.inputs["Metallic"].default_value = 0.85
    bsdf.inputs["Roughness"].default_value = 0.38
    return m


def _in_zone(p, z):
    if not (FAN_BACK_Y < p.y <= z["y_max"]):  # skip the fan blades in front of the pulleys
        return False
    return any((p.x - x) ** 2 + (p.z - zz) ** 2 <= r * r for x, zz, r in z["discs"])


def _import_joined():
    """Import the GLB and return one joined mesh object in model space (cm), steel material."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SRC)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    bpy.context.view_layer.update()
    for o in meshes:  # bake the importer hierarchy into the meshes, then drop the empties
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    empties = [o for o in new if o.type != "MESH"]
    with bpy.context.temp_override(selected_editable_objects=meshes, active_object=meshes[0]):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.object.join()  # removes the other mesh objects itself
    eng = meshes[0]
    for o in empties:
        bpy.data.objects.remove(o, do_unlink=True)
    eng.data.materials.clear()
    eng.data.materials.append(_steel())
    for p in eng.data.polygons:
        p.material_index = 0
    return eng


def _cut_zone(eng, z):
    """Move the faces inside the zone to a new object; returns it."""
    bm = bmesh.new()
    bm.from_mesh(eng.data)
    inside = [f for f in bm.faces if _in_zone(f.calc_center_median(), z)]
    zone_bm = bm.copy()
    keep = {f.index for f in inside}
    zone_bm.faces.ensure_lookup_table()
    bmesh.ops.delete(zone_bm, geom=[f for f in zone_bm.faces if f.index not in keep], context="FACES")
    bmesh.ops.delete(bm, geom=inside, context="FACES")
    bm.to_mesh(eng.data)
    bm.free()
    me = bpy.data.meshes.new(z["name"])
    zone_bm.to_mesh(me)
    zone_bm.free()
    o = bpy.data.objects.new(z["name"], me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(_steel())
    return o


def _set_origin_to_centre(o):
    pts = [v.co for v in o.data.vertices]
    c = sum(pts, Vector()) / max(1, len(pts))
    o.data.transform(Matrix.Translation(-c))
    o.location = o.location + c


def install_engine(root, vehicle, tag, decimate=None):
    """Replace the placeholder engine of `root` (vehicle empty at its rest pose) with the real engine.

    tag = build_vehicles.tag (sets zone / part_id / label_fr / explode_dir). Returns {part_id: zone_object}.
    decimate: optional face ratio (e.g. 0.15) for web exports.
    """
    for o in [c for c in bpy.data.objects if c.parent == root and c.name.split(".")[0] in REPLACED]:
        bpy.data.objects.remove(o, do_unlink=True)

    eng = _import_joined()
    zones = {pid: _cut_zone(eng, z) for pid, z in ZONES.items()}

    bay = BAY[vehicle]
    s = bay["scale"]
    # model (cm, front -Y, up +Z) -> vehicle (m, front +X): rotate +90 deg about Z, scale, then place
    xs = [v.co for v in eng.data.vertices]
    mn = Vector((min(p.x for p in xs), min(p.y for p in xs), min(p.z for p in xs)))
    mx = Vector((max(p.x for p in xs), max(p.y for p in xs), max(p.z for p in xs)))
    centre_x = (mn.x + mx.x) / 2
    m = (Matrix.Translation((bay["front_x"], 0, bay["bottom_z"])) @ Matrix.Rotation(math.radians(90), 4, "Z")
         @ Matrix.Scale(s, 4) @ Matrix.Translation((-centre_x, -mn.y, -mn.z)))
    for o in [eng, *zones.values()]:
        o.data.transform(m)
        if decimate:
            d = o.modifiers.new("decimate", "DECIMATE")
            d.ratio = decimate
            with bpy.context.temp_override(object=o, active_object=o):
                bpy.ops.object.modifier_apply(modifier=d.name)
        _set_origin_to_centre(o)
        loc = o.location.copy()
        o.parent = root
        o.matrix_parent_inverse = root.matrix_world.inverted()
        o.location = loc
        for p in o.data.polygons:
            p.use_smooth = True

    eng.name = eng.data.name = "engine__diesel"
    tag(eng, "engine", "", "Moteur diesel", (0, 0, 1.2))
    for pid, o in zones.items():
        z = ZONES[pid]
        tag(o, z["zone"], pid, z["label"], (0.6, 0, 1.6))
    return zones
