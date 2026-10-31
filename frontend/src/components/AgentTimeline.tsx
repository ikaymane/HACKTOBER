import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight, X } from "lucide-react";
import { memo, useEffect, useRef, useState } from "react";
import type { AgentEvent, AgentName } from "@shared/types";
import { useStore } from "@/store";
import { EXPO } from "./ui";

export const AGENT_COLOR: Record<AgentName, string> = {
  maintenance: "#22D3EE",
  fuel: "#A3E635",
  delay: "#C084FC",
  orchestrator: "#F472B6",
  system: "#94A3B8",
};

const KIND_LABEL: Record<AgentEvent["kind"], string> = {
  thought: "raisonnement", tool_call: "outil", tool_result: "résultat", decision: "décision",
  alert: "alerte", handoff: "relais", message: "message",
};

const EventRow = memo(function EventRow({ ev }: { ev: AgentEvent }) {
  const [open, setOpen] = useState(false);
  const color = AGENT_COLOR[ev.agent];
  const collapsible = ev.kind === "tool_call" || ev.kind === "tool_result";
  const isDecision = ev.kind === "decision";
  const body = ev.kind === "tool_call" ? JSON.stringify(ev.data?.args ?? ev.data, null, 1) : ev.detail;
  const openIncident = useStore((s) => s.openInspector);

  return (
    <motion.li
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EXPO }}
      className="relative pl-6"
    >
      <span className="absolute left-[7px] top-0 h-full w-px bg-line" />
      <span
        className="absolute left-[3px] top-[13px] h-[9px] w-[9px] rounded-full border-2"
        style={{ borderColor: color, background: isDecision ? color : "var(--color-bg)", boxShadow: isDecision ? `0 0 12px ${color}` : undefined }}
      />
      <div
        className={`mb-2 rounded-lg border px-3 py-2.5 transition-colors ${isDecision ? "border-transparent" : "border-line/70 bg-panel/40"}`}
        style={isDecision ? { background: `linear-gradient(135deg, ${color}1f, transparent 70%)`, borderColor: `${color}55` } : undefined}
      >
        <div className="flex items-center gap-2 text-[10.5px]">
          <span className="num font-medium uppercase tracking-wider" style={{ color }}>{ev.agent}</span>
          <span className="text-dim">·</span>
          <span className="text-dim">{KIND_LABEL[ev.kind]}</span>
          {ev.vehicle_id && (
            <button onClick={() => openIncident(ev.vehicle_id!)} className="num rounded border border-line px-1 text-muted hover:border-accent/50 hover:text-accent">
              {ev.vehicle_id}
            </button>
          )}
          <span className="num ml-auto text-dim">{ev.ts.slice(11, 19)}</span>
        </div>
        <button
          disabled={!collapsible}
          onClick={() => setOpen((o) => !o)}
          className="mt-1 flex w-full items-start gap-1 text-left"
        >
          {collapsible && (
            <ChevronRight size={13} className={`mt-[3px] shrink-0 text-dim transition-transform duration-300 ${open ? "rotate-90" : ""}`} />
          )}
          <span className={`text-[13px] leading-snug ${isDecision ? "font-medium text-ink" : "text-ink/90"} ${ev.kind === "tool_call" ? "num text-[12px]" : ""}`}>
            {ev.title}
          </span>
        </button>
        <AnimatePresence initial={false}>
          {(!collapsible && ev.detail) || (collapsible && open && body) ? (
            <motion.pre
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.5, ease: EXPO }}
              className={`overflow-hidden whitespace-pre-wrap break-words text-[11.5px] leading-relaxed text-muted ${collapsible ? "num mt-1.5 max-h-40 overflow-y-auto rounded bg-bg/70 p-2" : "mt-1 font-sans"}`}
            >
              {body}
            </motion.pre>
          ) : null}
        </AnimatePresence>
      </div>
    </motion.li>
  );
});

export function AgentTimeline() {
  const events = useStore((s) => s.events);
  const running = useStore((s) => s.runningScenario);
  const close = useStore((s) => s.toggleAudit);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [events.length]);

  return (
    <motion.aside
      className="absolute inset-y-0 right-0 z-20 flex w-[380px] flex-col border-l border-line bg-bg shadow-2xl"
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ duration: 0.4, ease: EXPO }}
    >
      <div className="flex items-center justify-between border-b border-line px-5 py-3">
        <span className="text-[13px] font-medium">Journal d'audit</span>
        <button onClick={close} className="rounded-full p-1 text-dim hover:bg-line hover:text-ink"><X size={14} /></button>
      </div>
      {running && (
        <div className="relative h-px overflow-hidden bg-line">
          <div className="shimmer absolute inset-0" />
        </div>
      )}
      <div ref={scroller} className="flex-1 overflow-y-auto px-4 py-4">
        {events.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <div className="relative h-10 w-10">
              <span className="absolute inset-0 rounded-full border border-accent/40 pulse-ring" />
              <span className="absolute inset-3 rounded-full bg-accent/60" />
            </div>
            <p className="max-w-[220px] text-[12.5px] leading-relaxed text-muted">
              Chaque outil, résultat, décision et approbation sera enregistré ici.
            </p>
          </div>
        ) : (
          <ul>
            {events.map((ev) => <EventRow key={ev.id} ev={ev} />)}
          </ul>
        )}
      </div>
    </motion.aside>
  );
}
