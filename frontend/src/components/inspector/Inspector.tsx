import { AnimatePresence, motion } from "framer-motion";
import { Boxes, ChevronLeft, ChevronRight, Fuel, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { Zone } from "@shared/types";
import { api, type ZoneStatus } from "@/api";
import { incidentForVehicle, useStore } from "@/store";
import { cityName } from "@/lib/geo";
import { EXPO, HEALTH_COLOR, HealthChip, Scramble, Tag } from "../ui";
import { FuelDrawer } from "./FuelDrawer";
import { PartPopup } from "./PartPopup";
import { Vehicle3D, type PickedPart } from "./Vehicle3D";

const ZONES: { zone: Zone; label: string }[] = [
  { zone: "engine", label: "Moteur" },
  { zone: "cooling", label: "Refroidissement" },
  { zone: "electrical", label: "Électrique" },
  { zone: "brakes", label: "Freins" },
  { zone: "transmission", label: "Transmission" },
  { zone: "tires", label: "Pneus" },
  { zone: "fuel", label: "Carburant" },
];

export default function Inspector() {
  const vehicles = useStore((s) => s.vehicles);
  const selectedId = useStore((s) => s.selectedId);
  const missions = useStore((s) => s.missions);
  const incidents = useStore((s) => s.incidents);
  const healthMap = useStore((s) => s.health);
  const close = useStore((s) => s.closeInspector);
  const step = useStore((s) => s.step);
  const refetchHealth = useStore((s) => s.refetchHealth);

  const vehicle = vehicles.find((v) => v.id === selectedId);
  const mission = vehicle?.mission_id ? missions[vehicle.mission_id] : undefined;
  const health = vehicle ? healthMap[vehicle.id] : undefined;
  const incident = vehicle ? incidentForVehicle(incidents, vehicle.id) : undefined;

  const [exploded, setExploded] = useState(false);
  const [picked, setPicked] = useState<PickedPart | null>(null);
  const [fuelOpen, setFuelOpen] = useState(false);
  const [dir, setDir] = useState(1);

  // Per vehicle: refresh health, auto-explode + open the failed part on incidents, open fuel on anomalies.
  useEffect(() => {
    if (!vehicle) return;
    refetchHealth(vehicle.id);
    setExploded(!!incident);
    setPicked(incident ? { zone: incident.diagnosis.zone, part_id: incident.diagnosis.part_id, label_fr: incident.diagnosis.part_name } : null);
    setFuelOpen(false);
    let alive = true;
    api.fuel(vehicle).then((f) => alive && f.anomalies.length > 0 && setFuelOpen(true)).catch(() => {});
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vehicle?.id, incident?.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") { setDir(1); step(1); }
      else if (e.key === "ArrowLeft") { setDir(-1); step(-1); }
      else if (e.key === "Escape") { if (picked) setPicked(null); else close(); }
      else if (e.key.toLowerCase() === "e") setExploded((x) => !x);
      else if (e.key.toLowerCase() === "f") setFuelOpen((x) => !x);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, close, picked]);

  const overall: ZoneStatus = useMemo(() => {
    const st = health ? Object.values(health.zones).map((z) => z.status) : [];
    return st.includes("fail") ? "fail" : st.includes("warn") ? "warn" : "ok";
  }, [health]);

  if (!vehicle) return null;
  const idx = vehicles.findIndex((v) => v.id === vehicle.id);

  return (
    <motion.div
      className="fixed inset-0 z-40 flex flex-col bg-bg"
      initial={{ clipPath: "inset(50% 0% 50% 0%)", opacity: 0.4 }}
      animate={{ clipPath: "inset(0% 0% 0% 0%)", opacity: 1 }}
      exit={{ clipPath: "inset(50% 0% 50% 0%)", opacity: 0 }}
      transition={{ duration: 0.55, ease: EXPO }}
    >
      {/* Header */}
      <header className="relative z-30 flex h-[72px] shrink-0 items-center gap-4 border-b border-line px-5">
        <div className="flex items-center gap-1">
          <button onClick={() => { setDir(-1); step(-1); }} className="flex h-9 w-9 items-center justify-center rounded-full border border-line text-muted transition-colors hover:border-accent/50 hover:text-accent" title="Précédent (←)">
            <ChevronLeft size={16} />
          </button>
          <button onClick={() => { setDir(1); step(1); }} className="flex h-9 w-9 items-center justify-center rounded-full border border-line text-muted transition-colors hover:border-accent/50 hover:text-accent" title="Suivant (→)">
            <ChevronRight size={16} />
          </button>
          <span className="num ml-2 text-[11px] text-dim">{String(idx + 1).padStart(2, "0")}/{String(vehicles.length).padStart(2, "0")}</span>
        </div>

        <div className="min-w-0 flex-1 overflow-hidden">
          <AnimatePresence mode="popLayout" initial={false} custom={dir}>
            <motion.div
              key={vehicle.id}
              custom={dir}
              initial={{ y: dir * 24, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -dir * 24, opacity: 0 }}
              transition={{ duration: 0.6, ease: EXPO }}
              className="flex items-center gap-3 whitespace-nowrap text-[14px]"
            >
              <Scramble text={vehicle.id} className="text-[20px] font-semibold text-ink" />
              <span className="text-dim">·</span>
              <span className="font-medium">{vehicle.model}</span>
              <span className="text-dim">·</span>
              <span className="num text-muted">{vehicle.plate}</span>
              <span className="text-dim">·</span>
              <span className="text-muted">{vehicle.driver}</span>
              {mission && (
                <>
                  <span className="text-dim">·</span>
                  <span className="text-muted">mission <span className="num text-ink">{mission.id}</span> → {cityName(mission.stops.at(-1)!.city)}</span>
                </>
              )}
              <HealthChip status={overall} />
            </motion.div>
          </AnimatePresence>
        </div>

        <button
          onClick={() => setExploded((x) => !x)}
          className={`flex items-center gap-2 rounded-full border px-4 py-2 text-[12.5px] transition-all duration-300 ${exploded ? "border-accent bg-accent text-bg" : "border-line text-muted hover:border-accent/50 hover:text-ink"}`}
        >
          <Boxes size={14} /> Vue éclatée <span className="num text-[10px] opacity-60">E</span>
        </button>
        <button
          onClick={() => setFuelOpen((x) => !x)}
          className={`flex items-center gap-2 rounded-full border px-4 py-2 text-[12.5px] transition-all duration-300 ${fuelOpen ? "border-accent/60 text-accent" : "border-line text-muted hover:border-accent/50 hover:text-ink"}`}
        >
          <Fuel size={14} /> Carburant <span className="num text-[10px] opacity-60">F</span>
        </button>
        <button onClick={close} className="flex h-9 w-9 items-center justify-center rounded-full border border-line text-muted transition-colors hover:border-ink/40 hover:text-ink" title="Fermer (Esc)">
          <X size={16} />
        </button>
      </header>

      {/* Stage */}
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className="grid-bg pointer-events-none absolute inset-0 opacity-50 [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_75%)]" />
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_60%,rgba(34,211,238,0.07),transparent_60%)]" />

        <div className="absolute inset-0">
          <Vehicle3D
            type={vehicle.type}
            health={health}
            failedPartId={incident?.diagnosis.part_id ?? null}
            failedPartName={incident?.diagnosis.part_name ?? null}
            insetX={(picked ? (incident && incident.diagnosis.zone === picked.zone ? 210 : 170) : 0) - (fuelOpen ? 210 : 0)}
            exploded={exploded}
            selected={picked}
            onPick={setPicked}
            vehicleKey={vehicle.id}
          />
        </div>

        <AnimatePresence>
          {picked && (
            <PartPopup
              key={`${vehicle.id}-${picked.zone}-${picked.part_id}`}
              part={picked}
              zone={health?.zones[picked.zone]}
              incident={incident}
              onClose={() => setPicked(null)}
            />
          )}
        </AnimatePresence>

        <AnimatePresence>
          {fuelOpen && <FuelDrawer key={`fuel-${vehicle.id}`} vehicle={vehicle} mission={mission} onClose={() => setFuelOpen(false)} />}
        </AnimatePresence>

        {/* Zone legend */}
        <motion.div
          className="absolute bottom-5 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1 rounded-full border border-line bg-bg/90 p-1"
          initial={{ y: 30, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.9, ease: EXPO, delay: 0.5 }}
          style={{ marginLeft: fuelOpen ? -210 : 0 }}
        >
          <span className="px-3"><Tag>Zones</Tag></span>
          {ZONES.map(({ zone, label }) => {
            const st = health?.zones[zone]?.status ?? "ok";
            const active = picked?.zone === zone;
            return (
              <button
                key={zone}
                onClick={() => {
                  const z = health?.zones[zone];
                  setPicked({ zone, part_id: z?.part_id ?? "", label_fr: label });
                  if (st !== "ok") setExploded(true);
                }}
                className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11.5px] transition-colors ${active ? "bg-panel text-ink" : "text-muted hover:text-ink"}`}
              >
                <span className="relative h-2 w-2 rounded-full" style={{ background: HEALTH_COLOR[st] }}>
                  {st === "fail" && <span className="pulse-ring absolute inset-0 rounded-full bg-fail" />}
                </span>
                {label}
              </button>
            );
          })}
        </motion.div>

        <div className="pointer-events-none absolute right-5 top-5 z-10 flex flex-col items-end gap-1 text-right" style={{ right: fuelOpen ? 440 : 20 }}>
          <span className="tag">Glisser pour orbiter · clic sur une pièce</span>
          <span className="tag text-dim">← → véhicule · E éclaté · F carburant · Esc</span>
        </div>
      </div>
    </motion.div>
  );
}
