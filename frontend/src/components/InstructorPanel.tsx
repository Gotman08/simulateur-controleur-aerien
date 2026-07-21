/** Panneau instructeur : generation de situation en langage naturel, scenarios
 *  sauvegardes, meteo (vent / turbulence / zones) et GUI BlueSky natif. */
import { useEffect, useRef, useState } from "react";
import { CloudLightning, Mic, MonitorUp, OctagonMinus, Sparkles, Wind, X } from "lucide-react";
import { api } from "../api";
import { WavRecorder } from "../audio";
import type { PlaceMode, ScenarioMeta } from "../types";
import type { SimHub } from "../useSim";
import { Btn, Input, Row, Section } from "./ui";

export default function InstructorPanel({ hub, placeMode, setPlaceMode }: {
  hub: SimHub;
  placeMode: PlaceMode;
  setPlaceMode: (m: PlaceMode) => void;
}) {
  const [desc, setDesc] = useState("");
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([]);
  const [scenario, setScenario] = useState("");
  const [windDir, setWindDir] = useState("");
  const [windSpd, setWindSpd] = useState("");
  const [windFl, setWindFl] = useState("");
  const [turb, setTurb] = useState(0);
  const [genBusy, setGenBusy] = useState(false);
  const [dictating, setDictating] = useState(false);
  const recRef = useRef<WavRecorder | null>(null);

  useEffect(() => {
    api.scenarios().then((r) => setScenarios(r.scenarios)).catch(() => undefined);
  }, []);

  // Le panneau est monte conditionnellement (onglets) : couper le micro si
  // l'utilisateur change d'onglet pendant une dictee (sinon flux orphelin).
  useEffect(() => () => { void recRef.current?.stop(); recRef.current = null; }, []);

  const generate = async () => {
    if (!desc.trim()) return;
    setGenBusy(true);
    hub.pushLog("info", `✈ Génération : ${desc.trim()}`);
    try { await api.generateScenario(desc.trim()); }
    catch (e) { hub.pushLog("rej", `Erreur génération : ${e}`); }
    finally { setGenBusy(false); }
  };

  // Dictee via l'API STT (clic = demarrer, re-clic = arreter + transcrire).
  const dictate = async () => {
    if (recRef.current) {                       // arret + transcription
      setDictating(false);
      const rec = recRef.current;               // ref nullee AVANT l'await :
      recRef.current = null;                    // pas de double transcription
      const wav = await rec.stop();
      if (!wav) return;
      try {
        const { text } = await api.transcribe(wav);
        if (text) setDesc(text);
      } catch (e) { hub.pushLog("rej", `⊘ Dictée : ${e}`); }
      return;
    }
    if (!hub.providers.stt) {
      hub.pushLog("rej", "⊘ STT non configuré ou injoignable - tapez la situation.");
      return;
    }
    const rec = new WavRecorder();
    recRef.current = rec;                       // pose AVANT l'await : un second
    setDictating(true);                         // clic prend la branche "arret"
    try {
      await rec.start();
    } catch (e) {
      hub.pushLog("rej", `⊘ Micro indisponible : ${e}`);
      if (recRef.current === rec) recRef.current = null;
      setDictating(false);
    }
  };

  return (
    <>
      <Section title="Situation (langage naturel)">
        <textarea
          className="min-h-[60px] w-full resize-y rounded-md border border-edge bg-panel2 px-2.5
            py-1.5 text-[13px] text-ink outline-none placeholder:text-mut/60 focus:border-acc/60"
          placeholder="ex : three A320 from the north at FL300 heading 180, 8 miles apart - ou en français"
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && e.ctrlKey) void generate(); }}
        />
        <Row>
          <Btn variant="primary" className="flex-1" disabled={genBusy} onClick={() => void generate()}>
            <Sparkles size={13} className="mr-1 inline" />
            {genBusy ? "Génération…" : "Générer la situation"}
          </Btn>
          <Btn
            title={dictating ? "Arrêter et transcrire (API STT)" : "Dicter la situation (API STT)"}
            className={dictating ? "!border-dang/70 !text-dang" : ""}
            onClick={() => void dictate()}
          >
            <Mic size={14} />
          </Btn>
        </Row>
        <Row>
          <select
            className="min-w-0 flex-1 rounded-md border border-edge bg-panel2 px-2 py-1.5 text-[13px]"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          >
            <option value="">- scénarios sauvegardés -</option>
            {scenarios.map((s) => (
              <option key={s.name} value={s.name} title={s.description}>{s.title}</option>
            ))}
          </select>
          <Btn
            disabled={!scenario}
            onClick={() => void api.loadScenario(scenario).catch((e) => hub.pushLog("rej", `Chargement : ${e}`))}
          >
            Charger
          </Btn>
        </Row>
      </Section>

      <Section title="Météo & zones">
        <Row>
          <Input className="w-16 font-mono" placeholder="dir°" value={windDir}
            onChange={(e) => setWindDir(e.target.value)} />
          <Input className="w-14 font-mono" placeholder="kt" value={windSpd}
            onChange={(e) => setWindSpd(e.target.value)} />
          <Input className="w-16 font-mono" placeholder="FL (opt)" value={windFl}
            onChange={(e) => setWindFl(e.target.value)} />
          <Btn
            onClick={() => {
              if (windDir === "") return;
              const dir = Number(windDir);
              const spd = Number(windSpd || 0);
              const fl = windFl ? Number(windFl) : undefined;
              // saisie non numerique -> NaN serialise null -> 400 backend :
              // on valide ICI avec un message clair, sans requete inutile.
              if (!Number.isFinite(dir) || !Number.isFinite(spd) || (fl !== undefined && !Number.isFinite(fl))) {
                hub.pushLog("rej", "⊘ Vent : direction/vitesse/FL doivent être numériques");
                return;
              }
              void api.setWind(dir, spd, fl !== undefined ? fl * 100 : undefined)
                .catch((e) => hub.pushLog("rej", `⊘ Vent : ${e}`));
            }}
          >
            <Wind size={13} className="mr-1 inline" />Vent
          </Btn>
          <Btn variant="ghost" title="Effacer le vent"
            onClick={() => void api.setWind("").catch((e) => hub.pushLog("rej", `⊘ Vent : ${e}`))}>
            <X size={13} />
          </Btn>
        </Row>
        <Row>
          <label className="flex flex-1 items-center gap-2 text-[12.5px] text-mut">
            turbulence
            <input
              type="range" min={0} max={8} step={1} value={turb} className="flex-1"
              onChange={(e) => { setTurb(+e.target.value); void api.setTurbulence(+e.target.value); }}
            />
            <span className="w-4 font-mono text-acc">{turb}</span>
          </label>
        </Row>
        <Row>
          <Btn
            className={placeMode === "storm" ? "!border-mag/70 !text-mag" : ""}
            title="Placer une cellule orageuse d'un clic sur le radar"
            onClick={() => setPlaceMode(placeMode === "storm" ? null : "storm")}
          >
            <CloudLightning size={13} className="mr-1 inline" />Cellule orageuse
          </Btn>
          <Btn
            className={placeMode === "restricted" ? "!border-dang/70 !text-dang" : ""}
            title="Placer une zone interdite d'un clic sur le radar"
            onClick={() => setPlaceMode(placeMode === "restricted" ? null : "restricted")}
          >
            <OctagonMinus size={13} className="mr-1 inline" />Zone interdite
          </Btn>
          <Btn variant="ghost" onClick={() => void api.clearZones()}>effacer</Btn>
        </Row>
        {placeMode && (
          <p className="mt-2 text-[11.5px] text-warn">
            Cliquez sur le radar pour placer {placeMode === "storm" ? "la cellule orageuse" : "la zone interdite"}.
          </p>
        )}
      </Section>

      <Section title="Outils">
        <Btn
          className="w-full"
          title="Exporte la situation en .scn et ouvre la fenêtre Qt officielle de BlueSky"
          onClick={async () => {
            hub.pushLog("info", "Lancement du GUI BlueSky natif…");
            try { await api.launchGui(); }
            catch (e) { hub.pushLog("rej", `GUI : ${e}`); }
          }}
        >
          <MonitorUp size={13} className="mr-1 inline" />GUI BlueSky natif
        </Btn>
      </Section>
    </>
  );
}
