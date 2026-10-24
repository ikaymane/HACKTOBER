import { AnimatePresence } from "framer-motion";
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { useStore } from "@/store";
import { Preloader } from "@/components/Preloader";
import { KpiBar } from "@/components/KpiBar";
import { FleetList } from "@/components/FleetList";
import { AgentTimeline } from "@/components/AgentTimeline";
import { ScenarioBar } from "@/components/ScenarioBar";
import { Toasts } from "@/components/Toasts";
import { FleetMap } from "@/components/map/FleetMap";

const Inspector = lazy(() => import("@/components/inspector/Inspector"));

export default function App() {
  const boot = useStore((s) => s.boot);
  const inspectorOpen = useStore((s) => s.inspectorOpen);
  const [ready, setReady] = useState(false);
  const [intro, setIntro] = useState(true);
  const [showApp, setShowApp] = useState(false);
  const onLeave = useCallback(() => setShowApp(true), []);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const minTime = new Promise((r) => setTimeout(r, 1800));
    Promise.all([boot(), minTime])
      .then(() => setReady(true))
      .catch((e) => { setError(String(e)); setReady(true); });
  }, [boot]);

  return (
    <div className="grain flex h-full flex-col">
      {showApp && (
        <>
          <KpiBar />
          <div className="flex min-h-0 flex-1">
            <FleetList />
            <main className="relative min-w-0 flex-1">
              <FleetMap />
            </main>
            <AgentTimeline />
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
          Backend injoignable ({error}). Lancez : <span className="num">MOCK=1 uvicorn app.main:app --reload</span>
        </div>
      )}
      {intro && <Preloader ready={ready} onLeave={onLeave} onDone={() => setIntro(false)} />}
    </div>
  );
}
