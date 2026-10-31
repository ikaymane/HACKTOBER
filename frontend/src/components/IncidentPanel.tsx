import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Box, Check, Loader2, ShieldCheck } from "lucide-react";
import { useMemo } from "react";
import type { AgentEvent, AgentName, Incident } from "@shared/types";
import { useStore } from "@/store";
import { EXPO, SEVERITY, mad } from "./ui";

const FUEL_FLAG: Record<string, string> = {
  overconsumption: "Surconsommation carburant", fill_over_capacity: "Plein supérieur au réservoir", fill_without_km: "Plein sans kilomètres",
  excessive_idle: "Ralenti excessif",
};

const STEPS: { agent: AgentName; label: string }[] = [
  { agent: "maintenance", label: "Diagnostic et pièce" },
  { agent: "fuel", label: "Carburant et trajet" },
  { agent: "delay", label: "Livraison et retards" },
  { agent: "orchestrator", label: "Plan final" },
];

/** What the agents are doing, in the manager's words. The raw trace stays in the audit log. */
function Progress({ events }: { events: AgentEvent[] }) {
  const start = events.findLastIndex((e) => e.agent === "system" && e.kind === "alert" && e.data?.scenario_id != null);
  const run = events.slice(Math.max(start, 0));
  return (
    <div className="rounded-xl border border-accent/30 bg-panel p-4">
      <div className="mb-3 text-[13px] font-medium">Analyse de la panne</div>
      <ul className="space-y-2">
        {STEPS.map(({ agent, label }) => {
          const done = run.some((e) => e.agent === agent && e.kind === "decision");
          const active = !done && run.some((e) => e.agent === agent);
          return (
            <li key={agent} className={`flex items-center gap-2.5 text-[12.5px] transition-colors duration-300 ${done ? "text-ink" : active ? "text-accent" : "text-dim"}`}>
              {done ? <Check size={14} className="text-ok" /> : active ? <Loader2 size={14} className="animate-spin" /> : <span className="mx-[3px] h-2 w-2 rounded-full border border-dim" />}
              {label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function fleetMove(inc: Incident) {
  if (inc.takeover_vehicle_id) return `${inc.takeover_vehicle_id} reprend la charge`;
  const di = inc.driver_instruction;
  if (di?.replacement_vehicle_id) return `${di.replacement_vehicle_id} remplace · ${Math.round(di.eta_min)} min`;
  return di ? `Direction dépôt ${di.depot_city}` : "Aucun véhicule à déplacer";
}

function Fact({ label, value, tone = "" }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <div className="text-[10.5px] text-dim">{label}</div>
      <div className={`num mt-0.5 text-[13px] ${tone}`}>{value}</div>
    </div>
  );
}

function IncidentCard({ inc, final }: { inc: Incident; final: AgentEvent | undefined }) {
  const approve = useStore((s) => s.approve);
  const open = useStore((s) => s.openInspector);
  const sev = SEVERITY[inc.diagnosis.severity];
  const actions = (final?.data?.next_actions as string[] | undefined) ?? [];
  const penalty = inc.penalty.avoided_mad > 0
    ? { label: "Pénalité évitée", value: mad(inc.penalty.avoided_mad), tone: "text-ok" }
    : inc.penalty.at_risk
      ? { label: "Pénalité à risque", value: mad(inc.penalty.amount_mad), tone: "text-warn" }
      : { label: "Pénalité", value: "Aucune", tone: "text-muted" };

  return (
    <motion.article
      layout="position"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EXPO }}
      className="rounded-xl border border-fail/30 bg-panel p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <AlertTriangle size={14} className="text-fail" />
            <span className="num text-[14px] font-semibold">{inc.vehicle_id}</span>
          </div>
          <h3 className="mt-1 text-[15px] font-medium leading-tight">{inc.diagnosis.part_name}</h3>
        </div>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-medium ${sev.cls}`}>{sev.label}</span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-line pt-3">
        <Fact label="Décision" value={inc.decision.action === "replace" ? "Remplacer" : "Réparer"} />
        <Fact label="Coût" value={mad(inc.decision.cost_mad)} />
        <Fact label="Arrêt" value={`${inc.decision.downtime_hours} h`} />
      </div>
      <div className="mt-2.5 grid grid-cols-[1fr_auto] gap-2">
        <Fact label="Flotte" value={fleetMove(inc)} />
        <div className="text-right"><Fact label={penalty.label} value={penalty.value} tone={penalty.tone} /></div>
      </div>

      {actions.length > 0 && (
        <ol className="mt-3 space-y-1 border-t border-line pt-3 text-[12px] leading-snug text-ink/85">
          {actions.slice(0, 3).map((a, i) => (
            <li key={i} className="flex gap-2"><span className="num text-accent">{i + 1}</span><span>{a}</span></li>
          ))}
        </ol>
      )}

      <div className="mt-3 flex gap-2">
        {final && (
          <button
            data-approve
            disabled={inc.approved}
            onClick={() => approve(inc.id)}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-md border py-2 text-[12.5px] font-medium transition-colors ${inc.approved ? "border-ok/40 bg-ok/10 text-ok" : "border-accent bg-accent text-bg hover:bg-accent/85"}`}
          >
            {inc.approved && <ShieldCheck size={14} />} {inc.approved ? "Plan approuvé" : "Approuver le plan"}
          </button>
        )}
        <button
          onClick={() => open(inc.vehicle_id)}
          className={`flex items-center justify-center gap-1.5 rounded-md border border-line px-3 py-2 text-[12.5px] text-muted transition-colors hover:border-accent/50 hover:text-ink ${final ? "" : "flex-1"}`}
        >
          <Box size={14} /> Voir la pièce
        </button>
      </div>
    </motion.article>
  );
}

/** The manager's view: what's wrong, what to do, what it costs. Nothing to read when nothing needs attention. */
export function IncidentPanel() {
  const incidents = useStore((s) => s.incidents);
  const events = useStore((s) => s.events);
  const running = useStore((s) => s.runningScenario);
  const health = useStore((s) => s.health);
  const vehicles = useStore((s) => s.vehicles);
  const open = useStore((s) => s.openInspector);
  const flags = useStore((s) => s.fuelKpi?.flags);

  const list = useMemo(() => Object.values(incidents).reverse(), [incidents]);
  const finals = useMemo(
    () => Object.fromEntries(events.filter((e) => e.agent === "orchestrator" && e.kind === "decision").map((e) => [e.data?.incident_id as string, e])),
    [events],
  );
  const watch = useMemo(() => vehicles.flatMap((v) => {
    if (v.status === "breakdown") return [];
    const fuelFlag = flags?.find((f) => f.vehicle_id === v.id);
    if (fuelFlag) return [{ id: v.id, reason: FUEL_FLAG[fuelFlag.kind] ?? "Alerte carburant" }];
    const zone = Object.values(health[v.id]?.zones ?? {}).find((z) => z.status !== "ok");
    return zone ? [{ id: v.id, reason: zone.reasons[0] ?? "À vérifier" }] : [];
  }), [vehicles, health, flags]);

  return (
    <div className="pointer-events-none absolute bottom-4 right-4 top-4 z-10 flex w-[340px] flex-col gap-3 overflow-y-auto">
      <AnimatePresence initial={false}>
        {running != null && (
          <motion.div key="progress" className="pointer-events-auto" initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }}>
            <Progress events={events} />
          </motion.div>
        )}
      </AnimatePresence>
      {list.map((inc) => <div key={inc.id} className="pointer-events-auto"><IncidentCard inc={inc} final={finals[inc.id]} /></div>)}
      {watch.length > 0 && (
        <div className="pointer-events-auto mt-auto rounded-xl border border-line bg-panel p-3">
          <div className="mb-2 text-[12px] font-medium text-muted">À surveiller</div>
          <ul className="space-y-0.5">
            {watch.map((w) => (
              <li key={w.id}>
                <button onClick={() => open(w.id)} className="flex w-full items-center gap-2 rounded px-1.5 py-1 text-left transition-colors hover:bg-line/60">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-warn" />
                  <span className="num text-[12px]">{w.id}</span>
                  <span className="truncate text-[11.5px] text-muted">{w.reason}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
