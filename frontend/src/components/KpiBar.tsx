import { motion } from "framer-motion";
import { useMemo } from "react";
import { useStore } from "@/store";
import { Counter, EXPO } from "./ui";

export function KpiBar() {
  const vehicles = useStore((s) => s.vehicles);
  const incidents = useStore((s) => s.incidents);
  const fuel = useStore((s) => s.fuelKpi);
  const live = useStore((s) => s.live);

  const k = useMemo(() => {
    const inc = Object.values(incidents);
    return {
      onMission: vehicles.filter((v) => v.status === "on_mission").length,
      total: vehicles.length,
      open: inc.filter((i) => !i.approved).length,
      broken: vehicles.filter((v) => v.status === "breakdown").length,
      atRisk: inc.filter((i) => i.penalty.at_risk).reduce((s, i) => s + i.penalty.amount_mad, 0),
      avoided: inc.reduce((s, i) => s + i.penalty.avoided_mad, 0),
    };
  }, [vehicles, incidents]);

  const items = [
    { label: "Véhicules en mission", value: <><Counter value={k.onMission} /><span className="text-dim">/{k.total}</span></>, sub: k.broken ? `${k.broken} à l'arrêt` : "Aucun à l'arrêt" },
    { label: "Plans à approuver", value: <Counter value={k.open} className={k.open ? "text-fail" : ""} />, sub: k.open ? "En attente de vous" : "Rien en attente" },
    { label: "Pénalités évitées", value: <Counter value={k.avoided} className={k.avoided ? "text-ok" : ""} />, sub: k.atRisk ? `MAD · ${k.atRisk.toLocaleString("fr-FR")} à risque` : "MAD" },
    { label: "Carburant, 7 derniers jours", value: <Counter value={fuel?.spend_mad ?? 0} />, sub: fuel ? `MAD · +${fuel.overspend_mad.toLocaleString("fr-FR")} surcoût` : "MAD" },
  ];

  return (
    <header className="relative z-20 flex h-[78px] items-stretch border-b border-line bg-bg">
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
            {live ? "Connecté" : "Hors ligne"}
          </div>
        </div>
      </div>

      <div className="grid flex-1 grid-cols-4">
        {items.map((it, i) => (
          <motion.div
            key={it.label}
            className="relative flex min-w-0 flex-col justify-center gap-1 border-r border-line px-6 last:border-r-0"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EXPO, delay: 0.05 + i * 0.05 }}
          >
            <span className="text-[11.5px] text-muted">{it.label}</span>
            <div className="flex items-baseline gap-2">
              <span className="text-[24px] font-medium leading-none tracking-tight">{it.value}</span>
              <span className="truncate text-[11px] text-dim">{it.sub}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </header>
  );
}
