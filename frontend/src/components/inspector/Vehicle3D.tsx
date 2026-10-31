import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { ContactShadows, Grid, OrbitControls, Sparkles, useGLTF } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import * as THREE from "three";
import { MeshSurfaceSampler } from "three/examples/jsm/math/MeshSurfaceSampler.js";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { VehicleType, Zone } from "@shared/types";
import type { VehicleHealth, ZoneStatus } from "@/api";

export interface PickedPart { zone: Zone; part_id: string; label_fr: string }

interface Props {
  type: VehicleType;
  health: VehicleHealth | undefined;
  failedPartId: string | null;
  failedPartName: string | null;
  exploded: boolean;
  insetX: number; // px the scene centre shifts right to stay clear of the side panels
  selected: PickedPart | null;
  onPick: (p: PickedPart | null) => void;
  vehicleKey: string;
}

const STATUS_HEX: Record<ZoneStatus, THREE.Color> = {
  ok: new THREE.Color("#64748B"),
  warn: new THREE.Color("#F59E0B"),
  fail: new THREE.Color("#EF4444"),
};
const CYAN = new THREE.Color("#22D3EE");
const EXPLODE_SCALE = 1.15;

interface PartRec {
  node: THREE.Object3D;
  zone: Zone | "body";
  partId: string;
  label: string;
  base: THREE.Vector3;
  dir: THREE.Vector3;
  mats: { m: THREE.MeshStandardMaterial; color0: THREE.Color; emissive0: THREE.Color; ei0: number }[];
  edges?: THREE.LineSegments;
}

// ---------- particle shader: points fly in from a scattered cloud and settle on the surfaces ----------

const pointsMaterial = () =>
  new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uProgress: { value: 0 },
      uTime: { value: 0 },
      uOpacity: { value: 1 },
      uColor: { value: new THREE.Color("#7DE8F7") },
      uSize: { value: 2.2 },
    },
    vertexShader: /* glsl */ `
      attribute vec3 aStart;
      attribute float aDelay;
      uniform float uProgress; uniform float uTime; uniform float uSize;
      varying float vFade;
      float easeOutExpo(float x) { return x >= 1.0 ? 1.0 : 1.0 - pow(2.0, -10.0 * x); }
      void main() {
        float t = clamp((uProgress - aDelay * 0.45) / 0.55, 0.0, 1.0);
        float e = easeOutExpo(t);
        vec3 p = mix(aStart, position, e);
        p += 0.012 * sin(uTime * 2.0 + aDelay * 40.0) * (1.0 - e * 0.7);
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = uSize * (8.0 / -mv.z) * (1.6 - e * 0.6);
        vFade = 0.35 + 0.65 * e;
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor; uniform float uOpacity;
      varying float vFade;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        if (d > 0.5) discard;
        gl_FragColor = vec4(uColor, smoothstep(0.5, 0.0, d) * uOpacity * vFade);
      }`,
  });

function buildPoints(mesh: THREE.Mesh, count: number, mat: THREE.ShaderMaterial) {
  const sampler = new MeshSurfaceSampler(mesh).build();
  const pos = new Float32Array(count * 3);
  const start = new Float32Array(count * 3);
  const delay = new Float32Array(count);
  const p = new THREE.Vector3();
  const inv = new THREE.Matrix4().copy(mesh.matrixWorld).invert();
  for (let i = 0; i < count; i++) {
    sampler.sample(p);
    pos.set([p.x, p.y, p.z], i * 3);
    // Start somewhere in a wide shell around the vehicle (world space), expressed in mesh space.
    const r = 7 + Math.random() * 9;
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    const s = new THREE.Vector3(r * Math.sin(ph) * Math.cos(th), Math.abs(r * Math.cos(ph)) * 0.6 + 1, r * Math.sin(ph) * Math.sin(th)).applyMatrix4(inv);
    start.set([s.x, s.y, s.z], i * 3);
    delay[i] = Math.random();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("aStart", new THREE.BufferAttribute(start, 3));
  g.setAttribute("aDelay", new THREE.BufferAttribute(delay, 1));
  const pts = new THREE.Points(g, mat);
  pts.frustumCulled = false;
  pts.raycast = () => {};
  return pts;
}

function area(mesh: THREE.Mesh) {
  const g = mesh.geometry;
  g.computeBoundingBox();
  const s = new THREE.Vector3();
  g.boundingBox!.getSize(s);
  s.multiply(mesh.getWorldScale(new THREE.Vector3()));
  return 2 * (s.x * s.y + s.y * s.z + s.x * s.z);
}

interface ModelProps extends Props {
  labels: { fail: RefObject<HTMLDivElement | null>; hover: RefObject<HTMLDivElement | null> };
  onFailLabel: (t: string | null) => void;
  onHoverLabel: (t: { text: string; sub: string } | null) => void;
}

interface BuiltVehicle { root: THREE.Object3D; parts: PartRec[]; ptsMat: THREE.ShaderMaterial; center: THREE.Vector3; points: THREE.Points[] }

// Sampling the particles and tracing edges is the slow part: do it once per vehicle type, not on every open.
const built = new Map<VehicleType, BuiltVehicle>();

function buildVehicle(scene: THREE.Object3D): BuiltVehicle {
  const root = scene.clone(true);
  root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root);
  const center = box.getCenter(new THREE.Vector3());
  const ptsMat = pointsMaterial();
  const parts: PartRec[] = [];
  const vehicleRoot = root.children[0] ?? root;
  const meshes: THREE.Mesh[] = [];

  for (const node of vehicleRoot.children) {
    const u = node.userData as { zone?: Zone | "body"; part_id?: string; label_fr?: string; explode_dir?: number[] };
    if (!u.zone) continue;
    const rec: PartRec = {
      node, zone: u.zone, partId: u.part_id ?? "", label: u.label_fr ?? node.name,
      base: node.position.clone(), dir: new THREE.Vector3(...(u.explode_dir ?? [0, 0, 0])), mats: [],
    };
    node.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const list = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const cloned = list.map((m) => {
        const c = (m as THREE.MeshStandardMaterial).clone();
        c.transparent = true;
        c.opacity = 0;
        c.depthWrite = true;
        rec.mats.push({ m: c, color0: c.color.clone(), emissive0: c.emissive?.clone() ?? new THREE.Color(0), ei0: c.emissiveIntensity ?? 1 });
        return c;
      });
      mesh.material = Array.isArray(mesh.material) ? cloned : cloned[0];
      mesh.userData.part = rec;
      meshes.push(mesh);
      if (u.zone === "body") {
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(mesh.geometry, 28),
          new THREE.LineBasicMaterial({ color: CYAN, transparent: true, opacity: 0, depthWrite: false }),
        );
        edges.raycast = () => {};
        mesh.add(edges);
        rec.edges = edges;
      }
    });
    parts.push(rec);
  }

  // Particles spread by surface area
  const areas = meshes.map(area);
  const total = areas.reduce((a, b) => a + b, 0) || 1;
  const points: THREE.Points[] = [];
  meshes.forEach((m, i) => {
    const n = Math.max(20, Math.round((areas[i] / total) * 9000));
    try {
      const pts = buildPoints(m, n, ptsMat);
      m.add(pts);
      points.push(pts);
    } catch { /* degenerate geometry */ }
  });

  return { root, parts, ptsMat, center, points };
}

const tmpColor = new THREE.Color();
const tmpEmissive = new THREE.Color();
const tmpVec = new THREE.Vector3();
const FOCUS_HOME = new THREE.Vector3(0, 1.2, 0);
const LABEL_LIFT = new THREE.Vector3(0, 0.45, 0);

function Model({ type, health, failedPartId, failedPartName, exploded, insetX, selected, onPick, vehicleKey, labels, onFailLabel, onHoverLabel }: ModelProps) {
  const { scene } = useGLTF(`/models/${type}.glb`);
  const [hover, setHover] = useState<PartRec | null>(null);
  const { camera, size } = useThree();
  const controls = useThree((s) => s.controls) as OrbitControlsImpl | null;

  const { root, parts, ptsMat, center, points } = useMemo(() => {
    let b = built.get(type);
    if (!b) built.set(type, (b = buildVehicle(scene)));
    return b;
  }, [type, scene]);

  // Replay the assembly on each vehicle switch.
  const clock = useRef(0);
  useEffect(() => {
    clock.current = 0;
    camera.position.set(15, 8.5, 15);
  }, [vehicleKey, camera]);

  const explode = useRef(0);
  const viewOffset = useRef(0);
  const focus = useRef(new THREE.Vector3(0, 1.2, 0));

  useFrame((state, dt) => {
    clock.current += dt;
    const t = clock.current;
    const progress = Math.min(t / 2.1, 1);
    ptsMat.uniforms.uProgress.value = progress;
    ptsMat.uniforms.uTime.value = state.clock.elapsedTime;
    const solid = THREE.MathUtils.smoothstep(t, 1.3, 2.4); // meshes fade in as particles land
    ptsMat.uniforms.uOpacity.value = THREE.MathUtils.lerp(1, exploded ? 0.5 : 0.22, solid);
    // Once the meshes are solid the particles are only visible in the exploded view: don't draw them otherwise.
    const showPoints = solid < 1 || exploded || explode.current > 0.02;
    if (points[0] && points[0].visible !== showPoints) for (const pts of points) pts.visible = showPoints;

    // Camera glides in during the intro.
    if (t < 2.6) {
      const k = 1 - Math.pow(2, -10 * Math.min(t / 2.6, 1));
      const far = Math.max(1, 1.45 / (size.width / size.height)); // narrow viewports: back off
      camera.position.lerpVectors(new THREE.Vector3(15, 8.5, 15).multiplyScalar(far), new THREE.Vector3(9.5, 4.6, 9.5).multiplyScalar(far), k);
    }

    explode.current = THREE.MathUtils.damp(explode.current, exploded ? 1 : 0, 7.5, dt); // ~600 ms
    const e = explode.current;
    const pulse = 0.5 + 0.5 * Math.sin(state.clock.elapsedTime * 5);

    for (const p of parts) {
      p.node.position.copy(p.base).addScaledVector(p.dir, e * EXPLODE_SCALE);
      const isBody = p.zone === "body";
      const zoneStatus: ZoneStatus = isBody ? "ok" : health?.zones[p.zone as Zone]?.status ?? "ok";
      const exact = !!failedPartId && p.partId === failedPartId;
      const isHover = hover === p;
      const isSel = !!selected && selected.zone === p.zone && (!selected.part_id || selected.part_id === p.partId);
      const opacity = solid * (isBody ? THREE.MathUtils.lerp(1, 0.1, e) : 1);
      const transparent = opacity < 0.999; // opaque meshes sort and depth-test far cheaper

      for (const r of p.mats) {
        r.m.opacity = opacity;
        r.m.transparent = transparent;
        r.m.depthWrite = opacity > 0.6;
        if (isBody) {
          // beacons on the ambulance blink red / blue
          if (p.label === "Gyrophare") r.m.emissiveIntensity = r.ei0 * (0.4 + 2 * (p.node.name.includes("_0") ? pulse : 1 - pulse));
          continue;
        }
        const target = zoneStatus === "ok" ? tmpColor.copy(r.color0).lerp(STATUS_HEX.ok, 0.75) : STATUS_HEX[zoneStatus];
        r.m.color.lerp(target, 0.15);
        let ei = 0;
        const emis = tmpEmissive.setRGB(0, 0, 0);
        if (zoneStatus === "fail") { emis.copy(STATUS_HEX.fail); ei = exact ? 0.6 + 1.6 * pulse : 0.25 + 0.35 * pulse; }
        else if (zoneStatus === "warn") { emis.copy(STATUS_HEX.warn); ei = 0.25 + 0.2 * pulse; }
        if (!exact && (isSel || isHover)) { emis.copy(CYAN); ei = isSel ? 0.9 : 0.5; } // the failed part stays red
        r.m.emissive.copy(emis);
        r.m.emissiveIntensity = ei;
      }
      if (p.edges) (p.edges.material as THREE.LineBasicMaterial).opacity = e * 0.35 * solid;
    }

    // Slide the scene into the space the panels leave free.
    const offsetX = viewOffset.current + (insetX - viewOffset.current) * (1 - Math.exp(-5 * dt));
    if (Math.abs(offsetX - viewOffset.current) > 0.05 || !(camera as THREE.PerspectiveCamera).view) {
      viewOffset.current = offsetX;
      (camera as THREE.PerspectiveCamera).setViewOffset(size.width, size.height, -offsetX, 0, size.width, size.height);
    }

    // Ease the orbit target toward the selected part.
    const sel = selected && parts.find((p) => p.zone === selected.zone && (!selected.part_id || p.partId === selected.part_id));
    const want = sel ? sel.node.getWorldPosition(tmpVec) : FOCUS_HOME;
    focus.current.lerp(want, 1 - Math.exp(-3 * dt));
    if (controls) { controls.target.copy(focus.current); controls.update(); }
  });

  const findPart = (e: ThreeEvent<PointerEvent | MouseEvent>) => {
    let o: THREE.Object3D | null = e.object;
    while (o && !o.userData.part) o = o.parent;
    return (o?.userData.part as PartRec | undefined) ?? null;
  };

  const failLabel = parts.find((p) => p.partId && p.partId === failedPartId);

  // Screen-space labels: project the part's world position onto DOM overlays owned by Vehicle3D.
  useEffect(() => { onHoverLabel(hover && hover.zone !== "body" && hover !== failLabel ? { text: hover.label, sub: hover.zone } : null); }, [hover, failLabel, onHoverLabel]);
  useEffect(() => { onFailLabel(failLabel ? failedPartName ?? failLabel.label : null); }, [failLabel, failedPartName, onFailLabel]);
  const tmp = useMemo(() => new THREE.Vector3(), []);
  useFrame(() => {
    const place = (el: HTMLDivElement | null, node: THREE.Object3D | undefined) => {
      if (!el || !node) return;
      node.getWorldPosition(tmp).add(LABEL_LIFT).project(camera);
      el.style.transform = `translate3d(${((tmp.x + 1) / 2) * size.width}px, ${((1 - tmp.y) / 2) * size.height}px, 0) translate(-50%, -100%)`;
      el.style.opacity = tmp.z < 1 && clock.current > 1.8 ? "1" : "0";
    };
    place(labels.fail.current, failLabel?.node);
    place(labels.hover.current, hover?.node);
  });

  return (
    <group position={[-center.x, 0, -center.z]}>
      <primitive
        object={root}
        onPointerMove={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          const p = findPart(e);
          const pick = p && p.zone !== "body" ? p : null;
          if (pick !== hover) setHover(pick);
          document.body.style.cursor = pick ? "pointer" : "auto";
        }}
        onPointerOut={() => { setHover(null); document.body.style.cursor = "auto"; }}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation();
          const p = findPart(e);
          if (!p || p.zone === "body") return;
          onPick({ zone: p.zone as Zone, part_id: p.partId, label_fr: p.label });
        }}
      />
    </group>
  );
}

function Label({ refEl, tone, text, sub }: { refEl: RefObject<HTMLDivElement | null>; tone: "fail" | "hover"; text: string | null; sub: string }) {
  return (
    <div ref={refEl} className="pointer-events-none absolute left-0 top-0 z-10 transition-opacity duration-300" style={{ opacity: 0, display: text ? "block" : "none" }}>
      <div className={`whitespace-nowrap rounded-md border px-2.5 py-1 text-[12px] ${tone === "fail" ? "border-fail/60 bg-[#2a1416] text-ink shadow-[0_0_24px_rgba(239,68,68,0.35)]" : "border-accent/50 bg-bg/80 text-ink"}`}>
        <div className="font-medium">{text}</div>
        <div className={`num text-[10px] uppercase tracking-wider ${tone === "fail" ? "text-fail" : "text-accent"}`}>{sub}</div>
      </div>
      <div className={`mx-auto h-5 w-px ${tone === "fail" ? "bg-fail/70" : "bg-accent/60"}`} />
    </div>
  );
}

export function Vehicle3D(props: Props) {
  const fail = useRef<HTMLDivElement>(null);
  const hover = useRef<HTMLDivElement>(null);
  const [failText, setFailText] = useState<string | null>(null);
  const [hoverText, setHoverText] = useState<{ text: string; sub: string } | null>(null);
  return (
    <div className="relative h-full w-full overflow-hidden">
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [15, 8.5, 15], fov: 32, near: 0.1, far: 200 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      onPointerMissed={() => props.onPick(null)}
    >
      <ambientLight intensity={0.55} />
      <directionalLight position={[8, 12, 6]} intensity={1.6} />
      <directionalLight position={[-10, 4, -8]} intensity={1.1} color="#22D3EE" />
      <pointLight position={[0, 6, 0]} intensity={8} distance={14} color="#94A3B8" />
      <Model {...props} labels={{ fail, hover }} onFailLabel={setFailText} onHoverLabel={setHoverText} />
      <Grid
        position={[0, -0.001, 0]}
        args={[60, 60]}
        cellSize={0.5}
        cellThickness={0.6}
        cellColor="#1F2A37"
        sectionSize={3}
        sectionThickness={1}
        sectionColor="#22D3EE"
        fadeDistance={34}
        fadeStrength={2.2}
        infiniteGrid
      />
      <ContactShadows key={props.type} frames={1} position={[0, 0, 0]} opacity={0.55} scale={18} blur={2.4} far={4} /> {/* baked: live shadows re-render the scene each frame */}
      <Sparkles count={40} scale={[22, 7, 22]} position={[0, 3, 0]} size={1.6} speed={0.25} color="#22D3EE" opacity={0.35} />
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        minDistance={6}
        maxDistance={26}
        maxPolarAngle={Math.PI / 2.05}
        autoRotate={!props.selected}
        autoRotateSpeed={0.45}
      />
    </Canvas>
    <Label refEl={fail} tone="fail" text={failText} sub="Défaillance détectée" />
    <Label refEl={hover} tone="hover" text={hoverText?.text ?? null} sub={hoverText?.sub ?? ""} />
    </div>
  );
}

useGLTF.preload("/models/truck.glb");
useGLTF.preload("/models/ambulance.glb");
