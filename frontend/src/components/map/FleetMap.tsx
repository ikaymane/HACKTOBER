import DeckGL from "@deck.gl/react";
import { FlyToInterpolator, type MapViewState, type PickingInfo } from "@deck.gl/core";
import { ColumnLayer, PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { ScenegraphLayer } from "@deck.gl/mesh-layers";
import { TripsLayer } from "@deck.gl/geo-layers";
import { Map } from "react-map-gl/maplibre";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Vehicle } from "@shared/types";
import { useStore } from "@/store";
import { pointAt, type LngLat } from "@/lib/geo";

const STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const START: MapViewState = { longitude: -6.6, latitude: 33.0, zoom: 4.6, pitch: 0, bearing: 0 };
const HOME: MapViewState = { longitude: -6.9, latitude: 33.15, zoom: 6.15, pitch: 50, bearing: -12 };

const CYAN: [number, number, number] = [34, 211, 238];
const RED: [number, number, number] = [239, 68, 68];
const AMBER: [number, number, number] = [245, 158, 11];

interface Placed { v: Vehicle; pos: LngLat; heading: number; alert: "fail" | "warn" | null }

export function FleetMap() {
  const vehicles = useStore((s) => s.vehicles);
  const depots = useStore((s) => s.depots);
  const routes = useStore((s) => s.routes);
  const progress = useStore((s) => s.progress);
  const health = useStore((s) => s.health);
  const hoverId = useStore((s) => s.hoverId);
  const selectedId = useStore((s) => s.selectedId);
  const events = useStore((s) => s.events);
  const open = useStore((s) => s.openInspector);
  const setHover = useStore((s) => s.setHover);
  const tick = useStore((s) => s.tick);

  const [view, setView] = useState<MapViewState>(START);
  const [time, setTime] = useState(0);
  const [models, setModels] = useState(true);

  // Cinematic fly-in once the map is up.
  useEffect(() => {
    const t = setTimeout(() => {
      setView({ ...HOME, transitionDuration: 3200, transitionInterpolator: new FlyToInterpolator({ speed: 0.9 }) });
    }, 500);
    return () => clearTimeout(t);
  }, []);

  // Animation clock: drives the light trails and pulse rings; vehicles advance 4× / s.
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let acc = 0;
    const loop = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      acc += dt;
      setTime((t) => t + dt);
      if (acc > 0.25) { tick(acc); acc = 0; }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [tick]);

  const placed: Placed[] = useMemo(() => vehicles.map((v) => {
    const r = v.mission_id ? routes[v.mission_id] : undefined;
    const zones = health[v.id]?.zones;
    const alert = v.status === "breakdown" || (zones && Object.values(zones).some((z) => z.status === "fail")) ? "fail"
      : zones && Object.values(zones).some((z) => z.status === "warn") ? "warn" : null;
    if (r && progress[v.id] != null) {
      const { pos, heading } = pointAt(r, progress[v.id]);
      return { v, pos, heading, alert };
    }
    return { v, pos: [v.position.lng, v.position.lat] as LngLat, heading: 0, alert };
  }), [vehicles, routes, progress, health]);

  // Fly to the vehicle a scenario just broke.
  const lastAlert = useRef<string | null>(null);
  useEffect(() => {
    const ev = [...events].reverse().find((e) => e.agent === "system" && e.kind === "alert" && e.vehicle_id);
    if (!ev || ev.id === lastAlert.current) return;
    lastAlert.current = ev.id;
    const p = placed.find((x) => x.v.id === ev.vehicle_id);
    if (p) setView({ longitude: p.pos[0], latitude: p.pos[1] - 0.25, zoom: 7.6, pitch: 58, bearing: -20, transitionDuration: 2200, transitionInterpolator: new FlyToInterpolator({ speed: 1.1 }) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events]);

  const routeData = useMemo(() => vehicles.flatMap((v) => {
    const r = v.mission_id ? routes[v.mission_id] : undefined;
    if (!r) return [];
    return [{ v, path: r.coords, timestamps: r.cum, km: r.km, broken: v.status === "breakdown" }];
  }), [vehicles, routes]);

  const pulse = (time % 1.6) / 1.6;
  const focus = hoverId ?? selectedId;

  const layers = [
    new PathLayer({
      id: "roads-glow",
      data: routeData,
      getPath: (d) => d.path,
      getColor: (d) => (d.broken ? [...RED, 50] : [...CYAN, 28]),
      getWidth: 9,
      widthUnits: "pixels",
      capRounded: true,
      jointRounded: true,
    }),
    new PathLayer({
      id: "roads",
      data: routeData,
      getPath: (d) => d.path,
      getColor: (d) => (d.broken ? [...RED, 200] : d.v.id === focus ? [...CYAN, 255] : [...CYAN, 120]),
      getWidth: (d) => (d.v.id === focus ? 2.6 : 1.4),
      widthUnits: "pixels",
      capRounded: true,
      jointRounded: true,
      updateTriggers: { getColor: [focus], getWidth: [focus] },
    }),
    new TripsLayer({
      id: "trails",
      data: routeData.filter((d) => !d.broken),
      getPath: (d) => d.path,
      getTimestamps: (d) => d.timestamps,
      getColor: [180, 245, 255],
      widthMinPixels: 2.2,
      trailLength: 70,
      currentTime: (time * 90) % 700,
      fadeTrail: true,
      capRounded: true,
      jointRounded: true,
    }),
    new ColumnLayer({
      id: "depots",
      data: depots,
      diskResolution: 4,
      radius: 3500,
      extruded: true,
      getPosition: (d) => [d.position.lng, d.position.lat],
      getElevation: (d) => (d.has_workshop ? 26000 : 14000),
      getFillColor: (d) => (d.has_workshop ? [148, 163, 184, 200] : [100, 116, 139, 160]),
      material: { ambient: 0.6, diffuse: 0.6 },
      pickable: true,
    }),
    new TextLayer({
      id: "depot-labels",
      data: depots,
      getPosition: (d) => [d.position.lng, d.position.lat, d.has_workshop ? 30000 : 18000],
      getText: (d) => d.id.replace("DEP-", ""),
      getSize: 10,
      getColor: [148, 163, 184, 220],
      fontFamily: "JetBrains Mono",
      fontWeight: 500,
      getPixelOffset: [0, -8],
      billboard: true,
    }),
    new ScatterplotLayer<Placed>({
      id: "pulse",
      data: placed.filter((p) => p.alert === "fail" || p.v.id === focus),
      getPosition: (p) => p.pos,
      getRadius: (p) => (p.alert === "fail" ? 6 + pulse * 30 : 14),
      radiusUnits: "pixels",
      stroked: true,
      filled: true,
      getFillColor: (p) => (p.alert === "fail" ? [...RED, Math.round(90 * (1 - pulse))] : [...CYAN, 30]),
      getLineColor: (p) => (p.alert === "fail" ? [...RED, Math.round(255 * (1 - pulse))] : [...CYAN, 200]),
      lineWidthMinPixels: 1.2,
      updateTriggers: { getRadius: [pulse, focus], getFillColor: [pulse, focus], getLineColor: [pulse, focus] },
    }),
    new ScatterplotLayer<Placed>({
      id: "markers",
      data: placed,
      getPosition: (p) => p.pos,
      getRadius: (p) => (p.v.id === focus ? 6 : 4.5),
      radiusUnits: "pixels",
      stroked: true,
      getFillColor: (p) => (p.alert === "fail" ? RED : p.alert === "warn" ? AMBER : p.v.type === "ambulance" ? [241, 245, 249] : CYAN),
      getLineColor: [11, 15, 20],
      lineWidthMinPixels: 1.5,
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 120],
      updateTriggers: { getRadius: [focus] },
    }),
    ...(models
      ? (["truck", "ambulance"] as const).map((type) =>
          new ScenegraphLayer<Placed>({
            id: `models-${type}`,
            data: placed.filter((p) => p.v.type === type),
            scenegraph: `/models/${type}.glb`,
            getPosition: (p) => p.pos,
            getOrientation: (p) => [0, 90 - p.heading, 90],
            sizeScale: (type === "truck" ? 2600 : 2800) * Math.min(1, Math.pow(2, 6.2 - view.zoom) * 1.6),
            sizeMinPixels: 0,
            // luma.gl autoplays every clip in the GLB: stop all ("*" applies first), then roll the wheels only.
            // "explode" belongs to the inspector, never the map.
            _animations: { "*": { playing: false }, drive: { playing: true, speed: 1 } },
            _lighting: "pbr",
            getColor: (p) => (p.alert === "fail" ? [255, 120, 120, 255] : [255, 255, 255, 255]),
            pickable: true,
            onError: () => { setModels(false); return true; },
            updateTriggers: { getColor: [health] },
          }),
        )
      : []),
  ];

  const onClick = (info: PickingInfo) => {
    const p = info.object as Placed | undefined;
    if (p?.v) open(p.v.id);
  };
  const onHover = (info: PickingInfo) => {
    const p = info.object as Placed | undefined;
    setHover(p?.v?.id ?? null);
  };

  return (
    <div className="relative h-full w-full">
      <DeckGL
        viewState={view}
        onViewStateChange={({ viewState }) => setView(viewState as MapViewState)}
        controller={{ dragRotate: true, touchRotate: true }}
        layers={layers}
        onClick={onClick}
        onHover={onHover}
        getCursor={({ isHovering }) => (isHovering ? "pointer" : "grab")}
        getTooltip={({ object }) => {
          const o = object as (Placed & { id?: string; city?: string }) | undefined;
          if (o?.v) return {
            html: `<div style="font:500 12px Inter"><b style="font-family:JetBrains Mono">${o.v.id}</b> · ${o.v.model}<br/><span style="color:#94A3B8">${o.v.driver} · ${o.v.plate}</span></div>`,
            style: { background: "#121821", border: "1px solid #1F2A37", borderRadius: "8px", color: "#E5E7EB", padding: "8px 10px" },
          };
          if (o?.city) return {
            html: `<div style="font:500 12px Inter">${o.id}<br/><span style="color:#94A3B8">Dépôt ${o.city}</span></div>`,
            style: { background: "#121821", border: "1px solid #1F2A37", borderRadius: "8px", color: "#E5E7EB", padding: "8px 10px" },
          };
          return null;
        }}
      >
        <Map mapStyle={STYLE} reuseMaps attributionControl={{ compact: true }} />
      </DeckGL>

      {/* Vignette + HUD overlays */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_45%,rgba(11,15,20,0.85)_100%)]" />
      <div className="pointer-events-none absolute left-4 top-4 flex flex-col gap-1">
        <span className="tag"><span className="text-accent/80">[B]</span> Carte opérationnelle</span>
        <span className="num text-[10.5px] text-dim">
          {view.latitude.toFixed(3)}°N {Math.abs(view.longitude).toFixed(3)}°W · z{view.zoom.toFixed(1)} · {Math.round(view.pitch ?? 0)}°
        </span>
      </div>
      <div className="absolute bottom-4 left-4 flex items-center gap-4 rounded-full border border-line bg-bg/70 px-4 py-2 text-[11px] text-muted backdrop-blur">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-accent" />Camion</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-slate-100" />Ambulance</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-fail" />Panne</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 bg-slate-400" />Dépôt</span>
        <button onClick={() => setView({ ...HOME, transitionDuration: 1600, transitionInterpolator: new FlyToInterpolator() })} className="ml-2 border-l border-line pl-3 text-ink hover:text-accent">Recentrer</button>
      </div>
    </div>
  );
}
