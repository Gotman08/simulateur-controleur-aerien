"""
Application d'entrainement ATC - serveur local (FastAPI)
========================================================
LE point d'entree unique pour l'utilisateur. Lance le simulateur temps reel
(BlueSky via atc_sim), sert l'interface radar dans le navigateur, et orchestre
la boucle d'entrainement :

  - l'INSTRUCTEUR decrit une situation en langage naturel -> des avions
    apparaissent sur le radar (IA ROMEO si dispo, sinon generateur local) ;
  - l'ELEVE (controleur) parle (push-to-talk) ou tape une clairance -> elle est
    transcrite + interpretee + executee dans BlueSky -> l'avion manoeuvre et le
    pilote collationne (readback).

Backend IA HYBRIDE (atc_ai.AIClient) : ROMEO (Whisper/Mistral/XTTS) quand le tunnel
est ouvert, sinon repli 100 % local (le navigateur fait STT/TTS via la Web Speech API).

Lancer :  bluesky-env/Scripts/python.exe atc_app.py     (ouvre le navigateur)
"""
import os
import re
import sys
import json
import base64
import asyncio
import threading
import subprocess
import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Body, HTTPException
from fastapi.staticfiles import StaticFiles

import atc_sim
import atc_ai
import atc_exercise
import readback as RB

_HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DIST = os.path.join(os.path.dirname(_HERE), "frontend", "dist")
WEB_LEGACY = os.path.join(_HERE, "web")
SCEN_DIR = os.path.join(_HERE, "scenarios")

SIM = atc_sim.SimManager()
AI = atc_ai.AIClient()

# File d'evenements (transcript / readback / situation) a diffuser via WebSocket.
import queue
_event_q = queue.Queue()


def emit(ev):
    _event_q.put(ev)


EX = atc_exercise.ExerciseEngine(SIM, AI, emit)


# --- diffusion WebSocket -----------------------------------------------------
class WSManager:
    def __init__(self):
        self.active = set()

    async def connect(self, ws):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws):
        self.active.discard(ws)

    async def broadcast(self, msg):
        for ws in list(self.active):
            try:
                await ws.send_json(msg)
            except Exception:
                self.disconnect(ws)


MGR = WSManager()


async def _broadcaster():
    """Pousse l'etat ~8 Hz + les evenements en attente vers tous les clients."""
    while True:
        try:
            while not _event_q.empty():
                await MGR.broadcast(_event_q.get_nowait())
            msg = {"type": "state", **SIM.snapshot()}
            if EX.active:
                ex = EX.state()
                msg["exercise"] = {"elapsed_s": ex.get("elapsed_s"),
                                   "remaining_s": ex.get("remaining_s"),
                                   "score": ex.get("score")}
            await MGR.broadcast(msg)
        except Exception:
            pass
        await asyncio.sleep(0.12)


@asynccontextmanager
async def lifespan(app):
    SIM.start()
    task = asyncio.create_task(_broadcaster())
    yield
    task.cancel()
    SIM.stop()


app = FastAPI(title="ATC training app", lifespan=lifespan)


# --- coeur : interpretation -> execution -> readback -------------------------
_VERB_DESC = re.compile(r"\b(descend|descending|descent|descende[zr]|descendre)\b", re.I)
_VERB_CLIMB = re.compile(r"\b(climb|climbing|monte[zr]|monter)\b", re.I)


def _check_alt_coherence(text, orders, lines, rejected, cur_alt):
    """Garde-fou semantique : si la phrase dit 'descend' (sans 'climb'), un ordre
    ALT au-dessus du niveau actuel est incoherent (transcription tronquee ou
    hallucination du LLM) -> rejete plutot qu'execute. Et symetriquement."""
    want_desc = _VERB_DESC.search(text) and not _VERB_CLIMB.search(text)
    want_climb = _VERB_CLIMB.search(text) and not _VERB_DESC.search(text)
    if not (want_desc or want_climb):
        return orders, lines
    kept = []
    for o in orders:
        cur = cur_alt.get(o.get("callsign"))
        if o.get("action") == "ALT" and cur is not None:
            bad_up = want_desc and o["value"] > cur + 200
            bad_down = want_climb and o["value"] < cur - 200
            if bad_up or bad_down:
                sens = "« descend »" if bad_up else "« climb »"
                rejected.append(f"incohérence : {sens} entendu mais FL{int(o['value'] / 100):03d} "
                                f"est {'au-dessus' if bad_up else 'au-dessous'} du niveau actuel "
                                f"FL{int(cur / 100):03d} — ordre non exécuté")
                lines = [ln for ln in lines if ln != f"ALT {o['callsign']} {o['value']}"]
                continue
        kept.append(o)
    return kept, lines


def process_instruction(text):
    text = (text or "").strip()
    if not text:
        return {"transcript": "", "orders": [], "trafscript": [], "rejected": [], "readback_text": ""}
    res = AI.interpret(text)
    orders, lines = res.get("orders", []), res.get("trafscript", [])
    rejected = list(res.get("rejected", []))

    # Realisme radio : un indicatif absent du radar ne repond pas (et la
    # commande n'est pas envoyee au simulateur).
    snap = SIM.snapshot()
    known = {a["id"] for a in snap["aircraft"]}
    unknown = sorted({o.get("callsign") for o in orders
                      if o.get("callsign") and o["callsign"] not in known})
    if unknown:
        rejected += [f"{cs} : indicatif inconnu au radar (pas de réponse)" for cs in unknown]
        orders = [o for o in orders if o.get("callsign") in known]
        lines = [ln for ln in lines if len(ln.split()) > 1 and ln.split()[1] in known]

    cur_alt = {a["id"]: a["alt_ft"] for a in snap["aircraft"]}
    orders, lines = _check_alt_coherence(text, orders, lines, rejected, cur_alt)

    for line in lines:
        SIM.enqueue(line)
    if EX.active:
        EX.note_command(text, len(lines), len(rejected))
    rb = RB.readback_text(orders, cur_alt)
    return {"transcript": text, "orders": orders, "trafscript": lines,
            "rejected": rejected, "readback_text": rb}


def _list_scenarios():
    out = []
    if os.path.isdir(SCEN_DIR):
        for fn in sorted(os.listdir(SCEN_DIR)):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(SCEN_DIR, fn), encoding="utf-8") as f:
                        d = json.load(f)
                    out.append({"name": fn[:-5], "title": d.get("title", fn[:-5]),
                                "description": d.get("description", "")})
                except Exception:
                    pass
    return out


# --- API ---------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"mode": AI.mode(), "caps": AI.caps()}


@app.post("/api/health/refresh")
def health_refresh():
    AI.refresh_health()
    return {"mode": AI.mode(), "caps": AI.caps()}


@app.get("/api/nav")
def nav():
    return SIM.nav_static()


@app.get("/api/state")
def state():
    """Etat courant (repli si le WebSocket est indisponible / diagnostic)."""
    return SIM.snapshot()


@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": _list_scenarios()}


@app.post("/api/scenario")
def scenario(payload: dict = Body(...)):
    desc = str(payload.get("description", "")).strip()
    if not desc:
        raise HTTPException(400, "description vide")
    ac = AI.scenario(desc)
    created = SIM.create_aircraft(ac)
    emit({"type": "situation", "description": desc, "created": created, "mode": AI.mode()})
    return {"aircraft": ac, "created": created, "mode": AI.mode()}


@app.post("/api/scenario/load")
def scenario_load(payload: dict = Body(...)):
    name = os.path.basename(str(payload.get("name", "")))
    path = os.path.join(SCEN_DIR, name + ".json")
    if not os.path.isfile(path):
        raise HTTPException(404, "scenario inconnu")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("aircraft"):
        ac = atc_ai._items_to_aircraft(d["aircraft"])
    else:
        ac = AI.scenario(d.get("description", ""))
    created = SIM.create_aircraft(ac)
    emit({"type": "situation", "description": d.get("title", name), "created": created, "mode": AI.mode()})
    return {"aircraft": ac, "created": created}


@app.post("/api/weather/wind")
def weather_wind(payload: dict = Body(...)):
    d = payload.get("dir")
    if d is None or d == "":
        SIM.set_wind(None, None)
        emit({"type": "info", "message": "Vent supprimé."})
        return {"ok": True}
    SIM.set_wind(d, payload.get("spd", 0), payload.get("alt"))
    emit({"type": "info", "message": f"Vent réglé : {int(d):03d}°/{int(payload.get('spd', 0))} kt"})
    return {"ok": True}


@app.post("/api/weather/turbulence")
def weather_turb(payload: dict = Body(...)):
    lvl = float(payload.get("level", 0))
    SIM.set_turbulence(lvl)
    emit({"type": "info", "message": f"Turbulence : {'OFF' if lvl <= 0 else str(lvl) + ' m/s'}"})
    return {"ok": True}


@app.post("/api/weather/zone")
def weather_zone(payload: dict = Body(...)):
    ztype = payload.get("ztype", "storm")
    shape = payload.get("shape", "CIRCLE").upper()
    if shape == "CIRCLE":
        lat, lon = atc_sim.from_nm(float(payload["x"]), float(payload["y"]))
        coords = [lat, lon, float(payload.get("r", 12))]
    else:
        coords = []
        for px, py in payload.get("points", []):
            la, lo = atc_sim.from_nm(float(px), float(py))
            coords += [la, lo]
    SIM.add_zone(ztype, shape, coords)
    emit({"type": "info", "message": f"Zone {'orageuse' if ztype == 'storm' else 'interdite'} ajoutée."})
    return {"ok": True}


@app.post("/api/weather/clearzones")
def weather_clearzones():
    SIM.clear_zones()
    emit({"type": "info", "message": "Zones effacées."})
    return {"ok": True}


@app.post("/api/command")
def command(payload: dict = Body(...)):
    out = process_instruction(payload.get("text", ""))
    emit({"type": "exchange", "transcript": out["transcript"], "orders": out["orders"],
          "trafscript": out["trafscript"], "rejected": out["rejected"],
          "readback": out["readback_text"]})
    return out


@app.post("/api/voice")
def voice(file: UploadFile = File(...)):
    """Mode ROMEO : audio -> ASR -> interpretation -> readback synthetise (audio WAV)."""
    if not AI.caps().get("asr"):
        raise HTTPException(503, "ASR ROMEO indisponible (utilisez le mode local du navigateur)")
    wav = file.file.read()
    try:
        text = AI.asr(wav)
    except Exception as e:
        raise HTTPException(502, f"ASR ROMEO: {e}")
    out = process_instruction(text)
    audio_b64 = None
    if out["readback_text"] and AI.caps().get("tts"):
        try:
            audio_b64 = base64.b64encode(AI.tts(out["readback_text"])).decode("ascii")
        except Exception:
            audio_b64 = None
    emit({"type": "exchange", "transcript": out["transcript"], "orders": out["orders"],
          "trafscript": out["trafscript"], "rejected": out["rejected"],
          "readback": out["readback_text"]})
    out["audio_b64"] = audio_b64
    return out


@app.post("/api/sim/reset")
def sim_reset():
    if EX.active:                       # RESET pendant un exercice = abandon
        EX.stop()
    SIM.reset()
    emit({"type": "info", "message": "Simulation reinitialisee."})
    return {"ok": True}


@app.post("/api/sim/pause")
def sim_pause():
    SIM.pause()
    return {"ok": True}


@app.post("/api/sim/resume")
def sim_resume():
    SIM.resume()
    return {"ok": True}


@app.post("/api/sim/speed")
def sim_speed(payload: dict = Body(...)):
    SIM.set_speed(payload.get("value", 1.0))
    return {"ok": True}


# --- exercice (l'IA cree la situation, l'eleve s'adapte, tout est note) -------
@app.get("/api/exercise")
def exercise_state():
    return EX.state()


@app.post("/api/exercise/start")
def exercise_start(payload: dict = Body(default={})):
    if EX.active:
        raise HTTPException(409, "un exercice est déjà en cours")
    try:
        st = EX.start(difficulty=str(payload.get("difficulty", "moyen")),
                      duration_min=payload.get("duration_min"),
                      seed=payload.get("seed"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    emit({"type": "info", "message": f"Exercice {st.get('label', '')} démarré "
                                     f"({st.get('mode_ia', 'local')})."})
    return st


@app.post("/api/exercise/stop")
def exercise_stop():
    if not EX.active:
        raise HTTPException(409, "aucun exercice en cours")
    return EX.stop()


@app.get("/api/exercise/report")
def exercise_report():
    rep = EX.last_report()
    if not rep:
        raise HTTPException(404, "aucun rapport disponible")
    return rep


def _build_scn(snap):
    """Construit un scenario BlueSky (.scn) a partir de l'etat courant."""
    L = ["00:00:00.00>CDMETHOD ON", "00:00:00.00>ZONER 5", "00:00:00.00>ZONEDH 1000",
         "00:00:00.00>DTLOOK 120",
         f"00:00:00.00>PAN {atc_sim.CLAT} {atc_sim.CLON}", "00:00:00.00>ZOOM 4"]
    w = snap.get("wind")
    if w:
        L.append(f"00:00:00.00>WIND {atc_sim.CLAT} {atc_sim.CLON} {w['dir']} {w['spd']}")
    for a in snap.get("aircraft", []):
        L.append(f"00:00:00.00>CRE {a['id']} {a['type'] or 'A320'} "
                 f"{a['lat']} {a['lon']} {a['hdg']} {a['alt_ft']} {a['gs']}")
    for z in snap.get("zones", []):
        if z["shape"] == "CIRCLE":
            la, lo = atc_sim.from_nm(z["cx"], z["cy"])
            L.append(f"00:00:00.00>CIRCLE {z['name']} {la:.5f} {lo:.5f} {z['r']}")
        else:
            pts = " ".join(f"{atc_sim.from_nm(p[0], p[1])[0]:.5f} {atc_sim.from_nm(p[0], p[1])[1]:.5f}"
                           for p in z["points"])
            L.append(f"00:00:00.00>POLY {z['name']} {pts}")
    return "\n".join(L) + "\n"


@app.post("/api/gui/launch")
def gui_launch():
    """Exporte la situation en .scn et lance le GUI natif de BlueSky dessus."""
    try:
        import PyQt5  # noqa: F401
    except Exception:
        try:
            import PyQt6  # noqa: F401
        except Exception:
            raise HTTPException(503, "GUI natif BlueSky indisponible : installez PyQt5 et PyOpenGL "
                                     "(bluesky-env/Scripts/python.exe -m pip install pyqt5 pyopengl).")
    scn = _build_scn(SIM.snapshot())
    scen_dir = os.path.join(os.path.expanduser("~"), "bluesky", "scenario")
    if os.path.isdir(scen_dir):
        path, arg = os.path.join(scen_dir, "atc_trainer_export.scn"), "atc_trainer_export.scn"
    else:
        os.makedirs(os.path.join(_HERE, "demo_out"), exist_ok=True)
        path = arg = os.path.join(_HERE, "demo_out", "atc_trainer_export.scn")
    with open(path, "w", encoding="utf-8") as f:
        f.write(scn)
    try:
        subprocess.Popen([sys.executable, "-m", "bluesky", arg], cwd=_HERE)
    except Exception as e:
        raise HTTPException(500, f"lancement BlueSky: {e}")
    emit({"type": "info", "message": "Fenêtre BlueSky native lancée (situation exportée)."})
    return {"ok": True, "scenario": path}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await MGR.connect(websocket)
    try:
        # envoi initial immediat
        await websocket.send_json({"type": "state", **SIM.snapshot()})
        while True:
            await websocket.receive_text()        # keepalive (messages ignores)
    except WebSocketDisconnect:
        MGR.disconnect(websocket)
    except Exception:
        MGR.disconnect(websocket)


# --- interface web (SPA buildee dans frontend/dist, repli sur src/web) --------
_WEB_ROOT = WEB_DIST if os.path.isdir(WEB_DIST) else WEB_LEGACY
if os.path.isdir(_WEB_ROOT):
    if _WEB_ROOT == WEB_LEGACY:         # l'ancienne page reference /static/*
        app.mount("/static", StaticFiles(directory=WEB_LEGACY), name="static")
    # Monte en DERNIER : toutes les routes /api et /ws ci-dessus restent prioritaires.
    app.mount("/", StaticFiles(directory=_WEB_ROOT, html=True), name="web")


def main():
    import uvicorn
    host = os.environ.get("ATC_APP_HOST", "127.0.0.1")
    port = int(os.environ.get("ATC_APP_PORT", "8000"))
    url = f"http://{host}:{port}"
    print(f"[*] Application d'entrainement ATC : {url}")
    print(f"[*] Backend IA : mode={AI.mode()}  caps={AI.caps()}")
    if os.environ.get("ATC_APP_NOBROWSER") != "1":
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
