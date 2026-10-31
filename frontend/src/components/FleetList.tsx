import { motion } from "framer-motion";
import { useMemo } from "react";
import { Ambulance, Truck } from "lucide-react";
import { useStore } from "@/store";
import { cityName } from "@/lib/geo";
import { EXPO, StatusChip } from "./ui";

export function FleetList() {
  const vehicles = useStore((s) => s.vehicles);
  const missions = useStore((s) => s.missions);
  const health = useStore((s) => s.health);
  const selectedId = useStore((s) => s.selectedId);
  const hoverId = useStore((s) => s.hoverId);
  const open = useStore((s) => s.openInspector);
  const setHover = useStore((s) => s.setHover);

  const sorted = useMemo(() => {
    const rank = (id: string, status: string) => {
      if (status === "breakdown") return 0;
      const zones = Object.values(health[id]?.zones ?? {});
      return zones.some((z) => z.status === "fail") ? 1 : zones.some((z) => z.status === "warn") ? 2 : 3;
    };
    return vehicles.map((v, i) => ({ v, i, r: rank(v.id, v.status) })).sort((a, b) => a.r - b.r || a.i - b.i).map((x) => x.v);
  }, [vehicles, health]);

  return (
    <motion.aside
      className="flex w-[280px] shrink-0 flex-col border-r border-line bg-bg"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5, ease: EXPO }}
    >
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <span className="text-[13px] font-medium">Flotte</span>
        <span className="num text-[11px] text-dim">{vehicles.length} unités</span>
      </div>
      <ul className="flex-1 overflow-y-auto py-1">
        {sorted.map((v) => {
          const m = v.mission_id ? missions[v.mission_id] : undefined;
          const zones = health[v.id]?.zones;
          const alert = zones && Object.values(zones).some((z) => z.status === "fail")
            ? "fail" : zones && Object.values(zones).some((z) => z.status === "warn") ? "warn" : null;
          const Icon = v.type === "ambulance" ? Ambulance : Truck;
          const active = v.id === selectedId || v.id === hoverId;
          return (
            <motion.li
              key={v.id}
              layout="position"
              transition={{ duration: 0.35, ease: EXPO }}
            >
              <button
                onClick={() => open(v.id)}
                onMouseEnter={() => setHover(v.id)}
                onMouseLeave={() => setHover(null)}
                className={`group relative flex w-full items-center gap-3 px-5 py-2.5 text-left transition-colors duration-300 ${active ? "bg-panel" : "hover:bg-panel/60"}`}
              >
                <span className={`absolute left-0 top-0 h-full w-[2px] origin-top transition-transform duration-500 ease-[var(--ease-expo)] ${v.status === "breakdown" ? "bg-fail" : "bg-accent"} ${active || v.status === "breakdown" ? "scale-y-100" : "scale-y-0"}`} />
                <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border ${v.status === "breakdown" ? "border-fail/40 text-fail" : "border-line text-muted group-hover:text-ink"} transition-colors`}>
                  <Icon size={15} strokeWidth={1.6} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="num text-[13px] font-medium text-ink">{v.id}</span>
                    <StatusChip status={v.status} />
                  </span>
                  <span className="mt-0.5 block truncate text-[11.5px] text-muted">
                    {m ? <><span className="num text-dim">{m.id}</span> → {cityName(m.stops.at(-1)!.city)}</> : v.model}
                  </span>
                </span>
                {alert && (
                  <span className="relative h-2 w-2">
                    <span className={`absolute inset-0 rounded-full ${alert === "fail" ? "bg-fail" : "bg-warn"}`} />
                    {alert === "fail" && <span className="absolute inset-0 rounded-full bg-fail pulse-ring" />}
                  </span>
                )}
              </button>
            </motion.li>
          );
        })}
      </ul>
    </motion.aside>
  );
}
