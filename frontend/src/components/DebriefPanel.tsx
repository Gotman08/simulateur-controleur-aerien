/** Debrief d'exercice : score, decomposition du bareme, courbe de separation
 *  minimale, evenements et commandes. Donnees = rapport JSON du serveur. */
import { Download } from "lucide-react";
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import type { ExerciseReport } from "../types";
import { Badge, Btn, fmtTime, Section } from "./ui";
import { scoreColor } from "./ExercisePanel";

const BREAKDOWN: { key: "separation" | "conflits" | "zones" | "radio"; label: string; max: number }[] = [
  { key: "separation", label: "Séparation", max: 50 },
  { key: "conflits", label: "Conflits anticipés", max: 20 },
  { key: "zones", label: "Zones / météo", max: 15 },
  { key: "radio", label: "Radio", max: 15 },
];

export default function DebriefPanel({ report }: { report: ExerciseReport | null }) {
  if (!report) {
    return (
      <p className="px-4 py-6 text-center text-[12.5px] text-mut">
        Aucun débrief disponible. Terminez un exercice pour obtenir votre évaluation.
      </p>
    );
  }
  const sc = report.score;
  const series = (report.minsep_series ?? [])
    .filter(([, d]) => d != null)
    .map(([t, d]) => ({ t: Math.round(t), d }));

  return (
    <>
      <Section title={`Débrief — ${report.label ?? ""} · ${fmtTime(report.elapsed_s)}`}
        right={
          <Btn
            variant="ghost" className="px-2! py-0.5!"
            title="Télécharger le rapport JSON"
            onClick={() => downloadJson(report)}
          >
            <Download size={13} />
          </Btn>
        }>
        <div className="flex items-center gap-4">
          <div className={`font-mono text-5xl font-bold ${scoreColor(sc.total)}`}>{sc.total}</div>
          <div>
            <div className={`font-mono text-xl font-bold ${scoreColor(sc.total)}`}>{sc.grade}</div>
            <div className="text-[11.5px] text-mut">
              {report.auto_ended ? "temps écoulé" : "arrêt manuel"} ·
              IA {report.mode_ia ?? "local"} · {report.aircraft?.length ?? 0} aéronefs
            </div>
          </div>
        </div>

        <div className="mt-3 space-y-2">
          {BREAKDOWN.map((b) => (
            <div key={b.key}>
              <div className="flex justify-between text-[11.5px] text-mut">
                <span>{b.label}</span>
                <span className="font-mono">{sc[b.key]} / {b.max}</span>
              </div>
              <div className="mt-0.5 h-1.5 overflow-hidden rounded bg-edge">
                <div
                  className={`h-full ${sc[b.key] / b.max >= 0.75 ? "bg-rdr" : sc[b.key] / b.max >= 0.4 ? "bg-warn" : "bg-dang"}`}
                  style={{ width: `${(100 * sc[b.key]) / b.max}%` }}
                />
              </div>
            </div>
          ))}
        </div>

        <div className="mt-2 flex flex-wrap gap-1.5">
          <Badge tone={sc.n_los ? "dang" : "ok"}>{sc.n_los} perte(s) de séparation ({sc.t_los_s}s)</Badge>
          <Badge tone="acc">{sc.conflits_resolus}/{sc.conflits_predits} conflits résolus</Badge>
          <Badge tone={sc.n_zone ? "warn" : "mut"}>{sc.n_zone} pénétration(s) de zone</Badge>
          <Badge tone="mut">{sc.cmd_acceptees + sc.cmd_rejetees} clairances ({sc.cmd_rejetees} rejetée(s))</Badge>
        </div>
      </Section>

      {series.length > 1 && (
        <Section title="Séparation minimale (NM) — seuil 5 NM">
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series} margin={{ top: 6, right: 8, bottom: 0, left: -22 }}>
                <CartesianGrid stroke="#233042" strokeDasharray="3 3" />
                <XAxis dataKey="t" tick={{ fill: "#7e90a5", fontSize: 10 }}
                  tickFormatter={(v: number) => fmtTime(v)} stroke="#233042" />
                <YAxis tick={{ fill: "#7e90a5", fontSize: 10 }} stroke="#233042" domain={[0, "auto"]} />
                <Tooltip
                  contentStyle={{ background: "#10161e", border: "1px solid #233042", fontSize: 12 }}
                  labelFormatter={(v) => `t+${fmtTime(Number(v))}`}
                  formatter={(val) => [`${val} NM`, "séparation min"]}
                />
                <ReferenceLine y={5} stroke="#ff5868" strokeDasharray="5 4"
                  label={{ value: "5 NM", fill: "#ff5868", fontSize: 10, position: "insideTopRight" }} />
                <Line type="monotone" dataKey="d" stroke="#3fc6d6" dot={false} strokeWidth={1.6} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Section>
      )}

      {(report.los_events.length > 0 || report.zone_events.length > 0) && (
        <Section title="Événements">
          <ul className="space-y-1 text-[12px]">
            {report.los_events.map((e, i) => (
              <li key={`l${i}`} className="text-dang">
                ⚠ LoS {e.pair.join(" / ")} — t+{fmtTime(e.t_start)} → t+{fmtTime(e.t_end)}
                {e.min_nm != null && <> · min {e.min_nm.toFixed(1)} NM</>}
              </li>
            ))}
            {report.zone_events.map((e, i) => (
              <li key={`z${i}`} className="text-warn">
                △ {e.callsign} dans {e.zone} — t+{fmtTime(e.t_start)} → t+{fmtTime(e.t_end)}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {report.commands.length > 0 && (
        <Section title={`Clairances émises (${report.commands.length})`}>
          <ul className="max-h-44 space-y-1 overflow-y-auto font-mono text-[11.5px] text-mut">
            {report.commands.map((c, i) => (
              <li key={i}>
                <span className="text-acc">t+{fmtTime(c.t)}</span>{" "}
                <span className={c.rejected ? "text-dang" : "text-ink"}>{c.text}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}

function downloadJson(report: ExerciseReport) {
  const blob = new Blob([JSON.stringify(report, null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `debrief_${(report.ended_iso ?? "rapport").replace(/[:T]/g, "-")}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}
