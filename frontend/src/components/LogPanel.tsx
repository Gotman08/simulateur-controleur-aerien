/** Journal de session : flux horodate des echanges et evenements. */
import { useEffect, useRef } from "react";
import { Eraser } from "lucide-react";
import type { LogEntry } from "../types";
import { Btn } from "./ui";

const COLOR: Record<LogEntry["kind"], string> = {
  info: "text-mut",
  tx: "text-rdr",
  cmd: "text-wpt",
  pilot: "text-warn",
  rej: "text-dang",
  warn: "text-warn",
  ok: "text-acc",
};

export default function LogPanel({ log, onClear }: { log: LogEntry[]; onClear: () => void }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [log]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-edge px-4 py-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-mut">
          Journal de session
        </span>
        <Btn variant="ghost" className="px-2! py-0.5!" title="Effacer" onClick={onClear}>
          <Eraser size={13} />
        </Btn>
      </div>
      <div className="flex-1 select-text overflow-y-auto px-4 py-2 font-mono text-[11.5px] leading-relaxed">
        {log.length === 0 && <span className="text-mut/60">— journal vide —</span>}
        {log.map((l) => (
          <div key={l.id} className={COLOR[l.kind]}>
            <span className="mr-1.5 text-mut/50">{l.t}</span>
            {l.text}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
