/** Panneau instructeur : generation de situation en langage naturel, scenarios
 *  sauvegardes, meteo (vent / turbulence / zones) et GUI BlueSky natif. */
import { useEffect, useState } from "react";
import { CloudLightning, Mic, MonitorUp, OctagonMinus, Sparkles, Wind, X } from "lucide-react";
import { api } from "../api";
import { getRecognition } from "../audio";
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

  useEffect(() => {
    api.scenarios().then((r) => setScenarios(r.scenarios)).catch(() => undefined);
  }, []);

  const generate = async () => {
    if (!desc.trim()) return;
    setGenBusy(true);
    hub.pushLog("info", `✈ Génération : ${desc.trim()}`);
    try { await api.generateScenario(desc.trim()); }
    catch (e) { hub.pushLog("rej", `Erreur génération : ${e}`); }
    finally { setGenBusy(false); }
  };

  const dictate = () => {
    const r = getRecognition();
    if (!r) { hub.pushLog("rej", "Dictée indisponible."); return; }
    r.onresult = (e) => setDesc(e.results[0][0].transcript);
    r.onerror = () => undefined;
    try { r.start(); } catch { /* deja en cours */ }
  };

  return (
    <>
      <Section title="Situation (langage naturel)">
        <textarea
          className="min-h-[60px] w-full resize-y rounded-md border border-edge bg-panel2 px-2.5
            py-1.5 text-[13px] text-ink outline-none placeholder:text-mut/60 focus:border-acc/60"
          placeholder="ex : three A320 from the north at FL300 heading 180, 8 miles apart — ou en français"
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && e.ctrlKey) void generate(); }}
        />
        <Row>
          <Btn variant="primary" className="flex-1" disabled={genBusy} onClick={() => void generate()}>
            <Sparkles size={13} className="mr-1 inline" />
            {genBusy ? "Génération…" : "Générer la situation"}
          </Btn>
          <Btn title="Dicter la situation" onClick={dictate}><Mic size={14} /></Btn>
        </Row>
        <Row>
          <select
            className="min-w-0 flex-1 rounded-md border border-edge bg-panel2 px-2 py-1.5 text-[13px]"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          >
            <option value="">— scénarios sauvegardés —</option>
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
              void api.setWind(+windDir, +(windSpd || 0), windFl ? +windFl * 100 : undefined);
            }}
          >
            <Wind size={13} className="mr-1 inline" />Vent
          </Btn>
          <Btn variant="ghost" title="Effacer le vent" onClick={() => void api.setWind("")}>
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
