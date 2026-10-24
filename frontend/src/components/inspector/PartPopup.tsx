import { motion } from "framer-motion";
import { CheckCircle2, MapPin, ShieldAlert, ShieldCheck, Truck, X } from "lucide-react";
import type { ReactNode } from "react";
import type { Incident, Severity, SupplierScore } from "@shared/types";
import type { ZoneHealth } from "@/api";
import { Bar, EXPO, mad } from "../ui";
import type { PickedPart } from "./Vehicle3D";

const ZONE_FR: Record<string, string> = {
  engine: "Moteur", cooling: "Refroidissement", electrical: "Électrique", brakes: "Freinage",
  transmission: "Transmission", tires: "Pneumatiques", fuel: "Carburant",
};

const SEVERITY: Record<Severity, { label: string; cls: string }> = {
  ok: { label: "OK", cls: "border-ok/40 bg-ok/10 text-ok" },
  monitor: { label: "Surveiller", cls: "border-warn/40 bg-warn/10 text-warn" },
  drive_to_depot: { label: "Rouler au dépôt", cls: "border-warn/50 bg-warn/15 text-warn" },
  stop_now: { label: "Arrêt immédiat", cls: "border-fail/50 bg-fail/15 text-fail" },
};

const item = {
  hidden: { opacity: 0, y: 14, filter: "blur(4px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.7, ease: EXPO } },
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <motion.section variants={item} className="border-t border-line px-5 py-4">
      <h4 className="tag mb-2.5">{title}</h4>
      {children}
    </motion.section>
  );
}

function SupplierTable({ inc }: { inc: Incident }) {
  const rows = [...inc.suppliers].sort((a, b) => b.score - a.score);
  if (!rows.length) return <p className="text-[12px] text-dim">Aucun classement fournisseur dans cet incident.</p>;
  const minPrice = Math.min(...rows.map((r) => r.price_mad));
  const minDelivery = Math.min(...rows.map((r) => r.delivery_hours));
  const maxWarranty = Math.max(...rows.map((r) => r.warranty_months));
  const kpis: [string, (r: SupplierScore) => number, (r: SupplierScore) => string][] = [
    ["Prix", (r) => minPrice / r.price_mad, (r) => mad(r.price_mad)],
    ["Délai", (r) => minDelivery / Math.max(r.delivery_hours, 0.5), (r) => `${r.delivery_hours} h`],
    ["Ponctualité", (r) => r.on_time_pct / 100, (r) => `${r.on_time_pct}%`],
    ["Garantie", (r) => r.warranty_months / maxWarranty, (r) => `${r.warranty_months} mois`],
    ["Note", (r) => r.rating / 5, (r) => r.rating.toFixed(1)],
  ];
  return (
    <div className="flex flex-col gap-2">
      {rows.map((r, i) => {
        const chosen = r.supplier_id === inc.chosen_supplier_id;
        return (
          <div key={r.supplier_id} className={`rounded-lg border p-3 ${chosen ? "border-accent/60 bg-accent/[0.06]" : "border-line bg-bg/40"}`}>
            <div className="mb-2 flex items-center gap-2">
              <span className="num text-[11px] text-dim">#{i + 1}</span>
              <span className="text-[12.5px] font-medium">{r.supplier_name}</span>
              {chosen && <span className="rounded-full bg-accent px-1.5 py-[1px] text-[9.5px] font-semibold uppercase text-bg">Choisi</span>}
              <span className="num ml-auto text-[12px] text-accent">{(r.score * (r.score <= 1 ? 100 : 1)).toFixed(0)}</span>
            </div>
            <div className="grid grid-cols-[64px_1fr_64px] items-center gap-x-2 gap-y-1">
              {kpis.map(([label, norm, fmt], k) => (
                <div key={label} className="contents">
                  <span className="text-[10.5px] text-muted">{label}</span>
                  <Bar value={norm(r)} color={chosen ? "var(--color-accent)" : "#475569"} delay={0.2 + k * 0.05 + i * 0.05} />
                  <span className="num text-right text-[10.5px] text-ink/80">{fmt(r)}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
      {inc.supplier_reason && <p className="mt-1 text-[12px] leading-relaxed text-muted">{inc.supplier_reason}</p>}
    </div>
  );
}

export function PartPopup({ part, zone, incident, onClose }: { part: PickedPart; zone: ZoneHealth | undefined; incident: Incident | undefined; onClose: () => void }) {
  const hasIncident = !!incident && incident.diagnosis.zone === part.zone;

  return (
    <motion.div
      initial={{ x: -40, opacity: 0, filter: "blur(10px)" }}
      animate={{ x: 0, opacity: 1, filter: "blur(0px)" }}
      exit={{ x: -30, opacity: 0, filter: "blur(10px)" }}
      transition={{ duration: 0.75, ease: EXPO }}
      className={`ticks absolute left-5 top-5 z-20 flex max-h-[calc(100%-40px)] flex-col overflow-hidden rounded-2xl border border-line bg-panel/95 shadow-2xl backdrop-blur-xl ${hasIncident ? "w-[400px]" : "w-[320px]"}`}
    >
      <motion.div className="overflow-y-auto" variants={{ show: { transition: { staggerChildren: 0.06, delayChildren: 0.15 } } }} initial="hidden" animate="show">
        <motion.header variants={item} className="relative px-5 pb-4 pt-5">
          <button onClick={onClose} className="absolute right-4 top-4 rounded-full p-1 text-dim hover:bg-line hover:text-ink"><X size={14} /></button>
          <div className="tag mb-1.5">{ZONE_FR[part.zone]} {part.part_id && <span className="num text-dim">· {part.part_id}</span>}</div>
          <h3 className="text-xl font-medium tracking-tight">{hasIncident ? incident.diagnosis.part_name : part.label_fr}</h3>
          {hasIncident ? (
            <div className="mt-3 flex items-center gap-3">
              <span className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${SEVERITY[incident.diagnosis.severity].cls}`}>
                {SEVERITY[incident.diagnosis.severity].label}
              </span>
              <div className="flex-1">
                <div className="mb-1 flex justify-between text-[10.5px] text-muted"><span>Confiance</span><span className="num text-ink">{Math.round(incident.diagnosis.confidence * 100)}%</span></div>
                <Bar value={incident.diagnosis.confidence} color="var(--color-fail)" delay={0.3} />
              </div>
            </div>
          ) : (
            <div className="mt-3 flex items-center gap-2 text-[12.5px] text-ok">
              <CheckCircle2 size={15} /> {zone?.status === "warn" ? <span className="text-warn">À surveiller</span> : "Aucun problème détecté"}
            </div>
          )}
        </motion.header>

        {!hasIncident && (
          <Section title="Signaux">
            {zone?.reasons.length ? (
              <ul className="space-y-1.5">{zone.reasons.map((r) => <li key={r} className="num text-[12px] text-ink/85">› {r}</li>)}</ul>
            ) : <p className="text-[12px] text-muted">Télémétrie dans les plages nominales.</p>}
          </Section>
        )}

        {hasIncident && (
          <>
            <Section title="Preuves de l'agent">
              <ul className="space-y-1.5">
                {incident.diagnosis.evidence.map((ev, i) => (
                  <motion.li key={i} variants={item} className="flex gap-2 text-[12.5px] leading-snug text-ink/90">
                    <span className="num mt-[1px] text-[10.5px] text-accent">{String(i + 1).padStart(2, "0")}</span>
                    <span className={/^[A-Z]\d{4}$/.test(ev) ? "num" : ""}>{ev}</span>
                  </motion.li>
                ))}
              </ul>
            </Section>

            <Section title="Proposition">
              <div className="flex items-center gap-3">
                <span className={`rounded-md px-2.5 py-1 text-[12px] font-semibold tracking-wide ${incident.decision.action === "replace" ? "bg-fail text-white" : "bg-warn text-bg"}`}>
                  {incident.decision.action === "replace" ? "REMPLACER" : "RÉPARER"}
                </span>
                <div className="num flex gap-4 text-[12.5px]">
                  <span>{mad(incident.decision.cost_mad)}</span>
                  <span className="text-muted">{incident.decision.downtime_hours} h d'arrêt</span>
                </div>
              </div>
              <p className="mt-2 text-[12.5px] leading-relaxed text-muted">{incident.decision.reason}</p>
            </Section>

            <Section title="Fournisseurs classés">
              <SupplierTable inc={incident} />
            </Section>

            {incident.driver_instruction && (
              <Section title="Instruction chauffeur">
                <div className="flex items-start gap-3">
                  <MapPin size={16} className="mt-0.5 text-accent" />
                  <div className="flex-1 text-[12.5px]">
                    <div className="font-medium">Dépôt {incident.driver_instruction.depot_city}</div>
                    <div className="num mt-0.5 text-muted">
                      {incident.driver_instruction.distance_km} km · ETA {incident.driver_instruction.eta_min} min
                      {incident.driver_instruction.replacement_vehicle_id && <> · relève <span className="text-accent">{incident.driver_instruction.replacement_vehicle_id}</span></>}
                    </div>
                    <p className="mt-1.5 leading-relaxed text-ink/80">{incident.driver_instruction.message}</p>
                  </div>
                </div>
              </Section>
            )}

            <Section title="Pénalité SLA">
              <div className={`flex items-start gap-3 rounded-lg border p-3 ${incident.penalty.at_risk ? (incident.penalty.mitigation ? "border-ok/40 bg-ok/[0.06]" : "border-warn/40 bg-warn/[0.06]") : "border-line"}`}>
                {incident.penalty.at_risk && !incident.penalty.mitigation ? <ShieldAlert size={16} className="text-warn" /> : <ShieldCheck size={16} className="text-ok" />}
                <div className="flex-1 text-[12.5px]">
                  <div className="flex items-baseline justify-between">
                    <span className="font-medium">
                      {!incident.penalty.at_risk ? "Aucune pénalité" : incident.penalty.mitigation ? "Pénalité évitée" : "Pénalité à risque"}
                    </span>
                    <span className={`num ${!incident.penalty.at_risk ? "text-muted" : incident.penalty.mitigation ? "text-ok line-through decoration-ok/60" : "text-warn"}`}>{mad(incident.penalty.amount_mad)}</span>
                  </div>
                  {incident.penalty.mitigation && (
                    <div className="mt-1 flex items-center gap-1.5 text-ok"><Truck size={13} /> pénalité évitée grâce à <span className="num">{incident.penalty.mitigation}</span></div>
                  )}
                  <p className="mt-1 text-muted">{incident.penalty.reason}</p>
                </div>
              </div>
            </Section>

            <Section title="Rapport envoyé à la société">
              <p className="whitespace-pre-line rounded-lg border border-line bg-bg/50 p-3 text-[12.5px] leading-relaxed text-ink/85">{incident.report_fr}</p>
            </Section>
          </>
        )}
      </motion.div>
    </motion.div>
  );
}
