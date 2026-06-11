/** Etat temps reel de la simulation : WebSocket /ws + journal + evenements.
 *  Le dernier etat est garde dans une ref (lu a 60 fps par le canvas) et la
 *  version React n'est rafraichie qu'a ~4 Hz pour ne pas re-rendre les panneaux
 *  a la cadence du serveur. */
import { useCallback, useEffect, useRef, useState } from "react";
import type { Caps, Exchange, ExerciseReport, ExerciseScore, LogEntry, SimState } from "./types";
import { api } from "./api";
import { speak } from "./audio";

const EMPTY: SimState = {
  t: 0, running: false, paused: false, speed: 1,
  aircraft: [], conflicts: [], predicted: [],
};

let logSeq = 0;
const now = () => new Date().toLocaleTimeString("fr-FR", { hour12: false });

export interface SimHub {
  stateRef: React.RefObject<SimState>;
  state: SimState;                       // version throttlee (~4 Hz)
  caps: Caps;
  mode: string;
  log: LogEntry[];
  lastExchange: Exchange | null;
  report: ExerciseReport | null;
  exerciseLive: { elapsed_s: number; remaining_s: number; score: ExerciseScore } | null;
  exerciseActive: boolean;
  pushLog: (kind: LogEntry["kind"], text: string) => void;
  clearLog: () => void;
  refreshHealth: () => Promise<void>;
  setReport: (r: ExerciseReport | null) => void;
  onExerciseEnded: (cb: () => void) => void;
}

export function useSim(): SimHub {
  const stateRef = useRef<SimState>(EMPTY);
  const [state, setState] = useState<SimState>(EMPTY);
  const [caps, setCaps] = useState<Caps>({ romeo: false, asr: false, llm: false, tts: false });
  const [mode, setMode] = useState("local");
  const [log, setLog] = useState<LogEntry[]>([]);
  const [lastExchange, setLastExchange] = useState<Exchange | null>(null);
  const [report, setReport] = useState<ExerciseReport | null>(null);
  const endedCb = useRef<() => void>(() => undefined);

  const pushLog = useCallback((kind: LogEntry["kind"], text: string) => {
    setLog((l) => [...l.slice(-249), { id: ++logSeq, t: now(), kind, text }]);
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const h = await api.healthRefresh();
      setCaps(h.caps);
      setMode(h.mode);
    } catch { /* serveur indisponible : on garde l'etat courant */ }
  }, []);

  // sante initiale + dernier rapport d'exercice eventuel
  useEffect(() => {
    api.health().then((h) => { setCaps(h.caps); setMode(h.mode); }).catch(() => undefined);
    api.exerciseReport().then(setReport).catch(() => undefined);
  }, []);

  // WebSocket + throttling de l'etat React
  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let lastPush = -1e9;          // le tout premier etat est rendu immediatement

    const handle = (msg: Record<string, unknown>) => {
      switch (msg.type) {
        case "state": {
          stateRef.current = msg as unknown as SimState;
          const t = performance.now();
          if (t - lastPush > 240) { lastPush = t; setState(stateRef.current); }
          break;
        }
        case "exchange": {
          const m = msg as unknown as Exchange & { readback: string };
          setLastExchange(m);
          pushLog("tx", `📡 ${m.transcript}`);
          (m.trafscript ?? []).forEach((l) => pushLog("cmd", `→ ${l}`));
          if (m.readback) pushLog("pilot", `🔊 ${m.readback}`);
          (m.rejected ?? []).forEach((r) => pushLog("rej", `⊘ ${r}`));
          if (!m.trafscript?.length && !m.rejected?.length) pushLog("rej", "⊘ aucun ordre reconnu");
          break;
        }
        case "situation":
          pushLog("ok", `✈ Situation : ${msg.description} → ${((msg.created as string[]) ?? []).join(", ") || "—"}`);
          break;
        case "info":
          pushLog("info", String(msg.message ?? ""));
          break;
        case "exercise_started":
          pushLog("ok", `▶ Exercice ${msg.label ?? ""} démarré — ${((msg.aircraft as string[]) ?? []).length} aéronefs`);
          break;
        case "exercise_event": {
          const kind = msg.kind as string;
          if (kind === "los") pushLog("rej", `⚠ PERTE DE SÉPARATION ${(msg.pair as string[]).join(" / ")} (t=${msg.t}s)`);
          else if (kind === "predicted") pushLog("warn", `△ Conflit prédit ${(msg.pair as string[]).join(" / ")} — CPA ${msg.dcpa} NM dans ${msg.tcpa}s`);
          else if (kind === "zone") pushLog("warn", `△ ${msg.callsign} pénètre ${msg.zone} (t=${msg.t}s)`);
          break;
        }
        case "exercise_ended": {
          const sc = msg.score as ExerciseScore | undefined;
          pushLog("ok", `■ Exercice terminé — score ${sc?.total ?? "?"}/100 (${sc?.grade ?? ""})`);
          api.exerciseReport().then((r) => { setReport(r); endedCb.current(); }).catch(() => undefined);
          break;
        }
      }
    };

    const connect = () => {
      if (closed) return;
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
      ws.onmessage = (ev) => {
        try { handle(JSON.parse(ev.data)); } catch { /* trame invalide ignoree */ }
      };
      ws.onclose = () => { if (!closed) setTimeout(connect, 1500); };
    };
    connect();
    return () => { closed = true; ws?.close(); };
  }, [pushLog]);

  return {
    stateRef, state, caps, mode, log, lastExchange, report,
    exerciseLive: state.exercise ?? null,
    exerciseActive: !!state.exercise,
    pushLog,
    clearLog: () => setLog([]),
    refreshHealth,
    setReport,
    onExerciseEnded: (cb) => { endedCb.current = cb; },
  };
}

/** Collationnement vocal cote navigateur quand ROMEO/XTTS est indisponible. */
export function speakLocalReadback(mode: string, readback: string | undefined) {
  if (mode !== "romeo" && readback) speak(readback);
}
