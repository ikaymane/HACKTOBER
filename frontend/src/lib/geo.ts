import type { RouteOption, Vehicle, VehicleType } from "@shared/types";
import { ROAD_GRAPH } from "@/data/roadGraph";

export type LngLat = [number, number];

type Edge = (typeof ROAD_GRAPH.edges)[number];
type City = (typeof ROAD_GRAPH.cities)[number];

export const CITIES: Record<string, City> = Object.fromEntries(ROAD_GRAPH.cities.map((c) => [c.id, c]));

export const cityName = (id: string) => CITIES[id]?.name ?? id;
export const cityLngLat = (id: string): LngLat => [CITIES[id].lng, CITIES[id].lat];

const adjacency = new Map<string, { to: string; edge: Edge }[]>();
for (const e of ROAD_GRAPH.edges) {
  for (const [a, b] of [[e.from, e.to], [e.to, e.from]] as const) {
    if (!adjacency.has(a)) adjacency.set(a, []);
    adjacency.get(a)!.push({ to: b, edge: e });
  }
}

const meta = ROAD_GRAPH.meta;

function edgeHours(e: Edge, type: VehicleType) {
  return e.km / meta.speed_kmh[e.road as "highway" | "national"][type];
}
function edgeToll(e: Edge, type: VehicleType) {
  return e.toll_mad * (type === "truck" ? meta.truck_toll_multiplier : 1);
}
function edgeCost(e: Edge, v: Pick<Vehicle, "type" | "base_l_100km">) {
  const fuel = (e.km * v.base_l_100km) / 100;
  return fuel * meta.diesel_mad_per_l + edgeToll(e, v.type) + edgeHours(e, v.type) * meta.driver_cost_mad_per_hour;
}

/** Dijkstra over the road graph; returns the city ids and the edges used. */
export function shortestPath(from: string, to: string, weight: (e: Edge) => number) {
  const dist = new Map<string, number>([[from, 0]]);
  const prev = new Map<string, { city: string; edge: Edge }>();
  const open = new Set<string>([from]);
  while (open.size) {
    let cur = "";
    let best = Infinity;
    for (const c of open) if ((dist.get(c) ?? Infinity) < best) [cur, best] = [c, dist.get(c)!];
    open.delete(cur);
    if (cur === to) break;
    for (const { to: nxt, edge } of adjacency.get(cur) ?? []) {
      const d = best + weight(edge);
      if (d < (dist.get(nxt) ?? Infinity)) {
        dist.set(nxt, d);
        prev.set(nxt, { city: cur, edge });
        open.add(nxt);
      }
    }
  }
  if (!prev.has(to) && from !== to) return { cities: [from, to], edges: [] as Edge[] };
  const cities = [to];
  const edges: Edge[] = [];
  let c = to;
  while (c !== from) {
    const p = prev.get(c)!;
    edges.unshift(p.edge);
    cities.unshift(p.city);
    c = p.city;
  }
  return { cities, edges };
}

/** Client-side mirror of Dev B's /route/compare, used until that endpoint ships. */
export function compareRoutesLocal(from: string, to: string, v: Vehicle): RouteOption[] {
  const variants: [RouteOption["label"], (e: Edge) => number][] = [
    ["shortest", (e) => e.km],
    ["cheapest", (e) => edgeCost(e, v)],
    ["fastest", (e) => edgeHours(e, v.type)],
  ];
  return variants.map(([label, w]) => {
    const { cities, edges } = shortestPath(from, to, w);
    const km = edges.reduce((s, e) => s + e.km, 0);
    const hours = edges.reduce((s, e) => s + edgeHours(e, v.type), 0);
    const fuel_l = (km * v.base_l_100km) / 100;
    const fuel_cost_mad = Math.round(fuel_l * meta.diesel_mad_per_l);
    const toll_mad = Math.round(edges.reduce((s, e) => s + edgeToll(e, v.type), 0));
    const driver_cost_mad = Math.round(hours * meta.driver_cost_mad_per_hour);
    return {
      label, path: cities, km, hours: +hours.toFixed(2), fuel_l: +fuel_l.toFixed(1),
      fuel_cost_mad, toll_mad, driver_cost_mad, total_cost_mad: fuel_cost_mad + toll_mad + driver_cost_mad,
    };
  });
}

/** City chain for a mission: origin → each stop, by fastest road. */
export function missionCityChain(origin: string, stops: string[], type: VehicleType) {
  const chain = [origin];
  for (const s of stops) {
    const leg = shortestPath(chain[chain.length - 1], s, (e) => edgeHours(e, type));
    chain.push(...leg.cities.slice(1));
  }
  return chain;
}

const OSRM = "https://router.project-osrm.org/route/v1/driving/";

/** Real road geometry through the given cities (OSRM demo server), cached; straight lines if offline. */
export async function roadGeometry(cityIds: string[]): Promise<LngLat[]> {
  const pts = cityIds.filter((c) => CITIES[c]).map(cityLngLat);
  const key = `fs-road:${cityIds.join(">")}`;
  try {
    const hit = localStorage.getItem(key);
    if (hit) return JSON.parse(hit);
  } catch { /* storage unavailable */ }
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 6000);
    const url = `${OSRM}${pts.map((p) => p.join(",")).join(";")}?overview=full&geometries=geojson`;
    const res = await fetch(url, { signal: ctrl.signal });
    clearTimeout(t);
    const json = await res.json();
    const coords: LngLat[] = json.routes?.[0]?.geometry?.coordinates;
    if (!coords?.length) throw new Error("no route");
    const thinned = coords.filter((_, i) => i % 3 === 0 || i === coords.length - 1);
    try { localStorage.setItem(key, JSON.stringify(thinned)); } catch { /* quota */ }
    return thinned;
  } catch {
    return pts;
  }
}

export function haversineKm(a: LngLat, b: LngLat) {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b[1] - a[1]);
  const dLng = toRad(b[0] - a[0]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export interface Polyline {
  coords: LngLat[];
  cum: number[]; // cumulative km at each vertex
  km: number;
}

export function toPolyline(coords: LngLat[]): Polyline {
  const cum = [0];
  for (let i = 1; i < coords.length; i++) cum.push(cum[i - 1] + haversineKm(coords[i - 1], coords[i]));
  return { coords, cum, km: cum[cum.length - 1] || 0 };
}

/** Position + heading (degrees, 0 = north, clockwise) at fraction t of the line. */
export function pointAt(pl: Polyline, t: number): { pos: LngLat; heading: number } {
  const { coords, cum, km } = pl;
  if (coords.length < 2) return { pos: coords[0], heading: 0 };
  const target = Math.min(Math.max(t, 0), 1) * km;
  let i = 1;
  while (i < cum.length - 1 && cum[i] < target) i++;
  const a = coords[i - 1];
  const b = coords[i];
  const seg = cum[i] - cum[i - 1] || 1;
  const f = (target - cum[i - 1]) / seg;
  const pos: LngLat = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
  const heading = (Math.atan2(b[0] - a[0], b[1] - a[1]) * 180) / Math.PI;
  return { pos, heading };
}

/** Fraction along the line closest to a point (for snapping a vehicle onto its road). */
export function nearestFraction(pl: Polyline, p: LngLat): number {
  let best = 0;
  let bestD = Infinity;
  pl.coords.forEach((c, i) => {
    const d = haversineKm(c, p);
    if (d < bestD) [bestD, best] = [d, i];
  });
  return pl.km ? pl.cum[best] / pl.km : 0;
}
