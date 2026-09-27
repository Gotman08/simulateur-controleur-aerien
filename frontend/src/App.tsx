/** A control desk: radar, flight strips, instructor, exercise and radio. */
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { ClipboardList, GraduationCap, Layers, ScrollText, Settings2 } from "lucide-react";
import { api } from "./api";
import RadarCanvas from "./components/RadarCanvas";
import ExercisePanel from "./components/ExercisePanel";
import InstructorPanel from "./components/InstructorPanel";
import LogPanel from "./components/LogPanel";
import RadioPanel from "./components/RadioPanel";
import StripBay from "./components/StripBay";
import TopBar from "./components/TopBar";
import { fmtTime } from "./components/ui";
import type { NavData, PlaceMode } from "./types";
import { useSim } from "./useSim";
import { DEFAULT_RADAR_OPTIONS } from "./radar";

const DebriefPanel = lazy(() => import("./components/DebriefPanel"));
const EMPTY_NAV: NavData = { waypoints: [], airports: [], fixes: [], routes: [], sector: [], range_nm: 70, center: [49.25, 4.05] };
type Tab = "trafic" | "instructeur" | "exercice" | "debrief" | "journal";
const TABS = [
  { id: "trafic" as const, label: "Trafic", icon: Layers },
  { id: "instructeur" as const, label: "Instructeur", icon: Settings2 },
  { id: "exercice" as const, label: "Exercice", icon: GraduationCap },
  { id: "debrief" as const, label: "Débrief", icon: ClipboardList },
  { id: "journal" as const, label: "Journal", icon: ScrollText },
];
const initialTab = (): Tab => TABS.find((t) => t.id === location.hash.slice(1))?.id ?? "trafic";

export default function App() {
  const hub = useSim();
  const { pushLog, onExerciseEnded } = hub;
  const [nav, setNav] = useState<NavData>(EMPTY_NAV);
  const [navReady, setNavReady] = useState(false);
  const [tab, setTab] = useState<Tab>(initialTab);
  const [selected, setSelected] = useState<string | null>(null);
  const [placeMode, setPlaceMode] = useState<PlaceMode>(null);
  const [centerOn, setCenterOn] = useState<{ id: string; tick: number } | null>(null);
  const [prefill, setPrefill] = useState("");
  const [layers, setLayers] = useState(DEFAULT_RADAR_OPTIONS);
  const chooseTab = useCallback((next: Tab) => {
    setTab(next);
    history.replaceState(null, "", `#${next}`);
  }, []);

  useEffect(() => {
    if (hub.connection !== "connected") return;
    let cancelled = false;
    let timer: number | undefined;
    const loadNav = () => void api.nav().then((n) => {
      if (!cancelled) { setNav(n); setNavReady(true); }
    }).catch(() => { if (!cancelled) timer = window.setTimeout(loadNav, 2000); });
    loadNav();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [hub.connection]);
  useEffect(() => onExerciseEnded(() => chooseTab("debrief")), [onExerciseEnded, chooseTab]);
  useEffect(() => {
    if (selected && !hub.state.aircraft.some((a) => a.id === selected)) setSelected(null);
  }, [selected, hub.state.aircraft]);

  const onPlace = useCallback((x: number, y: number) => {
    setPlaceMode(null);
    if (placeMode) void api.addZone(placeMode, x, y, placeMode === "storm" ? 14 : 10)
      .catch((e) => pushLog("rej", `Zone : ${e}`));
  }, [placeMode, pushLog]);
  const onSelect = useCallback((id: string | null) => {
    setSelected(id);
    if (id) setPrefill(id);
  }, []);
  const st = hub.state;
  const offline = hub.connection !== "connected";
  return (
    <div className="flex h-full min-h-dvh flex-col">
      <TopBar hub={hub} />
      {(offline || st.sim_alive === false || st.last_error) && (
        <div role="alert" className="border-b border-dang/30 bg-dang/10 px-5 py-2 text-sm text-dang">
          {offline ? "Liaison interrompue. Le radar affiche le dernier état reçu ; reconnexion automatique en cours."
            : st.last_error ? `Erreur de simulation : ${st.last_error}` : "Le moteur de simulation est arrêté. Consultez le journal du serveur."}
        </div>
      )}
      <div className="workspace">
        <main className="radar-stage" aria-label="Radar du secteur Reims">
          <RadarCanvas stateRef={hub.stateRef} nav={nav} selected={selected} onSelect={onSelect}
            placeMode={placeMode} onPlace={onPlace} options={layers} centerOn={centerOn} />
          <div className="pointer-events-none absolute left-5 top-4 text-[#bacbc0]">
            <p className="text-[10px] uppercase tracking-[.18em]">Surveillance du secteur</p>
            <p className="mt-0.5 font-mono text-sm">REIMS <span className="text-[#809b89]">· {nav.range_nm} NM</span></p>
            {!navReady && <p className="mt-2 text-xs text-amber-200">Chargement de la carte…</p>}
          </div>
          <details className="radar-controls absolute right-4 top-4 z-10 rounded-md text-xs">
            <summary className="select-none px-3 py-2">Couches radar</summary>
            <div className="grid gap-2 border-t border-[#3b5145] px-3 py-3">
              {([["labels", "Étiquettes"], ["trails", "Historique"], ["rings", "Distances"],
                ["routes", "Routes FMS"], ["waypoints", "Navigation"], ["sweep", "Balayage visuel"]] as const).map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2">
                    <input type="checkbox" checked={layers[key]} onChange={(e) => setLayers((l) => ({ ...l, [key]: e.target.checked }))} />
                    {label}
                  </label>
                ))}
            </div>
          </details>
          <div className="pointer-events-none absolute bottom-4 left-5 right-5 flex flex-wrap items-end justify-between gap-2 text-xs text-[#a6bbae]">
            <p id="radar-help">Molette : zoom · Glisser : déplacer<br /><span className="text-[#81998a]">Clavier : flèches, + / −, origine · Clic : sélectionner</span></p>
            <p className="font-mono text-[#bed2c5]">
              {st.conflicts.length ? `${st.conflicts.length} perte(s) de séparation` : st.predicted.length ? `${st.predicted.length} conflit(s) prédit(s)` : "Aucune alerte de séparation"}
            </p>
          </div>
          {placeMode && <div role="status" className="radar-controls absolute bottom-20 left-5 rounded px-3 py-2 text-sm">
            Cliquez pour placer la zone. <button type="button" className="ml-2 underline" onClick={() => setPlaceMode(null)}>Annuler</button>
          </div>}
        </main>
        <aside className="console" aria-label="Console de contrôle">
          <div className="flex items-center justify-between border-b border-edge px-4 py-3">
            <span className="text-xs font-semibold uppercase tracking-wider">Console</span>
            <span className="text-xs text-mut">{hub.exerciseLive ? `Exercice · reste ${fmtTime(hub.exerciseLive.remaining_s)}` : "Session libre"}</span>
          </div>
          <nav role="tablist" aria-label="Panneaux de contrôle" className="flex shrink-0 border-b border-edge bg-panel2">
            {TABS.map(({ id, label, icon: Icon }, index) => (
              <button key={id} type="button" role="tab" id={`tab-${id}`} aria-controls={`panel-${id}`} aria-selected={tab === id}
                tabIndex={tab === id ? 0 : -1} onClick={() => chooseTab(id)}
                onKeyDown={(e) => {
                  const offset = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
                  if (!offset && e.key !== "Home" && e.key !== "End") return;
                  e.preventDefault();
                  const next = e.key === "Home" ? 0 : e.key === "End" ? TABS.length - 1 : (index + offset + TABS.length) % TABS.length;
                  chooseTab(TABS[next].id);
                  (e.currentTarget.parentElement?.children[next] as HTMLButtonElement)?.focus();
                }}
                className={`relative flex min-w-0 flex-1 flex-col items-center gap-1 border-b-2 px-1 py-3 text-[11px] ${tab === id ? "border-acc bg-acc/5 font-semibold text-acc" : "border-transparent text-mut hover:bg-bg"}`}>
                <Icon size={16} strokeWidth={1.5} />{label}
                {id === "debrief" && hub.report && tab !== id && <span className="absolute right-3 top-2 h-1.5 w-1.5 rounded-full bg-acc" />}
              </button>
            ))}
          </nav>
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="min-h-0 flex-1 overflow-y-auto">
            {tab === "trafic" && <StripBay state={st} selected={selected} onSelect={onSelect} onCenter={(id) => setCenterOn({ id, tick: Date.now() })} />}
            {tab === "instructeur" && <InstructorPanel hub={hub} placeMode={placeMode} setPlaceMode={setPlaceMode} />}
            {tab === "exercice" && <ExercisePanel hub={hub} onDebrief={() => chooseTab("debrief")} />}
            {tab === "debrief" && <Suspense fallback={<p role="status" className="p-4 text-sm">Chargement du débrief…</p>}><DebriefPanel report={hub.report} /></Suspense>}
            {tab === "journal" && <LogPanel log={hub.log} onClear={hub.clearLog} />}
          </div>
          <RadioPanel hub={hub} prefill={prefill} />
        </aside>
      </div>
    </div>
  );
}
