import { create } from "zustand";
import type { AgentEvent, Depot, Incident, Mission, Vehicle } from "@shared/types";
import { api, subscribeEvents, type FuelKpi, type Scenario, type VehicleHealth } from "@/api";
import { nearestFraction, roadGeometry, toPolyline, type Polyline } from "@/lib/geo";

export interface Toast { id: string; title: string; sub: string; tone: "fail" | "info" | "ok" }

interface State {
  vehicles: Vehicle[];
  depots: Depot[];
  missions: Record<string, Mission>;
  scenarios: Scenario[];
  incidents: Record<string, Incident>;
  health: Record<string, VehicleHealth>;
  routes: Record<string, Polyline>; // by mission id
  tracks: Record<string, string>; // vehicle id -> last mission driven: a broken truck stays on the road it stopped on
  progress: Record<string, number>; // by vehicle id, 0..1 along its track
  fuelKpi: FuelKpi | null;
  events: AgentEvent[];
  lastAlert: { id: string; vehicle_id: string } | null; // the breakdown the map flies to
  toasts: Toast[];
  live: boolean;
  runningScenario: number | null;
  selectedId: string | null;
  inspectorOpen: boolean;
  auditOpen: boolean;
  hoverId: string | null;

  boot: () => Promise<void>;
  refetchFleet: () => Promise<void>;
  refetchIncident: (id: string) => Promise<void>;
  approve: (id: string) => Promise<void>;
  refetchHealth: (vid: string) => Promise<void>;
  openInspector: (vid: string) => void;
  closeInspector: () => void;
  toggleAudit: () => void;
  step: (dir: 1 | -1) => void;
  setHover: (vid: string | null) => void;
  runScenario: (id: number) => Promise<void>;
  reset: () => Promise<void>;
  tick: (dtSec: number) => void;
  pushToast: (toast: Toast) => void;
  dismissToast: (id: string) => void;
}

let booted = false;

// Agents emit in bursts: coalesce the refetches they trigger, or every event costs two requests.
const REFRESH_MS = 300;
const dirtyHealth = new Set<string>();
let refreshTimer: ReturnType<typeof setTimeout> | null = null;

/** Puts vehicles that just got a mission on that mission's road. */
function placeOnRoads(vehicles: Vehicle[], routes: State["routes"], tracks: State["tracks"], progress: State["progress"]) {
  const nextTracks = { ...tracks };
  const nextProgress = { ...progress };
  for (const v of vehicles) {
    if (!v.mission_id || nextTracks[v.id] === v.mission_id) continue;
    const r = routes[v.mission_id];
    if (!r) continue;
    nextTracks[v.id] = v.mission_id;
    nextProgress[v.id] = Math.min(nearestFraction(r, [v.position.lng, v.position.lat]), 0.92);
  }
  return { tracks: nextTracks, progress: nextProgress };
}

export const useStore = create<State>((set, get) => ({
  vehicles: [], depots: [], missions: {}, scenarios: [], incidents: {}, health: {}, routes: {}, tracks: {}, progress: {},
  fuelKpi: null, auditOpen: false, events: [], lastAlert: null, toasts: [], live: false, runningScenario: null, selectedId: null, inspectorOpen: false, hoverId: null,

  boot: async () => {
    if (booted) return;
    booted = true;
    const [vehicles, depots, missions, scenarios, incidents, audit, fuelKpi] = await Promise.all([
      api.fleet(), api.depots(), api.missions(), api.scenarios().catch(() => []), api.incidents().catch(() => []), api.audit().catch(() => []), api.fuelKpi().catch(() => null),
    ]);
    set({
      vehicles, depots, scenarios, fuelKpi, events: audit.slice(-200),
      missions: Object.fromEntries(missions.map((m) => [m.id, m])),
      incidents: Object.fromEntries(incidents.map((i) => [i.id, i])),
    });
    vehicles.forEach((v) => get().refetchHealth(v.id));

    subscribeEvents(
      (ev) => {
        set((s) => ({ events: [...s.events.slice(-199), ev] }));
        if (ev.agent === "system" && ev.kind === "alert" && ev.vehicle_id && ev.data?.scenario_id != null) {
          set({ lastAlert: { id: ev.id, vehicle_id: ev.vehicle_id } });
        }
        // Tool traffic doesn't touch the fleet; alerts, handoffs and decisions do.
        if (ev.vehicle_id && ev.kind !== "tool_call" && ev.kind !== "tool_result" && ev.kind !== "thought") {
          dirtyHealth.add(ev.vehicle_id);
          refreshTimer ??= setTimeout(() => {
            refreshTimer = null;
            get().refetchFleet();
            dirtyHealth.forEach((vid) => get().refetchHealth(vid));
            dirtyHealth.clear();
          }, REFRESH_MS);
        }
        const inc = ev.data?.incident_id as string | undefined;
        if (inc) get().refetchIncident(inc);
        const failed = ev.agent === "system" && ev.kind === "alert" && ev.data?.scenario_id == null;
        if ((ev.agent === "orchestrator" && ev.kind === "decision") || failed) set({ runningScenario: null });
      },
      (live) => set({ live }),
    );

    // Road geometry per mission, then snap each vehicle onto its road.
    const paths = await Promise.all(
      missions.map(async (m) => {
        const v = vehicles.find((x) => x.id === m.vehicle_id);
        const mp = await api.missionPath(m, v);
        const coords = mp.coords.length > 1
          ? mp.coords.map(([lat, lng]) => [lng, lat] as [number, number])
          : await roadGeometry(mp.path);
        return { m, v, pl: toPolyline(coords), pct: mp.progress_pct };
      }),
    );
    const routes: State["routes"] = {};
    const tracks: State["tracks"] = {};
    const progress: State["progress"] = {};
    for (const { m, v, pl, pct } of paths) {
      routes[m.id] = pl;
      if (!v) continue;
      tracks[v.id] = m.id;
      progress[v.id] = Math.min(pct != null ? pct / 100 : nearestFraction(pl, [v.position.lng, v.position.lat]), 0.92);
    }
    set({ routes, tracks, progress });
  },

  refetchFleet: async () => {
    const vehicles = await api.fleet();
    set((s) => ({ vehicles, ...placeOnRoads(vehicles, s.routes, s.tracks, s.progress) }));
  },

  refetchIncident: async (id) => {
    const inc = await api.incident(id);
    set((s) => ({ incidents: { ...s.incidents, [id]: inc } }));
    get().refetchHealth(inc.vehicle_id);
  },

  approve: async (id) => {
    const inc = await api.approve(id);
    set((s) => ({ incidents: { ...s.incidents, [id]: inc } }));
  },

  refetchHealth: async (vid) => {
    try {
      const h = await api.health(vid);
      set((s) => ({ health: { ...s.health, [vid]: h } }));
    } catch { /* vehicle may be gone after reset */ }
  },

  openInspector: (vid) => set({ selectedId: vid, inspectorOpen: true }),
  closeInspector: () => set({ inspectorOpen: false }),
  toggleAudit: () => set((s) => ({ auditOpen: !s.auditOpen })),
  step: (dir) => {
    const { vehicles, selectedId } = get();
    if (!vehicles.length) return;
    const i = vehicles.findIndex((v) => v.id === selectedId);
    const next = vehicles[(i + dir + vehicles.length) % vehicles.length];
    set({ selectedId: next.id });
  },
  setHover: (hoverId) => set({ hoverId }),

  runScenario: async (id) => {
    if (get().runningScenario != null) return;
    set({ runningScenario: id });
    try {
      await api.runScenario(id);
    } catch {
      set({ runningScenario: null });
      get().pushToast({ id: `busy-${Date.now()}`, tone: "info", title: `Scénario ${id} déjà joué`, sub: "Appuyez sur R pour réinitialiser la flotte." });
    }
  },

  reset: async () => {
    await api.reset();
    set({ incidents: {}, events: [], toasts: [], lastAlert: null, runningScenario: null, inspectorOpen: false });
    const [vehicles, missions] = await Promise.all([api.fleet(), api.missions()]);
    set((s) => ({
      vehicles,
      missions: Object.fromEntries(missions.map((m) => [m.id, m])),
      ...placeOnRoads(vehicles, s.routes, {}, {}),
    }));
    vehicles.forEach((v) => get().refetchHealth(v.id));
  },

  // Trucks on a mission creep along their roads so the map feels live; broken ones stop.
  tick: (dt) => {
    const { vehicles, progress } = get();
    const next = { ...progress };
    let changed = false;
    for (const v of vehicles) {
      if (v.status !== "on_mission" || next[v.id] == null) continue;
      const speed = v.type === "ambulance" ? 0.0022 : 0.0012; // fraction / s
      next[v.id] = Math.min(next[v.id] + speed * dt, 0.995); // arrived: waits at the last stop
      changed = true;
    }
    if (changed) set({ progress: next });
  },

  pushToast: (toast) => {
    set((s) => ({ toasts: [...s.toasts, toast] }));
    setTimeout(() => get().dismissToast(toast.id), 6500);
  },
  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export const incidentForVehicle = (incidents: Record<string, Incident>, vid: string) =>
  Object.values(incidents).filter((i) => i.vehicle_id === vid).at(-1);
