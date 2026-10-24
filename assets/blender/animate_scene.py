"""Showcase animation: a vehicle drives a curved road, slows to a stop in its lane, the body turns
see-through and the camera eases in on the broken part, glowing red. Calm on purpose: no explosion,
no blinking, no text.

  blender.exe -b --factory-startup --python assets/blender/animate_scene.py -- truck      [--preview]
  blender.exe -b --factory-startup --python assets/blender/animate_scene.py -- ambulance  [--preview]

Writes assets/models/anim_<vehicle>.blend and anim_<vehicle>.mp4 (--preview: 5 still frames only).

Motion is computed, not hand-keyed: the vehicle follows its lane at a smooth speed profile
(cruise -> eased braking -> stop), heading comes from the path, front wheels steer from path
curvature, wheels spin from distance travelled, and the sprung body pitches/rolls through a
spring-damper driven by longitudinal/lateral acceleration.
"""
import bisect
import math
import os
import random
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_vehicles as bv  # noqa: E402  (resets the scene on import)
import engine as real_engine  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
VEHICLE = next((a for a in ARGS if a in ("truck", "ambulance")), "truck")
PREVIEW = "--preview" in ARGS
OUT = bv.OUT
FPS = 24
scene = bpy.context.scene

CFG = {
    # side = which side the camera swings to (+1 left, -1 right): the side the broken part is on
    # view = close-up direction from the part, in the vehicle frame (+x front, +y left, +z up)
    "truck": {"v0": 15.0, "part": "P-WPUMP", "cam": 1.0, "side": 1, "close": 3.6, "view": (1.5, 0.75, 1.2)},
    "ambulance": {"v0": 18.0, "part": "P-ALT", "cam": 0.8, "side": -1, "close": 3.0, "view": (0.8, -1.0, 1.4)},
}[VEHICLE]

# timeline (frames)
F_BRAKE, F_STOP = 96, 192      # eased braking, stays in lane
F_XRAY0, F_XRAY1 = 200, 250    # body turns see-through, broken part lights up
F_PUSH0, F_PUSH1 = 196, 300    # camera eases in on the part
F_END = 340

rng = random.Random(7)


def smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def smootherstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (6 * x - 15) + 10)


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


# ---------------------------------------------------------------- road centreline
X0, X1 = -80.0, 260.0


def _y(x):  # gentle S-bend
    return 9.0 * math.tanh((x - 10.0) / 30.0)


_xs, _ys, _ss = [], [], []
_x, _s = X0, 0.0
while _x <= X1:
    y = _y(_x)
    if _xs:
        _s += math.hypot(_x - _xs[-1], y - _ys[-1])
    _xs.append(_x)
    _ys.append(y)
    _ss.append(_s)
    _x += 0.1
ROAD_LEN = _ss[-1]


def path(s):
    """(x, y, tx, ty) at arc length s."""
    s = min(max(s, 0.0), ROAD_LEN - 0.2)
    i = max(1, bisect.bisect_left(_ss, s))
    k = (s - _ss[i - 1]) / max(1e-9, _ss[i] - _ss[i - 1])
    x = _xs[i - 1] + (_xs[i] - _xs[i - 1]) * k
    y = _ys[i - 1] + (_ys[i] - _ys[i - 1]) * k
    tx, ty = _xs[i] - _xs[i - 1], _ys[i] - _ys[i - 1]
    n = math.hypot(tx, ty)
    return x, y, tx / n, ty / n


def offset_point(s, d):
    x, y, tx, ty = path(s)
    return x - ty * d, y + tx * d  # left normal = (-ty, tx)


# ---------------------------------------------------------------- vehicle kinematics
V0 = CFG["v0"]
S0 = 22.0
LANE = -1.875  # centre of the right lane
TB, T_BRAKE = (F_BRAKE - 1) / FPS, (F_STOP - F_BRAKE) / FPS


def kin(t):
    """(s, v, a) at time t (s). Braking follows a half-cosine so deceleration starts and ends at 0."""
    if t <= TB:
        return S0 + V0 * t, V0, 0.0
    if t <= TB + T_BRAKE:
        tau = t - TB
        w = math.pi / T_BRAKE
        s = S0 + V0 * TB + V0 * (tau / 2 + math.sin(w * tau) / (2 * w))
        v = V0 * (1 + math.cos(w * tau)) / 2
        a = -V0 * w * math.sin(w * tau) / 2
        return s, v, a
    return S0 + V0 * TB + V0 * T_BRAKE / 2, 0.0, 0.0


def veh_xy(t):
    return offset_point(kin(t)[0], LANE)


def heading(t, last):
    h = 0.03
    (x0, y0), (x1, y1) = veh_xy(t - h), veh_xy(t + h)
    if math.hypot(x1 - x0, y1 - y0) < 0.02:
        return last
    return math.atan2(y1 - y0, x1 - x0)


# ---------------------------------------------------------------- build world
def mat_noise(name, c1, c2, scale, rough=0.9):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 8
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    return m


def strip(name, segments, off0, off1, z, material, step=1.0):
    """Quad strip following the road between lateral offsets off0..off1 for each (s0, s1) segment."""
    verts, faces = [], []
    for s0, s1 in segments:
        n = max(1, int((s1 - s0) / step))
        base = len(verts)
        for i in range(n + 1):
            s = s0 + (s1 - s0) * i / n
            for d in (off0, off1):
                x, y = offset_point(s, d)
                verts.append((x, y, z))
        for i in range(n):
            a = base + 2 * i
            faces.append((a, a + 2, a + 3, a + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(material)
    scene.collection.objects.link(o)
    return o


def build_world():
    asphalt = mat_noise("asphalt", (0.035, 0.037, 0.04), (0.07, 0.072, 0.075), 60, rough=0.85)
    gravel = mat_noise("gravel", (0.33, 0.26, 0.19), (0.45, 0.37, 0.27), 25)
    ground = mat_noise("ground", (0.42, 0.30, 0.20), (0.58, 0.45, 0.31), 0.6, rough=1.0)
    paint = bv.mat("lane_paint", (0.9, 0.9, 0.86), rough=0.5)
    full = [(0, ROAD_LEN)]
    strip("road", full, -3.75, 3.75, 0.0, asphalt)
    strip("shoulder_R", full, -7.0, -3.75, -0.01, gravel)
    strip("shoulder_L", full, 3.75, 7.0, -0.01, gravel)
    strip("edge_R", full, -3.65, -3.5, 0.004, paint)
    strip("edge_L", full, 3.5, 3.65, 0.004, paint)
    dashes = [(s, s + 3.0) for s in [i * 9.0 for i in range(int(ROAD_LEN / 9))]]
    strip("centre_dashes", dashes, -0.075, 0.075, 0.004, paint, step=0.5)

    bpy.ops.mesh.primitive_plane_add(size=1200, location=(90, 0, -0.03))
    bpy.context.active_object.name = "ground"
    bpy.context.active_object.data.materials.append(ground)

    post_mat = bv.mat("post_white", (0.92, 0.92, 0.9), rough=0.4)
    refl = bv.mat("reflector", (0.9, 0.1, 0.05), emit=(0.6, 0.05, 0.02))
    for s in range(0, int(ROAD_LEN), 20):
        for d in (-7.3, 7.3):
            x, y = offset_point(s, d)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0.5))
            p = bpy.context.active_object
            p.scale = (0.12, 0.12, 1.0)
            p.data.materials.append(post_mat)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0.9))
            r = bpy.context.active_object
            r.scale = (0.13, 0.13, 0.12)
            r.data.materials.append(refl)

    bush = bv.mat("bush", (0.17, 0.24, 0.10), rough=0.9)
    rock = bv.mat("rock", (0.36, 0.29, 0.22), rough=0.95)
    for _ in range(260):
        s = rng.uniform(0, ROAD_LEN)
        d = rng.choice((-1, 1)) * rng.uniform(9, 60)
        x, y = offset_point(s, d)
        if rng.random() < 0.7:
            sc = rng.uniform(0.5, 1.8)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1, location=(x, y, sc * 0.45))
            o = bpy.context.active_object
            o.scale = (sc, sc * rng.uniform(0.8, 1.2), sc * 0.75)
            o.data.materials.append(bush)
        else:
            sc = rng.uniform(0.3, 1.1)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1, location=(x, y, sc * 0.2))
            o = bpy.context.active_object
            o.scale = (sc * 1.3, sc, sc * 0.6)
            o.rotation_euler = (0, 0, rng.uniform(0, 6.28))
            o.data.materials.append(rock)

    # sky: vertical gradient (EEVEE-safe), warm sun
    world = bpy.data.worlds.new("sky")
    nt = world.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.85, 0.80, 0.72, 1)   # hazy horizon
    ramp.color_ramp.elements[1].position = 0.45
    ramp.color_ramp.elements[1].color = (0.25, 0.45, 0.80, 1)   # zenith blue
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 4.0
    sun.data.color = (1.0, 0.94, 0.85)
    sun.data.angle = math.radians(1.5)
    sun.rotation_euler = (math.radians(48), 0, math.radians(-35))
    scene.collection.objects.link(sun)


# ---------------------------------------------------------------- vehicle rig
def rig_vehicle():
    root = bv.build_truck() if VEHICLE == "truck" else bv.build_ambulance()
    real_engine.install_engine(root, VEHICLE, bv.tag)
    for o in [c for c in bv.children(root) if c.name.startswith("cooling__radiator")]:
        bpy.data.objects.remove(o, do_unlink=True)  # placeholder panel would sit between camera and pump
    kids = bv.children(root)
    bpy.context.view_layer.update()
    tires = [o for o in kids if o["zone"] == "tires"]
    radius = max(o.dimensions.z for o in tires) / 2
    front_x = max(o.location.x for o in tires)
    rear = [o.location.x for o in tires if o.location.x < 0]
    wheelbase = front_x - sum(rear) / len(rear)

    unsprung = [o for o in kids if o["zone"] in ("tires", "brakes")]
    sprung = bpy.data.objects.new("sprung", None)
    scene.collection.objects.link(sprung)
    sprung.parent = root
    sprung.location = (0.5, 0, 1.0)
    bpy.context.view_layer.update()
    for o in kids:
        if o not in unsprung:
            mw = o.matrix_world.copy()
            o.parent = sprung
            o.matrix_parent_inverse = sprung.matrix_world.inverted()
            o.matrix_world = mw
    return root, sprung, kids, radius, wheelbase


# ---------------------------------------------------------------- animation
def key(o, path_, f):
    o.keyframe_insert(path_, frame=f)


def drive(root, sprung, kids, radius, wheelbase):
    wheels = [o for o in kids if o["zone"] == "tires" or o.name.startswith("brakes__disc")]
    calipers = [o for o in kids if o.name.startswith("brakes__caliper")]
    is_front = lambda o: "_F" in o.name  # noqa: E731

    bv._set_interp("LINEAR")
    wn, zeta = 2 * math.pi * 1.3, 0.55  # well-damped suspension: one soft rebound, no wobble
    p = pr = r = rr = 0.0
    psi = heading(0.0, 0.0)
    s_prev = kin(0.0)[0]
    track, steer = [], 0.0
    for f in range(1, F_END + 1):
        t = (f - 1) / FPS
        s, v, a = kin(t)
        psi_new = heading(t, psi)
        ds = max(1e-3, abs(s - s_prev))
        kappa = (psi_new - psi) / ds if v > 0.3 else 0.0
        psi, s_prev = psi_new, s
        if v > 0.3:
            steer = math.atan(wheelbase * kappa)
        a_lat = v * v * kappa
        for _ in range(8):
            dt = 1 / FPS / 8
            pt, rt = 0.0035 * (-a), max(-0.04, min(0.04, 0.006 * a_lat))
            pr += (-wn * wn * (p - pt) - 2 * zeta * wn * pr) * dt
            p += pr * dt
            rr += (-wn * wn * (r - rt) - 2 * zeta * wn * rr) * dt
            r += rr * dt
        bump = (v / V0) * (0.005 * math.sin(t * 9.1) + 0.003 * math.sin(t * 19.7 + 1.3))
        x, y = veh_xy(t)
        track.append((x, y, psi))

        root.location = (x, y, 0.0)
        root.rotation_euler = (0, 0, psi)
        key(root, "location", f)
        key(root, "rotation_euler", f)
        sprung.location = (0.5, 0, 1.0 + bump)
        sprung.rotation_euler = (r, p, 0)
        key(sprung, "location", f)
        key(sprung, "rotation_euler", f)
        spin = (s - S0) / radius
        for o in wheels:
            o.rotation_euler = (0, spin, steer if is_front(o) else 0)
            key(o, "rotation_euler", f)
        for o in calipers:
            o.rotation_euler = (0, 0, steer if is_front(o) else 0)
            key(o, "rotation_euler", f)
    return track


def xray(kids):
    """Body fades to a glass ghost; mechanics go neutral grey; the broken part glows red."""
    failing = next(o for o in kids if o.get("part_id") == CFG["part"])
    shell = [o for o in kids if o["zone"] == "body" and "chassis" not in o.name]

    grey = bv.mat("internal_grey", (0.55, 0.57, 0.6), metal=0.5, rough=0.4)
    if hasattr(grey, "surface_render_method"):
        grey.surface_render_method = "BLENDED"
    g_alpha = next(n for n in grey.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Alpha"]
    g_alpha.default_value = 1.0
    g_alpha.keyframe_insert("default_value", frame=F_XRAY0)
    g_alpha.default_value = 0.35  # mechanics turn semi-see-through so the red part shows through them
    g_alpha.keyframe_insert("default_value", frame=F_XRAY1)
    for o in kids:  # the real engine stays solid steel: it is what the viewer should read
        if o is failing or o in shell or o["zone"] in ("tires", "body") or o.name.startswith("engine__"):
            continue
        for slot in o.material_slots:
            slot.material = grey

    bv._set_interp("BEZIER")
    copies = {}
    for o in shell:
        for slot in o.material_slots:
            src = slot.material
            if src.name not in copies:
                c = src.copy()
                c.name = f"xray_{src.name}"
                copies[src.name] = c
            slot.material = copies[src.name]
    for m in copies.values():
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
        if hasattr(m, "use_transparency_overlap"):
            m.use_transparency_overlap = False
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        alpha = bsdf.inputs["Alpha"]
        alpha.default_value = 1.0
        alpha.keyframe_insert("default_value", frame=F_XRAY0)
        # red paint / beacons vanish completely so the only red on screen is the broken part
        alpha.default_value = 0.0 if any(k in m.name for k in ("red", "beacon", "headlight")) else 0.1
        alpha.keyframe_insert("default_value", frame=F_XRAY1)
        em = bsdf.inputs["Emission Strength"]  # lights/beacons dim with the body
        if em.default_value > 0:
            em.keyframe_insert("default_value", frame=F_XRAY0)
            em.default_value = 0.0
            em.keyframe_insert("default_value", frame=F_XRAY1)

    fm = failing.active_material.copy()
    fm.name = "failing_part"
    failing.active_material = fm
    bsdf = next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.75, 0.04, 0.03, 1)
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.06, 0.03, 1)
    em = bsdf.inputs["Emission Strength"]
    em.default_value = 0.0
    em.keyframe_insert("default_value", frame=F_XRAY0 + 10)
    em.default_value = 3.0
    em.keyframe_insert("default_value", frame=F_XRAY1 + 10)
    f, hi = F_XRAY1 + 10, False  # slow breathing glow, no flashing
    while f + 30 <= F_END:
        f += 30
        em.default_value = 3.0 if hi else 1.8
        em.keyframe_insert("default_value", frame=f)
        hi = not hi

    # soft red light on the part so it reads even when partly hidden behind other parts
    glow = bpy.data.objects.new("failing_glow", bpy.data.lights.new("failing_glow", "POINT"))
    scene.collection.objects.link(glow)
    glow.parent = failing
    glow.data.color = (1.0, 0.12, 0.06)
    glow.data.shadow_soft_size = 0.3
    glow.data.energy = 0.0
    glow.data.keyframe_insert("energy", frame=F_XRAY0 + 10)
    glow.data.energy = 60.0 if VEHICLE == "truck" else 12.0  # smaller engine bay -> much less light
    glow.data.keyframe_insert("energy", frame=F_XRAY1 + 10)
    return failing


def camera(track, failing):
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 38
    cam.data.clip_end = 2000
    tgt = bpy.data.objects.new("cam_target", None)
    scene.collection.objects.link(tgt)
    c = cam.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = tgt
    cam.data.dof.aperture_fstop = 5.6

    scene.frame_set(F_END)
    part = tuple(failing.matrix_world.translation)
    k = CFG["cam"]

    # chase -> 3/4 front-right view: swing around the vehicle in polar coordinates of its frame
    a_chase = math.atan2(5, -15)
    a_side = math.atan2(10, 9) if CFG["side"] > 0 else math.atan2(-10, 9) + 2 * math.pi
    r_chase, r_side = math.hypot(5, 15), math.hypot(9, 10)

    bv._set_interp("LINEAR")
    cpos = tpos = None
    for f in range(1, F_END + 1):
        x, y, psi = track[f - 1]
        w = smootherstep((f - 80) / (190 - 80))
        ang = psi + a_chase + (a_side - a_chase) * w
        rad = (r_chase + (r_side - r_chase) * w) * k
        orbit = (x + rad * math.cos(ang), y + rad * math.sin(ang), (4.2 - 1.0 * w) * k)
        look = (x + math.cos(psi) * 0.6, y + math.sin(psi) * 0.6, 1.4)

        # push in on the broken part from CFG["view"], CFG["close"] metres away
        e = smootherstep((f - F_PUSH0) / (F_PUSH1 - F_PUSH0))
        if e > 0:
            vx, vy, vz = CFG["view"]
            n = math.sqrt(vx * vx + vy * vy + vz * vz)
            vx, vy, vz = vx / n, vy / n, vz / n
            wx, wy = vx * math.cos(psi) - vy * math.sin(psi), vx * math.sin(psi) + vy * math.cos(psi)
            d = CFG["close"]
            close = (part[0] + wx * d, part[1] + wy * d, part[2] + vz * d)
            orbit = lerp(orbit, close, e)
            look = lerp(look, part, e)
        cpos = orbit if cpos is None else lerp(cpos, orbit, 0.15)
        tpos = look if tpos is None else lerp(tpos, look, 0.25)
        cam.location = cpos
        tgt.location = tpos
        key(cam, "location", f)
        key(tgt, "location", f)
        cam.data.lens = 38 + 12 * e
        cam.data.keyframe_insert("lens", frame=f)


def render_setup(name):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, F_END
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5
    ee = scene.eevee
    ee.taa_render_samples = 32
    for attr, val in (("use_raytracing", True), ("use_shadows", True)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    scene.view_settings.view_transform = "AgX"
    looks = [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["look"].enum_items]
    scene.view_settings.look = "AgX - Medium High Contrast" if "AgX - Medium High Contrast" in looks else "None"
    try:
        scene.render.image_settings.media_type = "VIDEO"
    except (AttributeError, TypeError):
        pass
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format, scene.render.ffmpeg.codec = "MPEG4", "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.filepath = os.path.join(OUT, f"anim_{name}.mp4")


def main():
    build_world()
    root, sprung, kids, radius, wheelbase = rig_vehicle()
    track = drive(root, sprung, kids, radius, wheelbase)
    failing = xray(kids)
    camera(track, failing)
    render_setup(VEHICLE)
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"anim_{VEHICLE}.blend"))
    if PREVIEW:
        scene.render.image_settings.media_type = "IMAGE"
        scene.render.image_settings.file_format = "PNG"
        for f in (40, 150, 200, 260, 330):
            scene.frame_set(f)
            scene.render.filepath = os.path.join(OUT, f"_check_{VEHICLE}_{f}.png")
            bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)
    print("DONE", VEHICLE)


try:
    main()
except Exception:
    import traceback

    traceback.print_exc()
    sys.exit(1)
