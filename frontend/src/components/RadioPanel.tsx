/** Poste radio du controleur : push-to-talk (touche « V » maintenue) + saisie
 *  texte + dernier echange. Chemin UNIQUE : capture WAV -> /api/voice (API STT)
 *  -> interpretation -> collationnement TOUJOURS vocalise par l'API TTS (audio
 *  joue par l'event WebSocket "exchange", commande tapee ou parlee). */
import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, SendHorizonal } from "lucide-react";
import { api } from "../api";
import { WavRecorder } from "../audio";
import { type SimHub } from "../useSim";
import { Btn, Input } from "./ui";

export default function RadioPanel({ hub, prefill }: { hub: SimHub; prefill: string }) {
  const [text, setText] = useState("");
  const [talking, setTalking] = useState(false);
  const [busy, setBusy] = useState(false);
  const wavRef = useRef<WavRecorder | null>(null);
  const providersRef = useRef(hub.providers);
  providersRef.current = hub.providers;
  const talkingRef = useRef(false);
  talkingRef.current = talking;

  // selection d'un avion au radar -> indicatif pre-rempli
  useEffect(() => {
    if (prefill) setText((t) => (t.trim() ? t : prefill + " "));
  }, [prefill]);

  const send = useCallback(async (t: string) => {
    const txt = t.trim();
    if (!txt) return;
    try {
      await api.command(txt);          // readback texte + audio arrivent via l'event WS
    } catch (e) {
      hub.pushLog("rej", `⊘ Erreur commande : ${e}`);
    }
  }, [hub]);

  const startTalk = useCallback(async () => {
    if (wavRef.current) return;        // deja en cours d'emission
    if (!providersRef.current.stt) {
      hub.pushLog("rej", "⊘ STT non configuré ou injoignable (voir .env) - tapez la clairance.");
      return;
    }
    const rec = new WavRecorder();
    wavRef.current = rec;
    setTalking(true);
    try {
      await rec.start();               // si stopTalk arrive pendant l'attente,
    } catch (e) {                      // WavRecorder (flag cancelled) ferme le flux
      hub.pushLog("rej", `⊘ Micro indisponible : ${e}`);
      if (wavRef.current === rec) wavRef.current = null;
      setTalking(false);
    }
  }, [hub]);

  const stopTalk = useCallback(async () => {
    setTalking(false);
    // Nulle la ref AVANT l'await : un second stopTalk concurrent (keyup V +
    // blur quasi simultanes) ne doit pas renvoyer le meme audio deux fois.
    const rec = wavRef.current;
    wavRef.current = null;
    if (!rec) return;
    const wav = await rec.stop();
    if (!wav) return;
    setBusy(true);
    try {
      await api.voice(wav);            // reponse (texte + audio) via l'event WS
    } catch (e) {
      hub.pushLog("rej", `⊘ Erreur /api/voice : ${e}`);
    } finally {
      setBusy(false);
    }
  }, [hub]);

  // touche « V » = alternat (hors champs de saisie)
  useEffect(() => {
    const isTyping = (t: EventTarget | null) =>
      t instanceof HTMLElement && (t.tagName === "INPUT" || t.tagName === "TEXTAREA");
    // Ctrl+V / Cmd+V / Alt+V restent des raccourcis systeme (coller...) :
    // seul « V » nu declenche l'alternat.
    const plainV = (e: KeyboardEvent) =>
      e.code === "KeyV" && !e.ctrlKey && !e.metaKey && !e.altKey;
    const down = (e: KeyboardEvent) => {
      if (plainV(e) && !isTyping(e.target) && !e.repeat) { e.preventDefault(); void startTalk(); }
    };
    const up = (e: KeyboardEvent) => {
      if (plainV(e) && !isTyping(e.target)) { e.preventDefault(); void stopTalk(); }
    };
    // Si le focus est perdu pendant la transmission (alt-tab, popup permission
    // micro...), le keyup « V » peut ne jamais arriver : on coupe le micro pour
    // eviter une transmission bloquee / un micro laisse ouvert.
    const stopIfTalking = () => { if (talkingRef.current) void stopTalk(); };
    const onVisibility = () => { if (document.hidden) stopIfTalking(); };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", stopIfTalking);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", stopIfTalking);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [startTalk, stopTalk]);

  const m = hub.lastExchange;
  return (
    <div className="shrink-0 border-t border-edge bg-panel px-4 py-3">
      <div
        aria-live="polite"
        className={`flex w-full select-none items-center justify-center gap-1.5 rounded-lg
          border-2 px-4 py-3.5 text-[14px] font-bold tracking-wide transition-colors ${talking
            ? "border-dang bg-dang text-white"
            : "border-edge bg-panel2 text-mut"}`}
        title="Maintenir la touche V pour parler"
      >
        <Mic size={15} className={talking ? "inline" : "inline opacity-70"} />
        {talking
          ? "TRANSMISSION…"
          : busy
            ? "TRAITEMENT…"
            : "MAINTENIR « V » POUR PARLER"}
      </div>

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
