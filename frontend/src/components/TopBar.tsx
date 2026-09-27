/** Simulation controls and live operational status. */
import { Pause, Play, RotateCcw, TowerControl } from "lucide-react";
import type { SimHub } from "../useSim";
import { api } from "../api";
import { Badge, Btn, fmtTime } from "./ui";

export default function TopBar({ hub }: { hub: SimHub }) {
  const st = hub.state;
  const ready = hub.connection === "connected" && st.sim_alive !== false;
  const action = (promise: Promise<unknown>) => void promise.catch((e) => hub.pushLog("rej", String(e)));
  return (
    <header className="shrink-0 border-b border-edge bg-panel2 px-5 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded border border-acc/25 bg-acc/5 p-2.5"><TowerControl size={23} className="text-acc" /></div>
          <div>
            <h1 className="text-[17px] font-semibold tracking-tight">Poste de contrôle</h1>
            <p className="text-xs text-mut">Secteur Reims <span className="px-1.5">/</span> Entraînement ATC</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm tabular-nums" aria-label="Temps de simulation">T+ {fmtTime(st.t)}</span>
          <div className="hidden h-6 border-l border-edge sm:block" />
          <Btn disabled={!ready} title={st.paused ? "Reprendre la simulation" : "Mettre en pause"}
            onClick={() => action(st.paused ? api.resume() : api.pause())}>
            {st.paused ? <Play size={14} /> : <Pause size={14} />}
            {st.paused ? "Reprendre" : "Pause"}
          </Btn>
          <label className="flex items-center gap-2 text-xs text-mut">
            Vitesse
            <select className="rounded border border-edge bg-panel2 px-2 py-2 font-mono text-ink"
              aria-label="Vitesse de simulation" value={st.speed} disabled={!ready}
              onChange={(e) => action(api.setSpeed(Number(e.target.value)))}>
              {[0.5, 1, 2, 5, 10, 20].map((n) => <option key={n} value={n}>{n}×</option>)}
              {![0.5, 1, 2, 5, 10, 20].includes(st.speed) && <option value={st.speed}>{st.speed}×</option>}
            </select>
          </label>
          <Btn variant="ghost" disabled={!ready} title="Réinitialiser la simulation"
            onClick={() => { if (confirm("Vider le radar et terminer l’exercice en cours ?")) action(api.reset()); }}>
            <RotateCcw size={15} />
          </Btn>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-edge/70 pt-2.5 text-xs">
        <div className="flex flex-wrap items-center gap-3" role="status">
          <span className={ready ? "text-rdr" : "text-dang"}>
            <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-current" />
            {hub.connection === "connecting" ? "Connexion…" : hub.connection !== "connected" ? "Connexion interrompue" : st.sim_alive === false ? "Simulateur arrêté" : st.paused ? "Simulation en pause" : "Simulation en cours"}
          </span>
          <span className="text-mut">{st.aircraft.length} aéronefs</span>
          <span className="text-mut">Détection : {st.cd_engine === "bluesky" ? "BlueSky" : st.cd_engine === "geometry" ? "secours géométrique" : "initialisation"}</span>
          {st.wind && <span className="font-mono text-mut">Vent {String(st.wind.dir).padStart(3, "0")}° / {st.wind.spd} kt</span>}
        </div>
        <div className="flex items-center gap-2">
          <span className="mr-1 text-mut">Services radio</span>
          {(["stt", "llm", "tts"] as const).map((p) => (
            <button key={p} type="button" className="rounded px-1 py-0.5"
              aria-label={`Retester le service ${p.toUpperCase()}`}
              title={`${p.toUpperCase()} : ${hub.providers[p] ? "disponible" : "indisponible"}. Cliquer pour retester.`}
              onClick={() => void hub.refreshHealth()}>
              <Badge tone={hub.providers[p] ? "ok" : "mut"}>{p.toUpperCase()} {hub.providers[p] ? "✓" : "—"}</Badge>
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
