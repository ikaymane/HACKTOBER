import { motion } from "framer-motion";
import { useMemo } from "react";
import { useStore } from "@/store";
import { Counter, EXPO, Tag } from "./ui";

export function KpiBar() {
  const vehicles = useStore((s) => s.vehicles);
  const incidents = useStore((s) => s.incidents);
  const routes = useStore((s) => s.routes);
  const progress = useStore((s) => s.progress);
  const missions = useStore((s) => s.missions);
  const live = useStore((s) => s.live);

  const k = useMemo(() => {
    const inc = Object.values(incidents);
    const atRisk = inc.filter((i) => i.penalty.at_risk && !i.penalty.mitigation).reduce((s, i) => s + i.penalty.amount_mad, 0);
    const avoided = inc.filter((i) => i.penalty.at_risk && i.penalty.mitigation).reduce((s, i) => s + i.penalty.amount_mad, 0);
    // Estimated diesel burnt today: km done on the current mission × L/100 km × 11.6 MAD/L.
    const fuel = vehicles.reduce((s, v) => {
      const r = v.mission_id ? routes[v.mission_id] : undefined;
      if (!r) return s;
      return s + ((r.km * (progress[v.id] ?? 0) * v.base_l_100km) / 100) * 11.6;
    }, 0);
    return {
      onMission: vehicles.filter((v) => v.status === "on_mission").length,
      total: vehicles.length,
      open: inc.length,
      broken: vehicles.filter((v) => v.status === "breakdown").length,
      atRisk, avoided, fuel,
      missions: Object.keys(missions).length,
    };
  }, [vehicles, incidents, routes, progress, missions]);

  const items = [
    { n: "01", label: "Véhicules en mission", value: <><Counter value={k.onMission} /><span className="text-dim">/{k.total}</span></>, sub: `${k.missions} missions actives` },
    { n: "02", label: "Incidents ouverts", value: <Counter value={k.open} className={k.open ? "text-fail" : ""} />, sub: k.broken ? `${k.broken} véhicule(s) à l'arrêt` : "Aucune panne" },
    { n: "03", label: "Pénalités à risque / évitées", value: <><Counter value={k.atRisk} className={k.atRisk ? "text-warn" : ""} /><span className="mx-1.5 text-dim">/</span><Counter value={k.avoided} className="text-ok" /></>, sub: "MAD" },
    { n: "04", label: "Carburant aujourd'hui", value: <Counter value={k.fuel} />, sub: "MAD · estimé" },
  ];

  return (
    <header className="relative z-20 flex h-[78px] items-stretch border-b border-line bg-bg/80 backdrop-blur">
      <div className="flex w-[280px] shrink-0 items-center gap-3 border-r border-line px-5">
        <svg width="30" height="30" viewBox="0 0 84 84" fill="none">
          <rect x="2" y="2" width="80" height="80" rx="18" stroke="#1F2A37" strokeWidth="3" />
          <path d="M24 60V24h30M24 42h22" stroke="#22D3EE" strokeWidth="7" strokeLinecap="round" />
          <circle cx="58" cy="57" r="7" fill="#22D3EE" />
        </svg>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight">FleetSense</div>
          <div className="flex items-center gap-1.5 text-[11px] text-muted">
            <span className={`h-1.5 w-1.5 rounded-full ${live ? "bg-ok" : "bg-fail"}`} />
            {live ? "Agents en ligne" : "Hors ligne"}
          </div>
        </div>
      </div>

      <div className="grid flex-1 grid-cols-4">
        {items.map((it, i) => (
          <motion.div
            key={it.n}
            className="relative flex flex-col justify-center gap-1 border-r border-line px-6 last:border-r-0"
            initial={{ opacity: 0, y: -14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, ease: EXPO, delay: 0.1 + i * 0.08 }}
          >
            <Tag n={it.n}>{it.label}</Tag>
            <div className="flex items-baseline gap-2">
              <span className="text-[26px] font-medium leading-none tracking-tight">{it.value}</span>
              <span className="text-[11px] text-dim">{it.sub}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </header>
  );
}
