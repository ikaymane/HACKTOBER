import { motion } from "framer-motion";
import { Fuel, Route, X } from "lucide-react";
import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Mission, RouteOption, Vehicle } from "@shared/types";
import { api, type FuelReport } from "@/api";
import { cityName } from "@/lib/geo";
import { EXPO, mad } from "../ui";

const ROUTE_FR: Record<RouteOption["label"], string> = { shortest: "Plus courte", cheapest: "Moins chère", fastest: "Plus rapide" };
const ANOMALY_FR: Record<string, string> = {
  overconsumption: "Surconsommation", fill_over_capacity: "Plein > capacité", fill_without_km: "Plein sans km",
  excessive_idle: "Ralenti excessif", detour: "Détour",
};

const item = {
  hidden: { opacity: 0, x: 20, filter: "blur(4px)" },
  show: { opacity: 1, x: 0, filter: "blur(0px)", transition: { duration: 0.7, ease: EXPO } },
};

export function FuelDrawer({ vehicle, mission, onClose, onReport }: { vehicle: Vehicle; mission: Mission | undefined; onClose: () => void; onReport?: (r: FuelReport) => void }) {
  const [fuel, setFuel] = useState<FuelReport | null>(null);
  const [routes, setRoutes] = useState<RouteOption[] | null>(null);

  useEffect(() => {
    let alive = true;
    setFuel(null);
    setRoutes(null);
    api.fuel(vehicle).then((f) => { if (alive) { setFuel(f); onReport?.(f); } });
    if (mission) api.compareRoutes(mission.origin, mission.stops.at(-1)!.city, vehicle).then((r) => alive && setRoutes(r));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vehicle.id, mission?.id]);

  const delta = fuel?.delta_pct ?? 0;
  const cheapest = routes ? Math.min(...routes.map((r) => r.total_cost_mad)) : 0;
  // Ties are common on a small graph: recommend one route only, preferring the "cheapest" label.
  const bestLabel = routes ? (routes.find((r) => r.label === "cheapest" && r.total_cost_mad === cheapest) ?? routes.find((r) => r.total_cost_mad === cheapest))?.label : null;
  const maxCost = routes ? Math.max(...routes.map((r) => r.total_cost_mad)) : 1;

  return (
    <motion.aside
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ duration: 0.85, ease: EXPO }}
      className="absolute bottom-0 right-0 top-0 z-20 flex w-[420px] flex-col border-l border-line bg-panel/95 backdrop-blur-xl"
    >
      <div className="flex items-center gap-2 border-b border-line px-5 py-4">
        <Fuel size={15} className="text-accent" />
        <span className="text-[14px] font-medium">Carburant</span>
        {fuel?.mocked && <span className="tag ml-1 text-dim">aperçu local</span>}
        <button onClick={onClose} className="ml-auto rounded-full p-1 text-dim hover:bg-line hover:text-ink"><X size={14} /></button>
      </div>

      {!fuel ? (
        <div className="m-5 h-40 rounded-lg shimmer" />
      ) : (
        <motion.div className="flex-1 overflow-y-auto" variants={{ show: { transition: { staggerChildren: 0.07, delayChildren: 0.2 } } }} initial="hidden" animate="show">
          <motion.div variants={item} className="grid grid-cols-3 gap-px border-b border-line bg-line">
            {[
              ["Attendu", `${fuel.expected_l_100km}`, "L/100"],
              ["Réel", fuel.actual_l_100km != null ? `${fuel.actual_l_100km}` : "—", "L/100"],
              ["Écart", fuel.delta_pct != null ? `${delta > 0 ? "+" : ""}${delta}%` : "—", ""],
            ].map(([k, v, u], i) => (
              <div key={k} className="bg-panel px-4 py-3">
                <div className="tag">{k}</div>
                <div className={`num mt-1 text-[20px] ${i === 2 ? (delta > 10 ? "text-fail" : delta > 5 ? "text-warn" : "text-ok") : ""}`}>
                  {v}<span className="ml-1 text-[11px] text-dim">{u}</span>
                </div>
              </div>
            ))}
          </motion.div>

          <motion.div variants={item} className="h-[190px] px-2 pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={fuel.logs.filter((l) => l.l_100km != null).map((l) => ({ ...l, d: l.ts.slice(5, 10) }))} margin={{ left: -18, right: 14, top: 6, bottom: 0 }}>
                <CartesianGrid stroke="#1F2A37" strokeDasharray="2 4" vertical={false} />
                <XAxis dataKey="d" tick={{ fill: "#64748B", fontSize: 10, fontFamily: "JetBrains Mono" }} axisLine={{ stroke: "#1F2A37" }} tickLine={false} />
                <YAxis domain={["dataMin - 2", "dataMax + 2"]} tick={{ fill: "#64748B", fontSize: 10, fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: "#0B0F14", border: "1px solid #1F2A37", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#94A3B8" }}
                  formatter={(v) => [`${v} L/100 km`, "Conso"]}
                />
                <ReferenceLine y={fuel.expected_l_100km} stroke="#94A3B8" strokeDasharray="4 4" label={{ value: "attendu", fill: "#94A3B8", fontSize: 10, position: "insideTopLeft" }} />
                <Line type="monotone" dataKey="l_100km" stroke={delta > 10 ? "#EF4444" : "#22D3EE"} strokeWidth={2} dot={{ r: 2.5, strokeWidth: 0, fill: delta > 10 ? "#EF4444" : "#22D3EE" }} animationDuration={1400} animationEasing="ease-out" />
              </LineChart>
            </ResponsiveContainer>
          </motion.div>

          {fuel.anomalies.length > 0 && (
            <motion.div variants={item} className="px-5 pt-3">
              <h4 className="tag mb-2">Anomalies · agent carburant</h4>
              <div className="flex flex-col gap-2">
                {fuel.anomalies.map((a, i) => (
                  <div key={i} className="rounded-lg border border-warn/40 bg-warn/[0.06] p-3">
                    <div className="flex items-baseline justify-between">
                      <span className="text-[12.5px] font-medium text-warn">{ANOMALY_FR[a.kind] ?? a.kind}</span>
                      <span className="num text-[11px] text-muted">{a.value} vs {a.expected}</span>
                    </div>
                    {a.note && <p className="mt-1 text-[12px] leading-relaxed text-ink/85">{a.note}</p>}
                    {a.probable_cause && <span className="tag mt-1.5 inline-block">cause probable · {a.probable_cause}</span>}
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {routes && mission && (
            <motion.div variants={item} className="px-5 pt-5">
              <h4 className="tag mb-2 flex items-center gap-1.5"><Route size={11} /> Itinéraires · {cityName(mission.origin)} → {cityName(mission.stops.at(-1)!.city)}</h4>
              <div className="flex flex-col gap-2">
                {routes.map((r) => {
                  const best = r.label === bestLabel;
                  return (
                    <div key={r.label} className={`rounded-lg border p-3 ${best ? "border-accent/60 bg-accent/[0.06]" : "border-line"}`}>
                      <div className="flex items-baseline justify-between">
                        <span className="text-[12.5px] font-medium">{ROUTE_FR[r.label]} {best && <span className="ml-1 rounded-full bg-accent px-1.5 text-[9.5px] font-semibold uppercase text-bg">recommandé</span>}</span>
                        <span className="num text-[13px]">{mad(r.total_cost_mad)}</span>
                      </div>
                      <div className="mt-2 h-1 overflow-hidden rounded-full bg-line">
                        <motion.div className="h-full" style={{ background: best ? "#22D3EE" : "#475569" }} initial={{ width: 0 }} animate={{ width: `${(r.total_cost_mad / maxCost) * 100}%` }} transition={{ duration: 1.1, ease: EXPO, delay: 0.4 }} />
                      </div>
                      <div className="num mt-2 flex justify-between text-[10.5px] text-muted">
                        <span>{r.km} km</span><span>{r.hours.toFixed(1)} h</span><span>{r.fuel_l} L</span><span>péage {r.toll_mad}</span>
                      </div>
                      <div className="mt-1 truncate text-[11px] text-dim">{r.path.map(cityName).join(" → ")}</div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          )}

          <motion.div variants={item} className="px-5 py-5">
            <h4 className="tag mb-2">Pleins</h4>
            <table className="w-full text-[11.5px]">
              <thead className="text-left text-dim">
                <tr><th className="pb-1.5 font-normal">Date</th><th className="font-normal">Ville</th><th className="text-right font-normal">L</th><th className="text-right font-normal">L/100</th><th className="text-right font-normal">MAD</th></tr>
              </thead>
              <tbody className="num">
                {[...fuel.logs].reverse().map((l, i) => (
                  <tr key={`${l.ts}-${i}`} className="border-t border-line/60">
                    <td className="py-1.5 text-muted">{l.ts.slice(5, 10)}</td>
                    <td className="font-sans">{cityName(l.station_city)}</td>
                    <td className="text-right">{l.litres}</td>
                    <td className={`text-right ${(l.l_100km ?? 0) > fuel.expected_l_100km * 1.1 ? "text-fail" : ""}`}>{l.l_100km ?? "—"}</td>
                    <td className="text-right text-muted">{Math.round(l.cost_mad).toLocaleString("fr-FR")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </motion.div>
        </motion.div>
      )}
    </motion.aside>
  );
}
