"""
Echange radio controleur <-> pilote (les avions PARLENT)
========================================================
Pour chaque instruction : le controleur parle (TTS voix + VHF) -> /asr -> /interpret
-> BlueSky execute -> le PILOTE collationne (readback) dans la voix clonee de l'avion
(+ VHF). On verifie que le readback est intelligible (re-/asr) et on assemble un
fichier d'echange radio par instruction + une bande son de session complete.

Prerequis : tunnel + serveur actifs. Lancer : bluesky-env/Scripts/python.exe voice_exchange.py
Sorties : demo_out/exchange_<i>.wav (ctrl+pilote), demo_out/session_radio.wav
"""
import os
import io
import numpy as np
import soundfile as sf

import bluesky_runtime as bsk
import pipeline_e2e as P          # tts(), asr(), interpret()
import readback as RB

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_out")
SR = 16000
CTRL_VOICE = "pilot_2.wav"        # voix du controleur

# (callsign, type, lat, lon, hdg, alt_ft, spd_kt, voix_pilote)
FLEET = [
    ("AFR1234", "A320", 49.45, 3.6, 90, 13000, 250, "pilot_1.wav"),
    ("BAW57",   "B738", 49.05, 3.8, 90, 20000, 300, "pilot_3.wav"),
    ("RYR9",    "B738", 48.80, 4.2, 90, 9000,  240, "pilot_1.wav"),
]
EXCHANGES = [
    "air france one two three four descend flight level one zero zero",
    "speedbird five seven turn right heading one eight zero",
    "ryanair niner climb flight level two four zero",
]


def arr(b):
    a, _ = sf.read(io.BytesIO(b), dtype="float32")
    return a if a.ndim == 1 else a.mean(axis=1)


def sil(s):
    return np.zeros(int(s * SR), dtype=np.float32)


def main():
    os.makedirs(OUT, exist_ok=True)
    voice = {cs: v for cs, *_, v in FLEET}
    bsk.bs(); bsk.reset()
    for cs, typ, lat, lon, hdg, alt, spd, _ in FLEET:
        bsk.create(cs, typ, lat, lon, hdg, alt, spd)

    session = []
    print("=== ECHANGE RADIO CONTROLEUR <-> PILOTE ===")
    for i, instr in enumerate(EXCHANGES, 1):
        ctrl_wav = P.tts(instr, CTRL_VOICE, vhf=True)          # le controleur parle
        stt = P.asr(ctrl_wav)
        res = P.interpret(stt)
        st = {s["id"]: s for s in bsk.state()}
        cur_alt = {cs: st[cs]["alt_ft"] for cs in st}
        for line in res["trafscript"]:
            bsk.cmd(line)
        cs = res["orders"][0]["callsign"] if res["orders"] else None
        rb = RB.readback_text(res["orders"], cur_alt)
        pv = voice.get(cs, "pilot_1.wav")

        print(f"\n[{i}] CONTROLEUR : \"{instr}\"")
        print(f"     -> ASR \"{stt}\"  -> {res['trafscript']}")
        if rb:
            pilot_wav = P.tts(rb, pv, vhf=True)                # l'AVION repond (voix clonee)
            rb_stt = P.asr(pilot_wav)                          # readback intelligible ?
            print(f"     PILOTE ({cs}, voix {pv}) : \"{rb}\"")
            print(f"     -> readback re-transcrit : \"{rb_stt}\"")
            ca, pa = arr(ctrl_wav), arr(pilot_wav)
            ex = np.concatenate([ca, sil(0.5), pa])
            sf.write(os.path.join(OUT, f"exchange_{i}.wav"), ex, SR)
            session += [ca, sil(0.4), pa, sil(0.9)]
        else:
            print("     (aucun ordre exploitable -> pas de readback)")
        bsk.advance(60)

    if session:
        sf.write(os.path.join(OUT, "session_radio.wav"), np.concatenate(session), SR)
        dur = sum(len(x) for x in session) / SR
        print(f"\n[OK] demo_out/session_radio.wav ({dur:.0f}s) + exchange_*.wav")
    print("\n=== ETAT FINAL ===")
    for s in bsk.state():
        if s["id"] in voice:
            print(f"  {s['id']}: cap {s['hdg']:.0f}  FL{int(round(s['alt_ft']/100)):03d}  {s.get('cas_kt')}kt")


if __name__ == "__main__":
    main()
