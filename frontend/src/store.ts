import { create } from "zustand";
import type { AgentEvent, Depot, Incident, Mission, Vehicle } from "@shared/types";
import { api, subscribeEvents, type Scenario, type VehicleHealth } from "@/api";
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
  progress: Record<string, number>; // by vehicle id, 0..1 along its mission route
  events: AgentEvent[];
  toasts: Toast[];
  live: boolean;
  runningScenario: number | null;
  selectedId: string | null;
  inspectorOpen: boolean;
  hoverId: string | null;

  boot: () => Promise<void>;
  refetchFleet: () => Promise<void>;
  refetchIncident: (id: string) => Promise<void>;
  refetchHealth: (vid: string) => Promise<void>;
  openInspector: (vid: string) => void;
  closeInspector: () => void;
  step: (dir: 1 | -1) => void;
  setHover: (vid: string | null) => void;
  runScenario: (id: number) => Promise<void>;
  reset: () => Promise<void>;
  tick: (dtSec: number) => void;
  dismissToast: (id: string) => void;
}

let booted = false;

export const useStore = create<State>((set, get) => ({
  vehicles: [], depots: [], missions: {}, scenarios: [], incidents: {}, health: {}, routes: {}, progress: {},
  events: [], toasts: [], live: false, runningScenario: null, selectedId: null, inspectorOpen: false, hoverId: null,

  boot: async () => {
    if (booted) return;
    booted = true;
    const [vehicles, depots, missions, scenarios, incidents] = await Promise.all([
      api.fleet(), api.depots(), api.missions(), api.scenarios().catch(() => []), api.incidents().catch(() => []),
    ]);
    set({
      vehicles, depots, scenarios,
      missions: Object.fromEntries(missions.map((m) => [m.id, m])),
      incidents: Object.fromEntries(incidents.map((i) => [i.id, i])),
    });
    vehicles.forEach((v) => get().refetchHealth(v.id));

    subscribeEvents(
      (ev) => {
        set((s) => ({ events: [...s.events.slice(-199), ev] }));
        if (ev.vehicle_id) {
          get().refetchFleet();
          get().refetchHealth(ev.vehicle_id);
        }
        const inc = ev.data?.incident_id as string | undefined;
        if (inc) get().refetchIncident(inc);
        if (ev.agent === "orchestrator" && ev.kind === "decision") set({ runningScenario: null });
      },
      (live) => set({ live }),
    );

    // Road geometry per mission, then snap each vehicle onto its road.
    await Promise.all(
      missions.map(async (m) => {
        const v = vehicles.find((x) => x.id === m.vehicle_id);
        const mp = await api.missionPath(m, v);
        // The backend's coords are city-to-city straight lines: draw the real roads through the same cities,
        // and snap the vehicle by its GPS position (finer than the city-index progress_pct).
        const pl = toPolyline(await roadGeometry(mp.path));
        const frac = v ? nearestFraction(pl, [v.position.lng, v.position.lat]) : (mp.progress_pct ?? 0) / 100;
        set((s) => ({
          routes: { ...s.routes, [m.id]: pl },
          progress: v ? { ...s.progress, [v.id]: Math.min(frac, 0.92) } : s.progress,
        }));
      }),
    );
  },

  refetchFleet: async () => {
    const vehicles = await api.fleet();
    set({ vehicles });
  },

  refetchIncident: async (id) => {
    const isNew = !get().incidents[id];
    const inc = await api.incident(id);
    set((s) => ({ incidents: { ...s.incidents, [id]: inc } }));
    get().refetchHealth(inc.vehicle_id);
    if (isNew) {
      const toast: Toast = {
        id, tone: "fail",
        title: `Incident ${inc.id} · ${inc.vehicle_id} · ${inc.diagnosis.part_name}`,
        sub: `${inc.decision.action === "replace" ? "Remplacement" : "Réparation"} · confiance ${Math.round(inc.diagnosis.confidence * 100)}%`,
      };
      set((s) => ({ toasts: [...s.toasts, toast] }));
      setTimeout(() => get().dismissToast(id), 6500);
    }
  },

  refetchHealth: async (vid) => {
    try {
      const h = await api.health(vid);
      set((s) => ({ health: { ...s.health, [vid]: h } }));
    } catch { /* vehicle may be gone after reset */ }
  },

  openInspector: (vid) => set({ selectedId: vid, inspectorOpen: true }),
  closeInspector: () => set({ inspectorOpen: false }),
  step: (dir) => {
    const { vehicles, selectedId } = get();
    if (!vehicles.length) return;
    const i = vehicles.findIndex((v) => v.id === selectedId);
    const next = vehicles[(i + dir + vehicles.length) % vehicles.length];
    set({ selectedId: next.id });
  },
  setHover: (hoverId) => set({ hoverId }),

  runScenario: async (id) => {
    set({ runningScenario: id });
    await api.runScenario(id);
  },

  reset: async () => {
    await api.reset();
    set({ incidents: {}, events: [], toasts: [], runningScenario: null, inspectorOpen: false });
    const vehicles = await api.fleet();
    set({ vehicles });
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
      next[v.id] = next[v.id] >= 0.995 ? 0.02 : next[v.id] + speed * dt;
      changed = true;
    }
    if (changed) set({ progress: next });
  },

  dismissToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export const incidentForVehicle = (incidents: Record<string, Incident>, vid: string) =>
  Object.values(incidents).filter((i) => i.vehicle_id === vid).at(-1);
