"""Build the FleetSense truck + ambulance in Blender and export GLBs for the 3D inspector.

Run (headless):
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python assets/blender/build_vehicles.py

Outputs in assets/models/: truck.glb, ambulance.glb, vehicles.blend, preview_*.png

Every clickable part is its own node with glTF extras (three.js: object.userData):
  zone        engine | cooling | electrical | brakes | transmission | tires | fuel | body
  part_id     catalog id (P-WPUMP, P-ALT, ...) or "" for structure
  label_fr    display name
  explode_dir [x, y, z] in three.js coords (Y up): direction the part slides in the exploded view
"""
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "models"))
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- materials
_mats = {}


def mat(name, rgb, metal=0.0, rough=0.5, emit=None):
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1)
        bsdf.inputs["Emission Strength"].default_value = 3.0
    m.diffuse_color = (*rgb, 1)
    _mats[name] = m
    return m


ZONE_RGB = {  # neutral technical colors; the frontend recolors by health status
    "engine": (0.30, 0.32, 0.36), "cooling": (0.20, 0.45, 0.70), "electrical": (0.75, 0.60, 0.15),
    "brakes": (0.55, 0.20, 0.20), "transmission": (0.35, 0.30, 0.45), "tires": (0.06, 0.06, 0.07),
    "fuel": (0.25, 0.50, 0.30),
}


def zone_mat(zone):
    metal = 0.0 if zone == "tires" else 0.6
    return mat(f"zone_{zone}", ZONE_RGB[zone], metal=metal, rough=0.45 if zone != "tires" else 0.9)


# ---------------------------------------------------------------- primitives
def _finish(obj, material, bevel):
    obj.data.materials.append(material)
    if bevel:
        b = obj.modifiers.new("bevel", "BEVEL")
        b.width, b.segments, b.limit_method = bevel, 3, "ANGLE"
    for p in obj.data.polygons:
        p.use_smooth = False
    return obj


def box(name, loc, size, material, bevel=0.03, parent=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = o.data.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    o.parent = parent
    return _finish(o, material, bevel)


def cyl(name, loc, r, depth, material, axis="Z", verts=40, bevel=0.01, parent=None):
    rot = {"Z": (0, 0, 0), "Y": (math.pi / 2, 0, 0), "X": (0, math.pi / 2, 0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = o.data.name = name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)  # keep origin at the part centre
    o.parent = parent
    o = _finish(o, material, bevel)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def join(name, objs):
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs):
        bpy.ops.object.join()
    objs[0].name = objs[0].data.name = name
    return objs[0]


def to_three(v):  # Blender Z-up (x, y, z) -> three.js Y-up (x, z, -y)
    x, y, z = v
    return [round(x, 3), round(z, 3), round(-y, 3)]


def tag(o, zone, part_id="", label="", explode=(0, 0, 0)):
    o["zone"], o["part_id"], o["label_fr"] = zone, part_id, label
    o["explode_dir"] = to_three(explode)
    return o


# ---------------------------------------------------------------- shared assemblies
def wheel(root, prefix, x, y, r, w, rim_mat, side):
    tire = cyl(f"{prefix}_tire", (x, y, r), r, w, mat("tire_rubber", (0.05, 0.05, 0.055), rough=0.95), axis="Y", verts=48)
    rim = cyl(f"{prefix}_rim", (x, y + side * 0.01, r), r * 0.58, w + 0.02, rim_mat, axis="Y", verts=32)
    hub = cyl(f"{prefix}_hub", (x, y + side * 0.03, r), r * 0.18, w + 0.04, mat("chrome", (0.8, 0.8, 0.82), metal=1, rough=0.2), axis="Y", verts=16)
    t = join(f"tires__wheel_{prefix}", [tire, rim, hub])
    t.parent = root
    tag(t, "tires", "P-TIRE", f"Pneu {prefix}", (0, side * 1.4, 0))
    # brake disc + caliper, inboard of the wheel
    by = y - side * (w / 2 + 0.06)
    disc = cyl(f"brakes__disc_{prefix}", (x, by, r), r * 0.62, 0.05, mat("brake_disc", (0.45, 0.45, 0.47), metal=1, rough=0.35), axis="Y", verts=40, parent=root)
    tag(disc, "brakes", "P-BPAD", f"Disque / plaquettes {prefix}", (0, side * 0.8, 0.15))
    cal = box(f"brakes__caliper_{prefix}", (x + r * 0.35, by - side * 0.02, r + r * 0.35), (r * 0.35, 0.14, r * 0.28), zone_mat("brakes"), bevel=0.02, parent=root)
    tag(cal, "brakes", "P-BCAL", f"Étrier de frein {prefix}", (0.15, side * 0.8, 0.45))


def drivetrain(root, s):
    """Mechanical parts shared by both vehicles. s = dict of positions/sizes."""
    e = box("engine__block", s["engine"], s["engine_size"], zone_mat("engine"), parent=root)
    tag(e, "engine", "P-OILP", "Bloc moteur / pompe à huile", (0, 0, 1.6))
    tx, ty, tz = s["engine"]
    turbo = cyl("engine__turbo", (tx - 0.1, ty - s["engine_size"][1] / 2 - 0.12, tz + 0.1), 0.13, 0.22, zone_mat("engine"), axis="Y", parent=root)
    tag(turbo, "engine", "P-TURBO", "Turbocompresseur", (0, -1.0, 1.2))
    egr = cyl("engine__egr_valve", (tx + 0.15, ty + s["engine_size"][1] / 2 + 0.07, tz + 0.15), 0.06, 0.12, zone_mat("engine"), axis="Y", parent=root)
    tag(egr, "engine", "P-EGR", "Vanne EGR", (0, 1.0, 1.3))
    dpf = cyl("engine__dpf", s["dpf"], 0.16, 0.7, zone_mat("engine"), axis="X", parent=root)
    tag(dpf, "engine", "P-DPF", "Filtre à particules", (0, -0.6, -0.8))
    inj = box("fuel__injector_rail", (tx, ty, tz + s["engine_size"][2] / 2 + 0.06), (s["engine_size"][0] * 0.8, 0.08, 0.08), zone_mat("fuel"), bevel=0.01, parent=root)
    tag(inj, "fuel", "P-INJ", "Rampe d'injecteurs", (0, 0, 2.4))

    rad = box("cooling__radiator", s["radiator"], s["radiator_size"], zone_mat("cooling"), bevel=0.01, parent=root)
    tag(rad, "cooling", "P-RAD", "Radiateur", (1.6, 0, 0.2))
    pump = cyl("cooling__water_pump", s["water_pump"], 0.1, 0.12, zone_mat("cooling"), axis="X", parent=root)
    tag(pump, "cooling", "P-WPUMP", "Pompe à eau", (1.1, 0.3, 0.6))
    therm = cyl("cooling__thermostat", (s["water_pump"][0] - 0.05, s["water_pump"][1] - 0.2, s["water_pump"][2] + 0.25), 0.05, 0.08, zone_mat("cooling"), parent=root)
    tag(therm, "cooling", "P-THERM", "Thermostat", (1.0, -0.3, 0.9))

    alt = cyl("electrical__alternator", s["alternator"], 0.12, 0.2, zone_mat("electrical"), axis="X", parent=root)
    tag(alt, "electrical", "P-ALT", "Alternateur", (0.4, -1.3, 0.8))
    starter = cyl("electrical__starter", s["starter"], 0.08, 0.25, zone_mat("electrical"), axis="X", parent=root)
    tag(starter, "electrical", "P-STARTER", "Démarreur", (0, 1.3, -0.4))
    batt = box("electrical__battery", s["battery"], s["battery_size"], zone_mat("electrical"), bevel=0.015, parent=root)
    tag(batt, "electrical", "P-BATT", "Batterie", (0, -1.4, 0.2))

    gb = box("transmission__gearbox", s["gearbox"], s["gearbox_size"], zone_mat("transmission"), parent=root)
    tag(gb, "transmission", "P-CLUTCH", "Boîte / embrayage", (0, 0, -1.2))
    x0, x1 = s["driveshaft_x"]
    ds = cyl("transmission__driveshaft", ((x0 + x1) / 2, 0, s["driveshaft_z"]), 0.06, abs(x0 - x1), zone_mat("transmission"), axis="X", parent=root)
    tag(ds, "transmission", "", "Arbre de transmission", (0, 0, -1.0))

    tank = cyl("fuel__tank", s["tank"], s["tank_r"], s["tank_len"], zone_mat("fuel"), axis="X", verts=32, parent=root)
    tag(tank, "fuel", "", "Réservoir carburant", (0, 1.5 if s["tank"][1] > 0 else -1.5, 0))


# ---------------------------------------------------------------- truck
def build_truck():
    root = bpy.data.objects.new("Truck", None)
    scene.collection.objects.link(root)
    cab_blue = mat("truck_cab", (0.10, 0.28, 0.55), metal=0.3, rough=0.35)
    white = mat("body_white", (0.92, 0.93, 0.94), rough=0.4)
    dark = mat("trim_dark", (0.08, 0.09, 0.1), rough=0.6)
    glass = mat("glass", (0.05, 0.08, 0.12), metal=0.2, rough=0.05)
    chrome = mat("chrome", (0.8, 0.8, 0.82), metal=1, rough=0.2)
    light = mat("headlight", (1, 1, 0.9), emit=(1, 0.95, 0.8))

    # chassis + body (zone "body" = shell, turns transparent in exploded view)
    for side in (-1, 1):
        rail = box(f"body__chassis_rail_{'L' if side > 0 else 'R'}", (0.1, side * 0.45, 0.85), (7.6, 0.14, 0.26), dark, parent=root)
        tag(rail, "body", "", "Châssis")
    cab = box("body__cab", (3.35, 0, 2.05), (1.7, 2.45, 2.0), cab_blue, bevel=0.12, parent=root)
    tag(cab, "body", "", "Cabine", (0.6, 0, 0.6))
    roof = box("body__cab_roof", (3.2, 0, 3.2), (1.3, 2.3, 0.35), cab_blue, bevel=0.12, parent=root)
    tag(roof, "body", "", "Déflecteur", (0.6, 0, 0.9))
    ws = box("body__windshield", (4.21, 0, 2.45), (0.04, 2.2, 0.85), glass, bevel=0.02, parent=root)
    tag(ws, "body", "", "Pare-brise", (0.6, 0, 0.6))
    for side in (-1, 1):
        sw = box(f"body__side_window_{side}", (3.55, side * 1.23, 2.45), (0.8, 0.02, 0.6), glass, bevel=0.01, parent=root)
        tag(sw, "body", "", "Vitre", (0.6, 0, 0.6))
    bumper = box("body__bumper", (4.25, 0, 1.0), (0.18, 2.45, 0.35), dark, bevel=0.04, parent=root)
    tag(bumper, "body", "", "Pare-chocs", (0.8, 0, 0))
    grille = box("body__grille", (4.21, 0, 1.55), (0.04, 1.4, 0.55), chrome, bevel=0.01, parent=root)
    tag(grille, "body", "", "Calandre", (0.8, 0, 0))
    for side in (-1, 1):
        hl = box(f"body__headlight_{side}", (4.23, side * 0.95, 1.3), (0.05, 0.35, 0.18), light, bevel=0.01, parent=root)
        tag(hl, "body", "", "Phare", (0.8, 0, 0))
    cargo = box("body__cargo_box", (-0.75, 0, 2.5), (5.7, 2.5, 2.7), white, bevel=0.06, parent=root)
    tag(cargo, "body", "", "Caisse", (0, 0, 1.8))
    stripe = box("body__cargo_stripe", (-0.75, 0, 1.45), (5.72, 2.52, 0.18), cab_blue, bevel=0.01, parent=root)
    tag(stripe, "body", "", "Bande", (0, 0, 1.8))

    drivetrain(root, {
        "engine": (3.3, 0, 1.35), "engine_size": (1.0, 0.75, 0.65),
        "dpf": (1.9, -0.95, 0.95),
        "radiator": (3.95, 0, 1.45), "radiator_size": (0.08, 1.05, 0.75),
        "water_pump": (3.85, 0.15, 1.05),
        "alternator": (3.6, -0.55, 1.6), "starter": (2.85, 0.5, 1.05),
        "battery": (1.75, -1.05, 1.0), "battery_size": (0.6, 0.35, 0.35),
        "gearbox": (2.45, 0, 1.15), "gearbox_size": (0.65, 0.5, 0.5),
        "driveshaft_x": (2.1, -2.3), "driveshaft_z": 0.95,
        "tank": (0.6, 1.0, 1.0), "tank_r": 0.36, "tank_len": 1.5,
    })
    rim = mat("rim_truck", (0.75, 0.76, 0.78), metal=1, rough=0.25)
    for name, x in (("F", 3.25), ("R1", -1.55), ("R2", -2.85)):
        for side, s in ((1, "L"), (-1, "R")):
            wheel(root, f"{name}{s}", x, side * 1.08, 0.52, 0.36, rim, side)
    return root


# ---------------------------------------------------------------- ambulance
def build_ambulance():
    root = bpy.data.objects.new("Ambulance", None)
    scene.collection.objects.link(root)
    white = mat("amb_white", (0.95, 0.95, 0.96), rough=0.35)
    red = mat("amb_red", (0.80, 0.05, 0.06), rough=0.4)
    yellow = mat("amb_yellow", (0.95, 0.8, 0.05), rough=0.4)
    dark = mat("trim_dark", (0.08, 0.09, 0.1), rough=0.6)
    glass = mat("glass", (0.05, 0.08, 0.12), metal=0.2, rough=0.05)
    light = mat("headlight", (1, 1, 0.9), emit=(1, 0.95, 0.8))
    beacon_r = mat("beacon_red", (1, 0.05, 0.05), emit=(1, 0.05, 0.05))
    beacon_b = mat("beacon_blue", (0.05, 0.2, 1), emit=(0.05, 0.2, 1))

    for side in (-1, 1):
        rail = box(f"body__chassis_rail_{'L' if side > 0 else 'R'}", (0.1, side * 0.4, 0.5), (5.6, 0.1, 0.16), dark, parent=root)
        tag(rail, "body", "", "Châssis")
    body = box("body__patient_box", (-0.95, 0, 1.65), (3.9, 2.05, 2.1), white, bevel=0.08, parent=root)
    tag(body, "body", "", "Cellule sanitaire", (0, 0, 1.6))
    cab = box("body__cab", (1.75, 0, 1.45), (1.5, 2.0, 1.7), white, bevel=0.12, parent=root)
    tag(cab, "body", "", "Cabine", (0.6, 0, 0.8))
    hood = box("body__hood", (2.75, 0, 1.0), (0.75, 1.95, 0.8), white, bevel=0.12, parent=root)
    tag(hood, "body", "", "Capot", (0.9, 0, 0.9))
    ws = box("body__windshield", (2.51, 0, 1.85), (0.04, 1.85, 0.7), glass, bevel=0.01, parent=root)
    tag(ws, "body", "", "Pare-brise", (0.6, 0, 0.8))
    for side in (-1, 1):
        sw = box(f"body__side_window_{side}", (1.65, side * 1.01, 1.8), (0.75, 0.02, 0.5), glass, bevel=0.01, parent=root)
        tag(sw, "body", "", "Vitre", (0.6, 0, 0.8))
    stripe = box("body__red_stripe", (0.2, 0, 1.25), (6.15, 2.08, 0.22), red, bevel=0.01, parent=root)
    tag(stripe, "body", "", "Bande rouge", (0, 0, 1.6))
    chev = box("body__rear_chevrons", (-2.92, 0, 1.2), (0.03, 1.9, 0.5), yellow, bevel=0.005, parent=root)
    tag(chev, "body", "", "Chevrons", (-0.6, 0, 1.6))
    cross_v = box("body__cross_v", (-0.95, 1.035, 2.05), (0.18, 0.02, 0.6), red, bevel=0.005, parent=root)
    cross_h = box("body__cross_h", (-0.95, 1.035, 2.05), (0.6, 0.02, 0.18), red, bevel=0.005, parent=root)
    tag(join("body__cross_L", [cross_v, cross_h]), "body", "", "Croix", (0, 0, 1.6))
    cross_v = box("body__cross_v2", (-0.95, -1.035, 2.05), (0.18, 0.02, 0.6), red, bevel=0.005, parent=root)
    cross_h = box("body__cross_h2", (-0.95, -1.035, 2.05), (0.6, 0.02, 0.18), red, bevel=0.005, parent=root)
    tag(join("body__cross_R", [cross_v, cross_h]), "body", "", "Croix", (0, 0, 1.6))
    bar = box("body__lightbar", (1.7, 0, 2.38), (0.3, 1.5, 0.12), dark, bevel=0.02, parent=root)
    tag(bar, "body", "", "Rampe lumineuse", (0.6, 0, 1.2))
    for i, (yy, m) in enumerate(((0.45, beacon_r), (-0.45, beacon_b))):
        bcn = box(f"body__beacon_{i}", (1.7, yy, 2.48), (0.26, 0.55, 0.1), m, bevel=0.02, parent=root)
        tag(bcn, "body", "", "Gyrophare", (0.6, 0, 1.2))
    bumper = box("body__bumper", (3.15, 0, 0.62), (0.15, 2.0, 0.3), dark, bevel=0.04, parent=root)
    tag(bumper, "body", "", "Pare-chocs", (0.8, 0, 0))
    for side in (-1, 1):
        hl = box(f"body__headlight_{side}", (3.13, side * 0.72, 1.05), (0.05, 0.32, 0.16), light, bevel=0.01, parent=root)
        tag(hl, "body", "", "Phare", (0.8, 0, 0))

    drivetrain(root, {
        "engine": (2.6, 0, 0.95), "engine_size": (0.7, 0.6, 0.45),
        "dpf": (0.9, -0.55, 0.42),
        "radiator": (3.05, 0, 1.0), "radiator_size": (0.06, 1.0, 0.45),
        "water_pump": (2.98, 0.15, 0.8),
        "alternator": (2.8, -0.48, 1.12), "starter": (2.2, 0.42, 0.75),
        "battery": (1.75, -0.6, 0.75), "battery_size": (0.4, 0.25, 0.25),
        "gearbox": (1.95, 0, 0.72), "gearbox_size": (0.5, 0.38, 0.36),
        "driveshaft_x": (1.7, -1.5), "driveshaft_z": 0.55,
        "tank": (-0.6, 0.55, 0.52), "tank_r": 0.22, "tank_len": 0.9,
    })
    rim = mat("rim_amb", (0.85, 0.86, 0.88), metal=1, rough=0.25)
    for name, x in (("F", 2.25), ("R", -1.7)):
        for side, s in ((1, "L"), (-1, "R")):
            wheel(root, f"{name}{s}", x, side * 0.92, 0.38, 0.25, rim, side)
    return root


# ---------------------------------------------------------------- road tile
def build_road(length=60.0):
    """Straight 2-lane road along X. Vehicles drive +X in the right lane (y = 0); tile it along X."""
    root = bpy.data.objects.new("Road", None)
    scene.collection.objects.link(root)
    asphalt = mat("asphalt", (0.06, 0.065, 0.07), rough=0.9)
    paint = mat("road_paint", (0.92, 0.92, 0.88), rough=0.6)
    shoulder = mat("shoulder", (0.55, 0.45, 0.32), rough=1.0)  # Moroccan red-sand verge
    box("road__asphalt", (0, 1.75, 0.0), (length, 7.5, 0.04), asphalt, bevel=0, parent=root)
    for y in (-2.0, 5.5):
        box(f"road__edge_{y}", (0, y, 0.025), (length, 0.15, 0.01), paint, bevel=0, parent=root)
        box(f"road__shoulder_{y}", (0, y + (-1.6 if y < 0 else 1.6), -0.01), (length, 3.0, 0.03), shoulder, bevel=0, parent=root)
    dash, gap = 3.0, 6.0
    x = -length / 2 + dash / 2
    i = 0
    while x < length / 2:
        box(f"road__dash_{i}", (x, 1.75, 0.025), (dash, 0.15, 0.01), paint, bevel=0, parent=root)
        x += dash + gap
        i += 1
    for o in children(root):
        tag(o, "road")
    return root


# ---------------------------------------------------------------- animation clips (glTF animations)
# Each clip = one NLA track name, exported as one glTF animation:
#   drive   (1 s loop): wheels + brake discs roll forward, body bobs slightly
#   explode (1 s):      every part slides from rest to rest + explode_dir (play reversed to reassemble)
#   siren   (0.5 s loop, ambulance): beacons pulse alternately
FPS = 24


def _set_interp(kind):
    bpy.context.preferences.edit.keyframe_new_interpolation_type = kind


def _push(o, track):
    ad = o.animation_data
    act = ad.action
    act.name = f"{track}__{o.name}"
    tr = ad.nla_tracks.new()
    tr.name = track
    tr.strips.new(track, 1, act)
    ad.action = None


def add_clips(root):
    scene.render.fps = FPS
    kids = children(root)
    base = {o.name: tuple(o.location) for o in kids}

    _set_interp("LINEAR")
    for o in kids:
        rolls = o["zone"] == "tires" or o.name.startswith("brakes__disc")
        bobs = o["zone"] == "body" and "chassis" not in o.name
        if not (rolls or bobs):
            continue
        for i, f in enumerate(range(1, FPS + 2, FPS // 4)):
            if rolls:  # +Y spin rolls the wheel toward +X
                o.rotation_euler = (0, i * math.pi / 2, 0)
                o.keyframe_insert("rotation_euler", frame=f)
            if bobs:
                o.location = (*base[o.name][:2], base[o.name][2] + (0.015 if i % 2 else 0))
                o.keyframe_insert("location", frame=f)
        o.rotation_euler, o.location = (0, 0, 0), base[o.name]
        _push(o, "drive")

    _set_interp("BEZIER")
    for o in kids:
        x, y, z = o["explode_dir"]
        if (x, y, z) == (0, 0, 0):
            continue
        bx, by, bz = base[o.name]
        o.location = (bx, by, bz)
        o.keyframe_insert("location", frame=1)
        o.location = (bx + x, by - z, bz + y)  # three.js dir -> Blender space
        o.keyframe_insert("location", frame=FPS + 1)
        o.location = base[o.name]
        _push(o, "explode")

    beacons = [o for o in kids if o.name.startswith("body__beacon")]
    for i, o in enumerate(beacons):
        for f, s in ((1, 1.0), (4, 1.0 + 0.35 * (i == 0)), (7, 1.0 + 0.35 * (i == 1)), (13, 1.0)):
            o.scale = (s, s, s)
            o.keyframe_insert("scale", frame=f)
        o.scale = (1, 1, 1)
        _push(o, "siren")


# ---------------------------------------------------------------- export + previews
def children(root):
    return [o for o in bpy.data.objects if o.parent == root]


def export(root, filename, animations=True):
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for o in children(root):
        o.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, filename), export_format="GLB", use_selection=True,
                              export_extras=True, export_yup=True, export_apply=True,
                              export_animations=animations, export_animation_mode="NLA_TRACKS")


def setup_render():
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    scene.render.resolution_x, scene.render.resolution_y = 1280, 800
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("world")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.03, 0.04, 0.06, 1)
    bg.inputs["Strength"].default_value = 0.6
    scene.world = world
    for name, rot, energy in (("key", (50, 0, 35), 4.0), ("fill", (60, 0, -140), 1.5), ("rim", (20, 0, 180), 2.0)):
        ld = bpy.data.lights.new(name, "SUN")
        ld.energy = energy
        lo = bpy.data.objects.new(name, ld)
        lo.rotation_euler = [math.radians(a) for a in rot]
        scene.collection.objects.link(lo)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "floor"
    floor.data.materials.append(mat("floor", (0.07, 0.08, 0.1), rough=0.8))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam, floor


def aim(cam, target, dist, az_deg=-35, el_deg=22):
    az, el = math.radians(az_deg), math.radians(el_deg)
    tx, ty, tz = target
    cam.location = (tx + dist * math.cos(el) * math.cos(az), ty + dist * math.cos(el) * math.sin(az), tz + dist * math.sin(el))
    d = (tx - cam.location[0], ty - cam.location[1], tz - cam.location[2])
    cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)


def render(path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def explode(root, factor):
    """Blender-space offset = inverse of to_three()."""
    for o in children(root):
        x, y, z = o["explode_dir"]
        o.location = (o.get("_base", o.location)[0] + x * factor,
                      o.get("_base", o.location)[1] - z * factor,
                      o.get("_base", o.location)[2] + y * factor)


def main():
    truck = build_truck()
    amb = build_ambulance()
    road = build_road()
    add_clips(truck)
    add_clips(amb)
    scene.frame_set(1)
    export(truck, "truck.glb")
    export(amb, "ambulance.glb")
    export(road, "road.glb", animations=False)
    amb.location = (0, 6, 0)  # side by side in the .blend, on the road
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "vehicles.blend"))
    amb.location = (0, 0, 0)

    for o in [*children(truck), *children(amb)]:  # previews use plain transforms
        o.animation_data_clear()
    scene.frame_set(1)
    for o in [road, *children(road)]:
        o.hide_render = True
    cam, floor = setup_render()
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 16
    for root, other, name, dist in ((truck, amb, "truck", 13), (amb, truck, "ambulance", 10)):
        other.hide_render = True
        for o in children(other):
            o.hide_render = True
        for o in children(root):
            o["_base"] = list(o.location)
        aim(cam, (0, 0, 1.4), dist)
        render(os.path.join(OUT, f"preview_{name}.png"))
        shell = [o for o in children(root) if o["zone"] == "body" and "chassis" not in o.name]
        for o in shell:  # the frontend fades the shell; the preview just hides it
            o.hide_render = True
        explode(root, 0.9)
        aim(cam, (0, 0, 1.4), dist * 1.15)
        render(os.path.join(OUT, f"preview_{name}_exploded.png"))
        explode(root, 0.0)
        for o in shell:
            o.hide_render = False
        for o in children(root):
            del o["_base"]
        other.hide_render = False
        for o in children(other):
            o.hide_render = False

    print("DONE", OUT)


if __name__ == "__main__":  # importable by animate_scene.py without rebuilding everything
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
