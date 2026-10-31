import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";
import { useStore } from "@/store";
import { EXPO } from "./ui";

export function Toasts() {
  const toasts = useStore((s) => s.toasts);
  const dismiss = useStore((s) => s.dismissToast);
  const incidents = useStore((s) => s.incidents);
  const open = useStore((s) => s.openInspector);

  return (
    <div className="pointer-events-none fixed left-1/2 top-[94px] z-30 flex w-[380px] -translate-x-1/2 flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: -20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40 }}
            transition={{ duration: 0.7, ease: EXPO }}
            className="pointer-events-auto relative overflow-hidden rounded-xl border border-line bg-panel shadow-2xl"
          >
            <button
              className="flex w-full items-start gap-3 p-3.5 text-left"
              onClick={() => { const inc = incidents[t.id]; if (inc) open(inc.vehicle_id); dismiss(t.id); }}
            >
              <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent/15 text-accent">
                <AlertTriangle size={15} />
              </span>
              <span className="flex-1">
                <span className="block text-[13px] font-medium text-ink">{t.title}</span>
                <span className="mt-0.5 block text-[11.5px] text-muted">{t.sub}</span>
              </span>
            </button>
            <button onClick={() => dismiss(t.id)} className="absolute right-2 top-2 text-dim hover:text-ink"><X size={13} /></button>
            <motion.div className="h-[2px] bg-accent" initial={{ width: "100%" }} animate={{ width: "0%" }} transition={{ duration: 6.5, ease: "linear" }} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
