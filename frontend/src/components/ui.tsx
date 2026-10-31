import { animate, motion, useInView, useMotionValue, useTransform } from "framer-motion";
import { useEffect, useRef, type ReactNode } from "react";
import type { Severity, VehicleStatus } from "@shared/types";
import type { ZoneStatus } from "@/api";

export const EXPO = [0.16, 1, 0.3, 1] as const;
export const QUART = [0.76, 0, 0.24, 1] as const;

/** Number that rolls to its value (counts up on mount, eases between updates). */
export function Counter({ value, decimals = 0, className = "" }: { value: number; decimals?: number; className?: string }) {
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) =>
    v.toLocaleString("fr-FR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }),
  );
  useEffect(() => {
    const c = animate(mv, value, { duration: 1.4, ease: EXPO });
    return c.stop;
  }, [value, mv]);
  return <motion.span className={`num ${className}`}>{text}</motion.span>;
}

/** Text that slides up from behind a mask, word by word (discovermarket-style headline reveal). */
export function Reveal({ text, delay = 0, className = "", stagger = 0.045 }: { text: string; delay?: number; className?: string; stagger?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  return (
    <span ref={ref} className={`inline-flex flex-wrap ${className}`} aria-label={text}>
      {text.split(" ").map((w, i) => (
        <span key={i} className="overflow-hidden inline-block pb-[0.08em] -mb-[0.08em]" aria-hidden>
          <motion.span
            className="inline-block"
            initial={{ y: "110%" }}
            animate={inView ? { y: "0%" } : undefined}
            transition={{ duration: 0.9, ease: EXPO, delay: delay + i * stagger }}
          >
            {w}&nbsp;
          </motion.span>
        </span>
      ))}
    </span>
  );
}

/** Characters that scramble before resolving: used on ids and live numbers. */
export function Scramble({ text, className = "" }: { text: string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const glyphs = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789-·";
    let frame = 0;
    const total = 14;
    const id = setInterval(() => {
      frame++;
      el.textContent = text
        .split("")
        .map((ch, i) => (ch === " " || i < (frame / total) * text.length ? ch : glyphs[Math.floor(Math.random() * glyphs.length)]))
        .join("");
      if (frame >= total) clearInterval(id);
    }, 28);
    return () => clearInterval(id);
  }, [text]);
  return <span ref={ref} className={`num ${className}`}>{text}</span>;
}

const STATUS: Record<VehicleStatus, { label: string; cls: string; dot: string }> = {
  on_mission: { label: "En mission", cls: "text-accent border-accent/30 bg-accent/5", dot: "bg-accent" },
  available: { label: "Disponible", cls: "text-ok border-ok/30 bg-ok/5", dot: "bg-ok" },
  breakdown: { label: "Panne", cls: "text-fail border-fail/40 bg-fail/10", dot: "bg-fail" },
  maintenance: { label: "Atelier", cls: "text-warn border-warn/30 bg-warn/5", dot: "bg-warn" },
};

export function StatusChip({ status }: { status: VehicleStatus }) {
  const s = STATUS[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-[1px] text-[10.5px] font-medium ${s.cls}`}>
      <span className={`relative h-1.5 w-1.5 rounded-full ${s.dot}`}>
        {status === "breakdown" && <span className={`absolute inset-0 rounded-full ${s.dot} pulse-ring`} />}
      </span>
      {s.label}
    </span>
  );
}

export const HEALTH_COLOR: Record<ZoneStatus, string> = { ok: "#64748B", warn: "#F59E0B", fail: "#EF4444" };

export function HealthChip({ status }: { status: ZoneStatus }) {
  const label = { ok: "Sain", warn: "À surveiller", fail: "Défaillance" }[status];
  const cls = { ok: "text-ok border-ok/30 bg-ok/5", warn: "text-warn border-warn/30 bg-warn/10", fail: "text-fail border-fail/40 bg-fail/10" }[status];
  return <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${cls}`}>{label}</span>;
}

export function Tag({ n, children }: { n?: string; children: ReactNode }) {
  return (
    <span className="tag">
      {n && <span className="text-accent/80">[{n}]</span>} {children}
    </span>
  );
}

/** Thin progress bar that grows from 0. */
export function Bar({ value, color = "var(--color-accent)", delay = 0 }: { value: number; color?: string; delay?: number }) {
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-line">
      <motion.div
        className="h-full rounded-full"
        style={{ background: color }}
        initial={{ width: 0 }}
        animate={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
        transition={{ duration: 1.1, ease: EXPO, delay }}
      />
    </div>
  );
}

export const SEVERITY: Record<Severity, { label: string; cls: string }> = {
  ok: { label: "OK", cls: "border-ok/40 bg-ok/10 text-ok" },
  monitor: { label: "Surveiller", cls: "border-warn/40 bg-warn/10 text-warn" },
  drive_to_depot: { label: "Rouler au dépôt", cls: "border-warn/50 bg-warn/15 text-warn" },
  stop_now: { label: "Arrêt immédiat", cls: "border-fail/50 bg-fail/15 text-fail" },
};

export const mad = (n: number) => `${Math.round(n).toLocaleString("fr-FR")} MAD`;
