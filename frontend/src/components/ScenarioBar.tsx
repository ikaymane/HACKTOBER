import { motion } from "framer-motion";
import { FileClock, Play, RotateCcw } from "lucide-react";
import { useEffect } from "react";
import { useStore } from "@/store";
import { EXPO } from "./ui";

const SCENARIOS = [
  { id: 1, label: "Ambulance · alternateur", vid: "A-03" },
  { id: 2, label: "Camion · surchauffe", vid: "T-07" },
  { id: 3, label: "Camion · surconsommation", vid: "T-12" },
];

export function ScenarioBar() {
  const run = useStore((s) => s.runScenario);
  const reset = useStore((s) => s.reset);
  const running = useStore((s) => s.runningScenario);
  const inspectorOpen = useStore((s) => s.inspectorOpen);
  const auditOpen = useStore((s) => s.auditOpen);
  const toggleAudit = useStore((s) => s.toggleAudit);
  const eventCount = useStore((s) => s.events.length);

  // 1 / 2 / 3 / R / J shortcuts on the dashboard
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (inspectorOpen || e.target instanceof HTMLInputElement) return;
      if (["1", "2", "3"].includes(e.key)) run(+e.key);
      if (e.key.toLowerCase() === "r") reset();
      if (e.key.toLowerCase() === "j") toggleAudit();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [run, reset, toggleAudit, inspectorOpen]);

  return (
    <motion.footer
      className="relative z-20 flex h-14 items-center gap-3 border-t border-line bg-bg px-5"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5, ease: EXPO, delay: 0.2 }}
    >
      <span className="text-[12px] text-muted">Simuler une panne</span>
      <div className="ml-1 flex gap-2">
        {SCENARIOS.map((s) => {
          const active = running === s.id;
          return (
            <button
              key={s.id}
              onClick={() => run(s.id)}
              className={`flex items-center gap-2 rounded-full border py-1.5 pl-1.5 pr-3.5 text-[12.5px] transition-colors duration-200 ${active ? "border-accent/60 text-ink" : "border-line text-muted hover:border-accent/40 hover:text-ink"}`}
            >
              <span className={`num flex h-6 w-6 items-center justify-center rounded-full text-[11px] ${active ? "bg-accent text-bg" : "bg-panel text-ink"}`}>
                {active ? <Play size={10} fill="currentColor" /> : s.id}
              </span>
              {s.label}
            </button>
          );
        })}
      </div>
      <button
        onClick={toggleAudit}
        className={`ml-auto flex items-center gap-2 rounded-full border px-4 py-1.5 text-[12.5px] transition-colors ${auditOpen ? "border-accent/60 text-accent" : "border-line text-muted hover:border-accent/40 hover:text-ink"}`}
      >
        <FileClock size={13} /> Journal d'audit {eventCount > 0 && <span className="num text-[11px] text-dim">{eventCount}</span>}
      </button>
      <button
        onClick={reset}
        className="flex items-center gap-2 rounded-full border border-line px-4 py-1.5 text-[12.5px] text-muted transition-colors hover:border-ink/30 hover:text-ink"
      >
        <RotateCcw size={13} /> Réinitialiser
      </button>
    </motion.footer>
  );
}
