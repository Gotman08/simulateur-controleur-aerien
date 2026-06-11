/** Poste de controle : radar a gauche, console a droite (trafic / instructeur /
 *  exercice / debrief / journal) et poste radio toujours visible. */
import { useCallback, useEffect, useState } from "react";
import { ClipboardList, GraduationCap, Layers, ScrollText, Settings2 } from "lucide-react";
import { api } from "./api";
import RadarCanvas from "./components/RadarCanvas";
import DebriefPanel from "./components/DebriefPanel";
import ExercisePanel from "./components/ExercisePanel";
import InstructorPanel from "./components/InstructorPanel";
import LogPanel from "./components/LogPanel";
import RadioPanel from "./components/RadioPanel";
import StripBay from "./components/StripBay";
import TopBar from "./components/TopBar";
import type { NavData, PlaceMode } from "./types";
import { useSim } from "./useSim";

const EMPTY_NAV: NavData = {
  waypoints: [], airports: [], fixes: [], routes: [], sector: [],
  range_nm: 70, center: [49.25, 4.05],
};

type Tab = "trafic" | "instructeur" | "exercice" | "debrief" | "journal";

const TABS: { id: Tab; label: string; icon: typeof Layers }[] = [
  { id: "trafic", label: "Trafic", icon: Layers },
  { id: "instructeur", label: "Instructeur", icon: Settings2 },
  { id: "exercice", label: "Exercice", icon: GraduationCap },
  { id: "debrief", label: "Débrief", icon: ClipboardList },
  { id: "journal", label: "Journal", icon: ScrollText },
];

const initialTab = (): Tab => {
  const h = location.hash.replace("#", "") as Tab;
  return TABS.some((t) => t.id === h) ? h : "trafic";
};

export default function App() {
  const hub = useSim();
  const [nav, setNav] = useState<NavData>(EMPTY_NAV);
  const [tab, setTab] = useState<Tab>(initialTab);
  const [selected, setSelected] = useState<string | null>(null);
  const [placeMode, setPlaceMode] = useState<PlaceMode>(null);
  const [centerOn, setCenterOn] = useState<{ id: string; tick: number } | null>(null);
  const [prefill, setPrefill] = useState("");

  useEffect(() => {
    api.nav().then(setNav).catch(() => undefined);
  }, []);

  // fin d'exercice -> ouverture automatique du debrief
  useEffect(() => {
    hub.onExerciseEnded(() => setTab("debrief"));
  }, [hub]);

  const onPlace = useCallback((x: number, y: number) => {
    setPlaceMode((mode) => {
      if (mode) {
        void api.addZone(mode, x, y, mode === "storm" ? 14 : 10);
      }
      return null;
    });
  }, []);

  const onSelect = useCallback((id: string | null) => {
    setSelected(id);
    if (id) setPrefill(id);
  }, []);

  return (
    <div className="flex h-full flex-col">
      <TopBar hub={hub} />
      <div className="flex min-h-0 flex-1">
        {/* -------- scope radar -------- */}
        <main className="relative min-w-0 flex-1">
          <RadarCanvas
            stateRef={hub.stateRef}
            nav={nav}
            selected={selected}
            onSelect={onSelect}
            placeMode={placeMode}
            onPlace={onPlace}
            showSweep
            centerOn={centerOn}
          />
          <div className="pointer-events-none absolute left-3 top-2 font-mono text-[11px] text-mut/80">
            molette : zoom · glisser : déplacer · double-clic : recentrer · clic avion : sélection
          </div>
        </main>

        {/* -------- console laterale -------- */}
        <aside className="flex w-[400px] shrink-0 flex-col border-l border-edge bg-panel">
          <nav className="flex shrink-0 border-b border-edge">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => { setTab(id); history.replaceState(null, "", `#${id}`); }}
                className={`flex flex-1 flex-col items-center gap-0.5 px-1 py-2 text-[10.5px]
                  transition-colors ${tab === id
                    ? "border-b-2 border-acc bg-acc/5 text-acc"
                    : "border-b-2 border-transparent text-mut hover:text-ink"}`}
              >
                <Icon size={15} />
                {label}
                {id === "debrief" && hub.report && tab !== "debrief" && (
                  <span className="absolute mt-[-2px] ml-10 h-1.5 w-1.5 rounded-full bg-acc" />
                )}
              </button>
            ))}
          </nav>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === "trafic" && (
              <StripBay
                state={hub.state}
                selected={selected}
                onSelect={onSelect}
                onCenter={(id) => setCenterOn({ id, tick: Date.now() })}
              />
            )}
            {tab === "instructeur" && (
              <InstructorPanel hub={hub} placeMode={placeMode} setPlaceMode={setPlaceMode} />
            )}
            {tab === "exercice" && <ExercisePanel hub={hub} onDebrief={() => setTab("debrief")} />}
            {tab === "debrief" && <DebriefPanel report={hub.report} />}
            {tab === "journal" && <LogPanel log={hub.log} onClear={hub.clearLog} />}
          </div>

          <RadioPanel hub={hub} prefill={prefill} />
        </aside>
      </div>
    </div>
  );
}
