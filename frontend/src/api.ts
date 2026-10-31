import type {
  AgentEvent, Depot, FuelAnomaly, Incident, Mission, RouteOption, Vehicle, Zone,
} from "@shared/types";
import { compareRoutesLocal, missionCityChain } from "@/lib/geo";

const BASE = "/api";

export type ZoneStatus = "ok" | "warn" | "fail";
export interface ZoneHealth { status: ZoneStatus; reasons: string[]; part_id: string | null; incident_id: string | null }
export interface VehicleHealth { vehicle_id: string; type: Vehicle["type"]; zones: Record<Zone, ZoneHealth> }

export interface FuelKpi { window_days: number; spend_mad: number; overspend_mad: number; anomalies: number; flags: { vehicle_id: string; kind: string }[] }
export interface FuelLog { ts: string; litres: number; odometer_km: number; l_100km: number; station_city: string; cost_mad: number }
export interface FuelReport {
  vehicle_id: string; expected_l_100km: number; actual_l_100km: number; delta_pct: number;
  logs: FuelLog[]; anomalies: FuelAnomaly[]; mocked?: boolean;
}
export interface MissionPath { mission_id: string; path: string[]; coords: [number, number][]; progress_pct: number | null }
export interface Scenario { id: number; title: string; vehicle_id: string }

class HttpError extends Error {
  status: number;
  constructor(status: number, path: string) {
    super(`${status} ${path}`);
    this.status = status;
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new HttpError(res.status, path);
  return res.json();
}
async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new HttpError(res.status, path);
  return res.json();
}

/** Dev B's endpoints may not be live yet: fall back to a local computation on 404 / 405. */
async function withFallback<T>(fn: () => Promise<T>, fallback: () => T): Promise<T> {
  try {
    return await fn();
  } catch (e) {
    if (e instanceof HttpError && e.status !== 404 && e.status !== 405) throw e;
    return fallback();
  }
}

export const api = {
  fleet: () => get<Vehicle[]>("/fleet"),
  depots: () => get<Depot[]>("/depots"),
  missions: () => get<Mission[]>("/missions"),
  scenarios: () => get<Scenario[]>("/scenarios"),
  incidents: () => get<Incident[]>("/incidents"),
  incident: (id: string) => get<Incident>(`/incidents/${id}`),
  health: (vid: string) => get<VehicleHealth>(`/vehicles/${vid}/health`),
  audit: () => get<AgentEvent[]>("/audit"),
  approve: (id: string) => post<Incident>(`/incidents/${id}/approve`),
  runScenario: (id: number) => post<{ started: number }>(`/scenario/${id}`),
  reset: () => post<{ ok: boolean }>("/reset"),

  missionPath: (m: Mission, v: Vehicle | undefined) =>
    withFallback(
      () => get<MissionPath>(`/missions/${m.id}/path`),
      () => ({
        mission_id: m.id,
        path: missionCityChain(m.origin, m.stops.map((s) => s.city), v?.type ?? "truck"),
        coords: [],
        progress_pct: null,
      }),
    ),

  fuelKpi: () => get<FuelKpi>("/fuel/kpi"),
  fuel: (v: Vehicle) => withFallback(() => get<FuelReport>(`/fuel/${v.id}`), () => mockFuel(v)),

  compareRoutes: (from: string, to: string, v: Vehicle) =>
    withFallback(
      () => post<RouteOption[]>("/route/compare", { from, to, vehicle_id: v.id }),
      () => compareRoutesLocal(from, to, v),
    ),
};

/** Server-sent agent events. Returns a disposer. */
export function subscribeEvents(onEvent: (ev: AgentEvent) => void, onStatus: (live: boolean) => void) {
  // The Vite dev proxy holds back SSE headers, so the stream goes straight to the backend (CORS is open).
  const url = import.meta.env.VITE_EVENTS_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:8000/events" : `${BASE}/events`);
  const es = new EventSource(url);
  es.onopen = () => onStatus(true);
  es.onerror = () => onStatus(false);
  es.addEventListener("agent", (e) => onEvent(JSON.parse((e as MessageEvent).data)));
  return () => es.close();
}

// ---------- local fuel mock (shape of GET /fuel/{id}) ----------

function seeded(seed: string) {
  let h = 2166136261;
  for (const c of seed) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

const STATIONS = ["casablanca", "rabat", "settat", "marrakech", "fes", "meknes", "eljadida", "benguerir"];

function mockFuel(v: Vehicle): FuelReport {
  const rnd = seeded(v.id);
  const drift = v.id === "T-12" ? 0.26 : v.telemetry.idle_pct_7d > 25 ? 0.12 : 0;
  const logs: FuelLog[] = [];
  let odo = v.km - 6200;
  for (let i = 0; i < 10; i++) {
    const dist = 480 + Math.round(rnd() * 260);
    const ramp = drift * (i / 9);
    const l100 = v.base_l_100km * (1 + (rnd() - 0.5) * 0.08 + ramp);
    const litres = +((dist * l100) / 100).toFixed(1);
    odo += dist;
    const d = new Date(2026, 9, 24 - (10 - i) * 3, 8 + Math.floor(rnd() * 10), Math.floor(rnd() * 60));
    logs.push({
      ts: d.toISOString().slice(0, 16), litres, odometer_km: odo, l_100km: +l100.toFixed(1),
      station_city: STATIONS[Math.floor(rnd() * STATIONS.length)], cost_mad: Math.round(litres * 11.6),
    });
  }
  const recent = logs.slice(-3);
  const actual = +(recent.reduce((s, l) => s + l.l_100km, 0) / recent.length).toFixed(1);
  const delta = +(((actual - v.base_l_100km) / v.base_l_100km) * 100).toFixed(1);
  const anomalies: FuelAnomaly[] = [];
  if (delta > 12)
    anomalies.push({
      vehicle_id: v.id, kind: "overconsumption", value: actual, expected: v.base_l_100km,
      detected_at: logs[logs.length - 1].ts, probable_cause: "mechanical",
      note: "Hausse progressive sur 3 pleins, sans changement d'itinéraire : cause mécanique probable (frein qui frotte). Transmis à l'agent maintenance.",
    });
  if (v.telemetry.idle_pct_7d > 25)
    anomalies.push({
      vehicle_id: v.id, kind: "excessive_idle", value: v.telemetry.idle_pct_7d, expected: 10,
      detected_at: logs[logs.length - 1].ts, probable_cause: "behavior",
      note: "Moteur au ralenti au-delà du seuil sur 7 jours.",
    });
  return { vehicle_id: v.id, expected_l_100km: v.base_l_100km, actual_l_100km: actual, delta_pct: delta, logs, anomalies, mocked: true };
}
