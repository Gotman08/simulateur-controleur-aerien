/** Mode exercice : l'IA cree la situation (conflits garantis + meteo), l'eleve
 *  la resout ; score en direct et acces au debrief. */
import { useState } from "react";
import { CircleStop, Loader2, Play, Target } from "lucide-react";
import { api } from "../api";
import type { SimHub } from "../useSim";
import { Badge, Btn, fmtTime, Section } from "./ui";

const LEVELS = [
  { id: "facile", label: "Facile", desc: "3 aéronefs · 1 conflit programmé · pas de météo" },
  { id: "moyen", label: "Moyen", desc: "~6 aéronefs · 2 conflits programmés · vent" },
  { id: "difficile", label: "Difficile", desc: "~8 aéronefs · 3 conflits · vent fort, orage, turbulence" },
];

export default function ExercisePanel({ hub, onDebrief }: { hub: SimHub; onDebrief: () => void }) {
  const [level, setLevel] = useState("moyen");
  const [duration, setDuration] = useState(10);
  const [busy, setBusy] = useState(false);
  const [exMeta, setExMeta] = useState<{ objectives?: string[]; label?: string } | null>(null);
  const live = hub.exerciseLive;
  const active = hub.exerciseActive;

  const start = async () => {
    setBusy(true);
    try {
      const st = await api.exerciseStart(level, duration);
      setExMeta({ objectives: st.objectives, label: st.label });
    } catch (e) {
      hub.pushLog("rej", `Exercice : ${e}`);
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await api.exerciseStop();           // le rapport arrive via l'evenement WS
    } catch (e) {
      hub.pushLog("rej", `Exercice : ${e}`);
    } finally {
      setBusy(false);
    }
  };

  if (active && live) {
    const sc = live.score;
    const total = (live.elapsed_s ?? 0) + (live.remaining_s ?? 0);
    const pct = total > 0 ? (100 * (live.elapsed_s ?? 0)) / total : 0;
    return (
      <Section title={`Exercice en cours${exMeta?.label ? ` — ${exMeta.label}` : ""}`}>
        <div className="mb-2 flex items-center justify-between font-mono text-[12px] text-mut">
          <span>écoulé {fmtTime(live.elapsed_s)}</span>
          <span>reste {fmtTime(live.remaining_s)}</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded bg-edge">
          <div className="h-full bg-acc transition-all" style={{ width: `${pct}%` }} />
        </div>

        <div className="mt-3 flex items-end gap-3">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-mut">Score courant</div>
            <div className={`font-mono text-3xl font-bold ${scoreColor(sc?.total)}`}>
              {sc?.total ?? "—"}
              <span className="ml-1 text-base text-mut">/100 ({sc?.grade ?? "—"})</span>
            </div>
          </div>
          <div className="mb-1 flex flex-wrap gap-1.5">
            <Badge tone={sc?.n_los ? "dang" : "ok"}>LoS {sc?.n_los ?? 0}</Badge>
            <Badge tone="acc">conflits {sc?.conflits_resolus ?? 0}/{sc?.conflits_predits ?? 0}</Badge>
            <Badge tone={sc?.n_zone ? "warn" : "mut"}>zones {sc?.n_zone ?? 0}</Badge>
            <Badge tone={sc?.cmd_rejetees ? "warn" : "mut"}>
              radio {sc?.cmd_acceptees ?? 0}✓ {sc?.cmd_rejetees ?? 0}✗
            </Badge>
          </div>
        </div>

        {exMeta?.objectives && (
          <ul className="mt-3 space-y-1 text-[12.5px] text-mut">
            {exMeta.objectives.map((o, i) => (
              <li key={i} className="flex gap-1.5">
                <Target size={13} className="mt-0.5 shrink-0 text-acc" />{o}
              </li>
            ))}
          </ul>
        )}

        <Btn variant="danger" className="mt-3 w-full" disabled={busy} onClick={() => void stop()}>
          <CircleStop size={14} className="mr-1 inline" />Terminer l'exercice (débrief)
        </Btn>
      </Section>
    );
  }

  return (
    <Section title="Nouvel exercice">
      <p className="mb-2 text-[12.5px] leading-snug text-mut">
        L'IA génère une situation avec des conflits programmés et des conditions
        météo : à vous de maintenir la séparation, comme en réel. Tout est mesuré
        (séparation, conflits résolus, zones, radio) et noté sur 100.
      </p>
      <div className="space-y-1.5">
        {LEVELS.map((l) => (
          <label
            key={l.id}
            className={`block cursor-pointer rounded-md border px-3 py-2 transition-colors
              ${level === l.id ? "border-acc/70 bg-acc/5" : "border-edge bg-panel2 hover:border-acc/40"}`}
          >
            <input
              type="radio" name="level" className="mr-2 accent-(--color-acc)"
              checked={level === l.id}
              onChange={() => setLevel(l.id)}
            />
            <span className="text-[13px] font-semibold text-ink">{l.label}</span>
            <span className="mt-0.5 block pl-5 text-[11.5px] text-mut">{l.desc}</span>
          </label>
        ))}
      </div>
      <div className="mt-2 flex items-center gap-2 text-[12.5px] text-mut">
        durée
        <select
          className="rounded-md border border-edge bg-panel2 px-2 py-1 text-[12.5px] text-ink"
          value={duration}
          onChange={(e) => setDuration(+e.target.value)}
        >
          {[5, 10, 15, 20].map((d) => <option key={d} value={d}>{d} min</option>)}
        </select>
        (temps simulé)
      </div>
      <Btn variant="primary" className="mt-3 w-full" disabled={busy} onClick={() => void start()}>
        {busy ? <Loader2 size={14} className="mr-1 inline animate-spin" /> : <Play size={14} className="mr-1 inline" />}
        {busy ? "Génération de la situation…" : "Démarrer l'exercice"}
      </Btn>
      {hub.report && (
        <Btn variant="ghost" className="mt-2 w-full" onClick={onDebrief}>
          Voir le dernier débrief ({hub.report.score.total}/100)
        </Btn>
      )}
    </Section>
  );
}

export const scoreColor = (v: number | undefined) =>
  v == null ? "text-mut" : v >= 75 ? "text-rdr" : v >= 50 ? "text-warn" : "text-dang";
