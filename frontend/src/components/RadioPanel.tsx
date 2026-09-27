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
  const { pushLog } = hub;
  const [text, setText] = useState("");
  const [talking, setTalking] = useState(false);
  const [busy, setBusy] = useState(false);
  const wavRef = useRef<WavRecorder | null>(null);
  const pendingRef = useRef(false);
  const connectionRef = useRef(hub.connection);
  connectionRef.current = hub.connection;
  const providersRef = useRef(hub.providers);
  providersRef.current = hub.providers;
  const talkingRef = useRef(false);
  talkingRef.current = talking;
  useEffect(() => () => { void wavRef.current?.stop(); wavRef.current = null; }, []);

  // selection d'un avion au radar -> indicatif pre-rempli
  useEffect(() => {
    if (prefill) setText((t) => (t.trim() ? t : prefill + " "));
  }, [prefill]);

  const send = useCallback(async (t: string) => {
    const txt = t.trim();
    if (!txt || pendingRef.current || connectionRef.current !== "connected") return;
    pendingRef.current = true;
    setBusy(true);
    try {
      await api.command(txt);          // readback texte + audio arrivent via l'event WS
      setText("");
    } catch (e) {
      pushLog("rej", `Erreur commande : ${e}`);
    } finally {
      pendingRef.current = false;
      setBusy(false);
    }
  }, [pushLog]);

  const startTalk = useCallback(async () => {
    if (wavRef.current || pendingRef.current || connectionRef.current !== "connected") return;
    if (!providersRef.current.stt) {
      pushLog("rej", "Service de reconnaissance vocale indisponible. Tapez la clairance.");
      return;
    }
    const rec = new WavRecorder();
    wavRef.current = rec;
    setTalking(true);
    try {
      await rec.start();               // si stopTalk arrive pendant l'attente,
    } catch (e) {                      // WavRecorder (flag cancelled) ferme le flux
      pushLog("rej", `Micro indisponible : ${e}`);
      if (wavRef.current === rec) wavRef.current = null;
      setTalking(false);
    }
  }, [pushLog]);

  const stopTalk = useCallback(async () => {
    setTalking(false);
    // Nulle la ref AVANT l'await : un second stopTalk concurrent (keyup V +
    // blur quasi simultanes) ne doit pas renvoyer le meme audio deux fois.
    const rec = wavRef.current;
    wavRef.current = null;
    if (!rec) return;
    pendingRef.current = true;
    setBusy(true);
    try {
      const wav = await rec.stop();
      if (!wav) return;
      await api.voice(wav);            // reponse (texte + audio) via l'event WS
    } catch (e) {
      pushLog("rej", `Erreur transmission : ${e}`);
    } finally {
      pendingRef.current = false;
      setBusy(false);
    }
  }, [pushLog]);

  // touche « V » = alternat (hors champs de saisie)
  useEffect(() => {
    const isTyping = (t: EventTarget | null) =>
      t instanceof HTMLElement && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(t.tagName));
    // Ctrl+V / Cmd+V / Alt+V restent des raccourcis systeme (coller...) :
    // seul « V » nu declenche l'alternat.
    const plainV = (e: KeyboardEvent) =>
      e.code === "KeyV" && !e.ctrlKey && !e.metaKey && !e.altKey;
    const down = (e: KeyboardEvent) => {
      if (plainV(e) && !isTyping(e.target) && !e.repeat) { e.preventDefault(); void startTalk(); }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "KeyV" && wavRef.current) { e.preventDefault(); void stopTalk(); }
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
      <button
        type="button"
        disabled={busy || hub.connection !== "connected"}
        aria-label="Transmission radio : maintenir pour parler"
        onPointerDown={(e) => { if (e.button === 0) { e.currentTarget.setPointerCapture(e.pointerId); void startTalk(); } }}
        onPointerUp={() => void stopTalk()}
        onPointerCancel={() => void stopTalk()}
        onKeyDown={(e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); void startTalk(); } }}
        onKeyUp={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); void stopTalk(); } }}
        onBlur={() => { if (wavRef.current) void stopTalk(); }}
        aria-live="polite"
        className={`flex w-full select-none items-center justify-center gap-1.5 rounded-lg
          border px-4 py-3 text-[13px] font-medium transition-colors disabled:opacity-50 ${talking
            ? "border-dang bg-dang text-white"
            : "border-edge bg-panel2 text-mut"}`}
        title="Maintenir la touche V pour parler"
      >
        <Mic size={15} className={talking ? "inline" : "inline opacity-70"} />
        {talking
          ? "TRANSMISSION…"
          : busy
            ? "TRAITEMENT…"
            : "Maintenir pour parler · V"}
      </button>

      <div className="mt-2 flex gap-2">
        <Input
          className="flex-1 font-mono"
          aria-label="Clairance radio"
          disabled={busy || hub.connection !== "connected"}
          placeholder="air france one two three four descend flight level one zero zero"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void send(text);
          }}
        />
        <Btn variant="primary" title="Envoyer la clairance" disabled={busy || !text.trim() || hub.connection !== "connected"} onClick={() => void send(text)}>
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
