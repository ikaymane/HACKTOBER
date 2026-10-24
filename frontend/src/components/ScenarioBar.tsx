import { motion } from "framer-motion";
import { Play, RotateCcw } from "lucide-react";
import { useEffect } from "react";
import { useStore } from "@/store";
import { EXPO, Tag } from "./ui";

const SCENARIOS = [
  { id: 1, label: "Ambulance alternateur", vid: "A-03" },
  { id: 2, label: "Camion surchauffe", vid: "T-07" },
  { id: 3, label: "Carburant T-12", vid: "T-12" },
];

export function ScenarioBar() {
  const run = useStore((s) => s.runScenario);
  const reset = useStore((s) => s.reset);
  const running = useStore((s) => s.runningScenario);
  const inspectorOpen = useStore((s) => s.inspectorOpen);

  // 1 / 2 / 3 / R shortcuts on the dashboard
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (inspectorOpen || e.target instanceof HTMLInputElement) return;
      if (["1", "2", "3"].includes(e.key)) run(+e.key);
      if (e.key.toLowerCase() === "r") reset();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [run, reset, inspectorOpen]);

  return (
    <motion.footer
      className="relative z-20 flex h-14 items-center gap-3 border-t border-line bg-bg/85 px-5 backdrop-blur"
      initial={{ y: 30, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 1, ease: EXPO, delay: 0.4 }}
    >
      <Tag n="D">Scénarios</Tag>
      <div className="ml-3 flex gap-2">
        {SCENARIOS.map((s) => {
          const active = running === s.id;
          return (
            <button
              key={s.id}
              onClick={() => run(s.id)}
              className={`group relative flex items-center gap-2.5 overflow-hidden rounded-full border py-1.5 pl-1.5 pr-4 text-[12.5px] transition-colors duration-300 ${active ? "border-accent/60 text-ink" : "border-line text-muted hover:border-accent/40 hover:text-ink"}`}
            >
              <span className="absolute inset-0 origin-left scale-x-0 bg-accent/10 transition-transform duration-500 ease-[var(--ease-expo)] group-hover:scale-x-100" />
              {active && <span className="shimmer absolute inset-0" />}
              <span className={`num relative flex h-6 w-6 items-center justify-center rounded-full text-[11px] transition-colors ${active ? "bg-accent text-bg" : "bg-panel text-ink group-hover:bg-accent group-hover:text-bg"}`}>
                {active ? <Play size={10} fill="currentColor" /> : s.id}
              </span>
              <span className="relative">{s.label}</span>
              <span className="num relative text-[10.5px] text-dim">{s.vid}</span>
            </button>
          );
        })}
      </div>
      <button
        onClick={reset}
        className="group ml-auto flex items-center gap-2 rounded-full border border-line px-4 py-1.5 text-[12.5px] text-muted transition-colors hover:border-ink/30 hover:text-ink"
      >
        <RotateCcw size={13} className="transition-transform duration-500 group-hover:-rotate-180" /> Reset
      </button>
      <span className="tag hidden xl:inline">Raccourcis 1 · 2 · 3 · R</span>
    </motion.footer>
  );
}
