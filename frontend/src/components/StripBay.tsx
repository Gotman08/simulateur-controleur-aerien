/** Tableau de strips : un strip par vol, alertes en tete, clic = selection. */
import { ArrowDown, ArrowUp, Crosshair } from "lucide-react";
import type { Aircraft, SimState } from "../types";
import { Badge } from "./ui";

const prio = (a: Aircraft) => (a.alert === "los" ? 0 : a.alert === "predicted" ? 1 : a.inzone ? 2 : 3);

export default function StripBay({ state, selected, onSelect, onCenter }: {
  state: SimState;
  selected: string | null;
  onSelect: (id: string) => void;
  onCenter: (id: string) => void;
}) {
  const acs = [...state.aircraft].sort((a, b) => prio(a) - prio(b) || a.id.localeCompare(b.id));
  if (!acs.length) {
    return (
      <p className="px-4 py-6 text-center text-[12.5px] text-mut">
        Aucun trafic. Générez une situation (onglet Instructeur)
        ou démarrez un exercice.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-1.5 px-3 py-2">
      {acs.map((a) => (
        <Strip key={a.id} a={a} sel={a.id === selected} onSelect={onSelect} onCenter={onCenter} />
      ))}
    </ul>
  );
}

function Strip({ a, sel, onSelect, onCenter }: {
  a: Aircraft; sel: boolean; onSelect: (id: string) => void; onCenter: (id: string) => void;
}) {
  const border =
    a.alert === "los" ? "border-dang/70" :
    a.alert === "predicted" ? "border-warn/60" :
    a.inzone ? "border-mag/60" :
    sel ? "border-acc/70" : "border-edge";
  const cfl = a.sel_alt_ft != null && Math.abs(a.sel_alt_ft - a.alt_ft) > 200
    ? Math.round(a.sel_alt_ft / 100) : null;
  return (
    <li
      onClick={() => onSelect(a.id)}
      className={`cursor-pointer rounded-md border bg-panel2 px-3 py-2 transition-colors
        hover:border-acc/50 ${border} ${sel ? "bg-acc/5" : ""}`}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[13.5px] font-bold tracking-wide text-ink">{a.id}</span>
        <span className="font-mono text-[11px] text-mut">{a.type || "—"}</span>
        <div className="flex items-center gap-1">
          {a.alert === "los" && <Badge tone="dang">LoS</Badge>}
          {a.alert === "predicted" && <Badge tone="warn">CONF</Badge>}
          {a.inzone && <Badge tone="dang" className="border-mag/50! text-mag!">{a.inzone}</Badge>}
          <button
            title="Centrer le radar sur ce vol"
            className="rounded p-1 text-mut hover:bg-edge hover:text-acc"
            onClick={(e) => { e.stopPropagation(); onCenter(a.id); }}
          >
            <Crosshair size={13} />
          </button>
        </div>
      </div>
      <div className="mt-1 flex items-center gap-3 font-mono text-[12px] text-mut">
        <span className="text-ink">
          FL{String(a.fl).padStart(3, "0")}
          {a.vs_fpm > 300 && <ArrowUp size={11} className="inline text-rdr" />}
          {a.vs_fpm < -300 && <ArrowDown size={11} className="inline text-warn" />}
        </span>
        {cfl != null && <span title="Niveau autorisé">→ FL{String(cfl).padStart(3, "0")}</span>}
        <span>{a.gs} kt</span>
        <span>CAP {String(Math.round(a.hdg)).padStart(3, "0")}°</span>
        {Math.abs(a.vs_fpm) > 300 && <span>{a.vs_fpm > 0 ? "+" : ""}{a.vs_fpm} fpm</span>}
      </div>
    </li>
  );
}
