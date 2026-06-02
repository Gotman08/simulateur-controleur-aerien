"""
Pipeline bout-en-bout - Semaines 6&8 (V6/V7/V8)
===============================================
Orchestrateur LOCAL qui ferme la boucle, en s'appuyant sur le serveur ROMEO
(via tunnel SSH localhost:8765) et BlueSky local :

  texte ATC --/tts (voix clonee + VHF)--> audio --/asr--> transcription
        --/interpret--> JSON/TrafScript --> BlueSky execute --> etat des vols

Demontre : synthese vocale (S6), re-transcription (boucle voix), interpretation
ancree (S5) et execution simulateur (S8). Sauvegarde les audios dans demo_out/.

Prerequis : tunnel ouvert (tunnel.sh) + serveur lance (job_server.slurm) + venv BlueSky.
Lancer :  bluesky-env/Scripts/python.exe pipeline_e2e.py
"""
import os
import io
import json
import argparse
import requests
import numpy as np
import soundfile as sf

import bluesky_runtime as bsk

SERVER = os.environ.get("ATC_SERVER", "http://localhost:8765")       # ASR + interpret (GPU0)
TTS_SERVER = os.environ.get("ATC_TTS_SERVER", "http://localhost:8766")  # TTS XTTS (GPU1)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_out")

# scenario : (instruction du controleur, voix de reference a cloner)
SCENARIO = [
    ("air france one two three four descend flight level one hundred", "pilot_1.wav"),
    ("air france one two three four turn right heading two seven zero", "pilot_1.wav"),
    ("csa one delta zulu climb flight level two four zero reduce speed two five zero", "pilot_3.wav"),
]


def wer(ref, hyp):
    r, h = ref.lower().split(), hyp.lower().split()
    n, m = len(r), len(h)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c = 0 if r[i - 1] == h[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
    return d[n][m] / max(1, n)


def tts(text, voice, vhf=True):
    r = requests.post(f"{TTS_SERVER}/tts", json={"text": text, "voice": voice, "vhf": vhf}, timeout=180)
    r.raise_for_status()
    return r.content


def asr(wav_bytes):
    r = requests.post(f"{SERVER}/asr", files={"file": ("utt.wav", wav_bytes, "audio/wav")}, timeout=180)
    r.raise_for_status()
    return r.json()["text"]


def interpret(text):
    r = requests.post(f"{SERVER}/interpret", json={"text": text}, timeout=180)
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--advance", type=float, default=90.0, help="secondes de sim par instruction")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print(f"[*] serveur : {SERVER} | health : {requests.get(SERVER + '/health', timeout=30).json()}")
    bsk.bs(); bsk.reset()
    created = {}
    wers = []

    for i, (text, voice) in enumerate(SCENARIO, 1):
        print(f"\n================= ECHANGE {i} =================")
        print(f"[controleur] {text}")

        # 1) synthese vocale (voix clonee + VHF)
        wav = tts(text, voice, vhf=True)
        wpath = os.path.join(OUT, f"ex{i}_{voice.replace('.wav','')}.wav")
        with open(wpath, "wb") as f:
            f.write(wav)
        print(f"  1) /tts  -> {wpath} ({len(wav)} octets, voix={voice}, VHF)")

        # 2) re-transcription (boucle voix)
        stt = asr(wav)
        w = wer(text, stt)
        wers.append(w)
        print(f"  2) /asr  -> \"{stt}\"  (WER vs texte = {w*100:.0f} %)")

        # 3) interpretation ancree -> JSON/TrafScript
        res = interpret(stt)
        print(f"  3) /interpret -> {json.dumps(res['orders'], ensure_ascii=False)}")
        if res["rejected"]:
            print(f"     rejets securite : {res['rejected']}")

        # 4) execution BlueSky
        for o in res["orders"]:
            cs = o.get("callsign")
            if cs and cs not in created:
                bsk.create(cs, "A320", 48.0 + 0.1 * len(created), 2.0, 90, 12000, 250)
                created[cs] = True
        before = {s["id"]: s for s in bsk.state()}
        for line in res["trafscript"]:
            bsk.cmd(line)
            print(f"  4) BlueSky <- {line}")
        bsk.advance(args.advance)
        after = {s["id"]: s for s in bsk.state()}
        for line in res["trafscript"]:
            cs = line.split()[1] if len(line.split()) > 1 else None
            if cs in before and cs in after:
                b, a = before[cs], after[cs]
                print(f"     {cs} : hdg {b['hdg']}->{a['hdg']} | alt_ft {b['alt_ft']}->{a['alt_ft']} | cas {b.get('cas_kt')}->{a.get('cas_kt')}")

    print(f"\n[V6/V7/V8] boucle complete OK | WER moyen re-transcription = {100*sum(wers)/len(wers):.0f} %")
    print(f"[*] audios : {OUT}")


if __name__ == "__main__":
    main()
