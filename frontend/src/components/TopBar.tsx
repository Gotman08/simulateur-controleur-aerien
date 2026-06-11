/** Barre superieure : identite du poste, horloge simu, alertes, controles
 *  simulation (pause / vitesse / reset) et etat du backend IA. */
import { Gauge, Pause, Play, RotateCcw, Satellite, TowerControl, Wind } from "lucide-react";
import type { SimHub } from "../useSim";
import { api } from "../api";
import { Badge, Btn, fmtTime } from "./ui";

export default function TopBar({ hub }: { hub: SimHub }) {
  const st = hub.state;
  const nlos = st.conflicts?.length ?? 0;
  const npred = st.predicted?.length ?? 0;
  const ex = hub.exerciseLive;

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-edge bg-panel px-4">
      <div className="flex items-center gap-2 font-semibold tracking-wide text-ink">
        <TowerControl size={18} className="text-acc" />
        ATC&nbsp;TRAINER
        <span className="text-[12px] font-normal text-mut">CTR Reims · 70 NM</span>
      </div>

      <div className="ml-2 flex items-center gap-2 font-mono text-[12px] text-mut">
        <span>t+{fmtTime(st.t)}</span>
        <span>·</span>
        <span>{st.aircraft.length} vols</span>
        {st.cd_engine && (
          <Badge tone="mut" title="Moteur de détection de conflits">
            CD {st.cd_engine === "bluesky" ? "BlueSky" : "géo"}
          </Badge>
        )}
        {st.wind && (
          <Badge tone="acc" title="Vent actif">
            <Wind size={11} />
            {String(st.wind.dir).padStart(3, "0")}/{st.wind.spd} kt
          </Badge>
        )}
      </div>

      {/* alertes au centre */}
      <div className="flex flex-1 justify-center">
        {nlos > 0 ? (
          <Badge tone="dang" className="animate-alert text-[12px]!">⚠ PERTE DE SÉPARATION ({nlos})</Badge>
        ) : npred > 0 ? (
          <Badge tone="warn" className="text-[12px]!">
            △ conflit prédit — CPA dans {Math.min(...st.predicted.map((p) => p.t))}s
          </Badge>
        ) : ex ? (
          <Badge tone="acc" className="text-[12px]!">
            <Gauge size={12} /> exercice — reste {fmtTime(ex.remaining_s)} · score {ex.score?.total ?? "—"}
          </Badge>
        ) : null}
      </div>

      {/* controles simulation */}
      <div className="flex items-center gap-2">
        <Btn
          variant="ghost"
          title={st.paused ? "Reprendre" : "Pause"}
          onClick={() => (st.paused ? api.resume() : api.pause())}
        >
          {st.paused ? <Play size={15} /> : <Pause size={15} />}
        </Btn>
        <label className="flex items-center gap-1.5 text-[12px] text-mut" title="Vitesse de simulation">
          <input
            type="range" min={1} max={10} step={1} defaultValue={1}
            className="w-20"
            onChange={(e) => api.setSpeed(+e.target.value)}
          />
          <span className="w-6 font-mono text-acc">{st.speed}×</span>
        </label>
        <Btn
          variant="ghost"
          title="Vider le radar (RESET)"
          onClick={() => { if (confirm("Réinitialiser la simulation ?")) api.reset(); }}
        >
          <RotateCcw size={15} />
        </Btn>
        <Badge
          tone={hub.mode === "romeo" ? "ok" : "warn"}
          className="cursor-pointer"
          title={hub.mode === "romeo"
            ? "IA : serveur ROMEO (Whisper / Mistral / XTTS)"
            : "IA : repli local (voix navigateur). Cliquer pour re-détecter ROMEO."}
          onClick={() => { hub.pushLog("info", "Re-détection ROMEO…"); void hub.refreshHealth(); }}
        >
          <Satellite size={11} />
          {hub.mode === "romeo" ? "ROMEO" : "LOCAL"}
        </Badge>
      </div>
    </header>
  );
}
