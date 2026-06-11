/** Poste radio du controleur : push-to-talk (souris ou barre espace) + saisie
 *  texte + dernier echange. ROMEO -> capture WAV vers /api/voice ; sinon Web
 *  Speech API du navigateur (STT + voix du collationnement). */
import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, SendHorizonal } from "lucide-react";
import { api } from "../api";
import { getRecognition, playB64Wav, WavRecorder } from "../audio";
import { speakLocalReadback, type SimHub } from "../useSim";
import { Btn, Input } from "./ui";

export default function RadioPanel({ hub, prefill }: { hub: SimHub; prefill: string }) {
  const [text, setText] = useState("");
  const [talking, setTalking] = useState(false);
  const [busy, setBusy] = useState(false);
  const recRef = useRef<ReturnType<typeof getRecognition>>(null);
  const wavRef = useRef<WavRecorder | null>(null);
  const capsRef = useRef(hub.caps);
  capsRef.current = hub.caps;
  const modeRef = useRef(hub.mode);
  modeRef.current = hub.mode;

  // selection d'un avion au radar -> indicatif pre-rempli
  useEffect(() => {
    if (prefill) setText((t) => (t.trim() ? t : prefill + " "));
  }, [prefill]);

  const send = useCallback(async (t: string) => {
    const txt = t.trim();
    if (!txt) return;
    try {
      const out = await api.command(txt) as { readback_text?: string };
      speakLocalReadback(modeRef.current, out.readback_text);
    } catch (e) {
      hub.pushLog("rej", `Erreur commande : ${e}`);
    }
  }, [hub]);

  const startTalk = useCallback(async () => {
    setTalking(true);
    if (capsRef.current.asr) {
      try {
        wavRef.current = new WavRecorder();
        await wavRef.current.start();
      } catch (e) {
        hub.pushLog("rej", `Micro indisponible : ${e}`);
        setTalking(false);
      }
    } else {
      const r = getRecognition();
      if (!r) {
        hub.pushLog("rej", "Reconnaissance vocale indisponible — tapez la clairance.");
        setTalking(false);
        return;
      }
      recRef.current = r;
      r.onresult = (e) => { void send(e.results[0][0].transcript); };
      r.onerror = (e) => hub.pushLog("rej", `STT : ${e.error}`);
      try { r.start(); } catch { /* deja demarre */ }
    }
  }, [hub, send]);

  const stopTalk = useCallback(async () => {
    setTalking(false);
    if (capsRef.current.asr && wavRef.current) {
      const wav = await wavRef.current.stop();
      wavRef.current = null;
      if (!wav) return;
      setBusy(true);
      try {
        const j = await api.voice(wav);
        if (j.audio_b64) playB64Wav(j.audio_b64);
      } catch (e) {
        hub.pushLog("rej", `Erreur /api/voice : ${e}`);
      } finally {
        setBusy(false);
      }
    } else {
      try { recRef.current?.stop(); } catch { /* deja arrete */ }
    }
  }, [hub]);

  // barre espace = alternat (hors champs de saisie)
  useEffect(() => {
    const isTyping = (t: EventTarget | null) =>
      t instanceof HTMLElement && (t.tagName === "INPUT" || t.tagName === "TEXTAREA");
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !isTyping(e.target) && !e.repeat) { e.preventDefault(); void startTalk(); }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space" && !isTyping(e.target)) { e.preventDefault(); void stopTalk(); }
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
  }, [startTalk, stopTalk]);

  const m = hub.lastExchange;
  return (
    <div className="shrink-0 border-t border-edge bg-panel px-4 py-3">
      <button
        className={`w-full rounded-lg border-2 px-4 py-3.5 text-[14px] font-bold tracking-wide
          transition-colors ${talking
            ? "border-dang bg-dang text-white"
            : busy
              ? "cursor-wait border-edge bg-panel2 text-mut"
              : "border-rdr/70 bg-rdr/10 text-rdr hover:bg-rdr/20"}`}
        onPointerDown={(e) => { e.preventDefault(); void startTalk(); }}
        onPointerUp={(e) => { e.preventDefault(); void stopTalk(); }}
        onPointerLeave={() => { if (talking) void stopTalk(); }}
        title="Maintenir pour parler (ou barre espace)"
      >
        <Mic size={15} className="mr-1 inline" />
        {talking ? "TRANSMISSION…" : busy ? "TRAITEMENT…" : "MAINTENIR POUR PARLER"}
      </button>

      <div className="mt-2 flex gap-2">
        <Input
          className="flex-1 font-mono"
          placeholder="air france one two three four descend flight level one zero zero"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { void send(text); setText(""); }
          }}
        />
        <Btn variant="primary" title="Envoyer" onClick={() => { void send(text); setText(""); }}>
          <SendHorizonal size={15} />
        </Btn>
      </div>

      {m && (
        <div className="mt-2 space-y-0.5 text-[12.5px] leading-snug">
          <div className="text-rdr">📡 « {m.transcript} »</div>
          {m.trafscript?.length > 0 && (
            <div className="font-mono text-[11.5px] text-wpt">→ {m.trafscript.join(" · ")}</div>
          )}
          {m.readback && <div className="text-warn">🔊 {m.readback}</div>}
          {m.rejected?.map((r, i) => <div key={i} className="text-dang">⊘ {r}</div>)}
          {!m.trafscript?.length && !m.rejected?.length && (
            <div className="text-dang">⊘ aucun ordre reconnu</div>
          )}
        </div>
      )}
    </div>
  );
}
