import { AnimatePresence } from "framer-motion";
import { lazy, Suspense, useEffect, useState } from "react";
import { useStore } from "@/store";
import { Preloader } from "@/components/Preloader";
import { KpiBar } from "@/components/KpiBar";
import { FleetList } from "@/components/FleetList";
import { AgentTimeline } from "@/components/AgentTimeline";
import { IncidentPanel } from "@/components/IncidentPanel";
import { ScenarioBar } from "@/components/ScenarioBar";
import { Toasts } from "@/components/Toasts";
import { FleetMap } from "@/components/map/FleetMap";

const loadInspector = () => import("@/components/inspector/Inspector");
const Inspector = lazy(loadInspector);

export default function App() {
  const boot = useStore((s) => s.boot);
  const inspectorOpen = useStore((s) => s.inspectorOpen);
  const auditOpen = useStore((s) => s.auditOpen);
  const [ready, setReady] = useState(false);
  const [intro, setIntro] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const minTime = new Promise((r) => setTimeout(r, 900));
    Promise.all([boot(), minTime])
      .then(() => setReady(true))
      .catch((e) => { setError(String(e)); setReady(true); });
  }, [boot]);

  // Fetch the 3D inspector and its models once the map has settled, so the first click opens it straight away.
  useEffect(() => {
    if (!ready) return;
    const t = setTimeout(() => { loadInspector().catch(() => {}); }, 4500);
    return () => clearTimeout(t);
  }, [ready]);

  return (
    <div className="grain flex h-full flex-col">
      {/* Mounted behind the intro, not during its exit: the curtain lifts on a dashboard that has already laid out. */}
      {ready && (
        <>
          <KpiBar />
          <div className="flex min-h-0 flex-1">
            <FleetList />
            <main className="relative min-w-0 flex-1">
              <FleetMap />
              <IncidentPanel />
              <AnimatePresence>{auditOpen && <AgentTimeline key="audit" />}</AnimatePresence>
            </main>
          </div>
          <ScenarioBar />
          <Toasts />
          <AnimatePresence>
            {inspectorOpen && (
              <Suspense fallback={null}>
                <Inspector key="inspector" />
              </Suspense>
            )}
          </AnimatePresence>
        </>
      )}
      {error && !intro && (
        <div className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-fail/40 bg-panel px-4 py-2 text-[12px] text-fail">
          Backend injoignable ({error}). Lancez : <span className="num">python run.py</span>
        </div>
      )}
      {intro && <Preloader ready={ready} onDone={() => setIntro(false)} />}
    </div>
  );
}
