import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import { useEffect, useState } from "react";
import { EXPO, QUART, Reveal } from "./ui";

/** Intro: logo stroke-draws, counter runs to 100, then the panel lifts off like a curtain. */
export function Preloader({ ready, onLeave, onDone }: { ready: boolean; onLeave: () => void; onDone: () => void }) {
  const p = useMotionValue(0);
  const pct = useTransform(p, (v) => String(Math.round(v)).padStart(3, "0"));
  const width = useTransform(p, (v) => `${v}%`);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const a = animate(p, ready ? 100 : 82, { duration: ready ? 0.9 : 2.2, ease: ready ? EXPO : [0.3, 0, 0.2, 1] });
    if (ready) a.then(() => setTimeout(() => { setLeaving(true); onLeave(); }, 250));
    return a.stop;
  }, [ready, p, onLeave]);

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex flex-col justify-between bg-bg px-10 py-9 grid-bg"
      initial={{ clipPath: "inset(0% 0% 0% 0%)" }}
      animate={leaving ? { clipPath: "inset(0% 0% 100% 0%)" } : undefined}
      transition={{ duration: 1.1, ease: QUART }}
      onAnimationComplete={() => leaving && onDone()}
    >
      <div className="flex items-center justify-between">
        <span className="tag">FleetSense · Ops room</span>
        <span className="tag">Maroc · 16 véhicules</span>
      </div>

      <div className="flex flex-col items-center gap-8">
        <svg width="84" height="84" viewBox="0 0 84 84" fill="none">
          <motion.rect x="2" y="2" width="80" height="80" rx="18" stroke="#1F2A37" strokeWidth="1.5"
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.4, ease: EXPO }} />
          <motion.path d="M24 60V24h30M24 42h22" stroke="#22D3EE" strokeWidth="5" strokeLinecap="round"
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.3, ease: EXPO, delay: 0.25 }} />
          <motion.circle cx="58" cy="57" r="6" fill="#22D3EE"
            initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ duration: 0.8, ease: EXPO, delay: 1 }} />
        </svg>
        <h1 className="text-center text-5xl font-medium tracking-[-0.03em] text-ink">
          <Reveal text="Chaque véhicule." delay={0.3} />
          <br />
          <span className="text-muted"><Reveal text="Chaque panne. Décidée." delay={0.55} /></span>
        </h1>
      </div>

      <div className="flex items-end justify-between">
        <div className="w-64">
          <div className="tag mb-2">Connexion aux agents</div>
          <div className="h-px w-full bg-line">
            <motion.div className="h-px bg-accent" style={{ width }} />
          </div>
        </div>
        <motion.span className="num text-7xl font-light text-ink/90">{pct}</motion.span>
      </div>
    </motion.div>
  );
}
