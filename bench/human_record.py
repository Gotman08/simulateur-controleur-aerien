"""
Enregistrement des 25 clairances du banc E2E par un locuteur HUMAIN
===================================================================
Affiche chaque phrase du corpus (les memes 25 cas EN in-grammar que
e2e_bench.py), enregistre le micro, sauvegarde un WAV 16 kHz mono par
phrase. Les prises servent ensuite a bench/human_e2e.py (boucle complete
avec locuteur humain reel).

Regle de protocole : si la LECTURE est fausse (mot saute, mauvais chiffre),
refaire la prise ('n') — une erreur de lecture n'est pas une erreur du
systeme, la verite terrain est la phrase ecrite.

Execution (console PowerShell ou cmd, PAS via un IDE) :
  bench\\bench-env\\Scripts\\python.exe bench\\human_record.py --speaker nicolas
Options :
  --list-devices        liste les micros disponibles puis quitte
  --device N            index du micro (defaut : peripherique par defaut)
  --start N             reprendre a la phrase N (1..25)
  --max-n N             nombre de phrases (defaut 25, comme le banc)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

REC_SR = 48000      # capture (universellement supporte), reechantillonne en 16 k
OUT_SR = 16000      # frequence du pipeline ASR (identique au micro de l'app)


def to_16k(data: np.ndarray) -> np.ndarray:
    from math import gcd
    from scipy.signal import resample_poly
    g = gcd(REC_SR, OUT_SR)
    return resample_poly(data, OUT_SR // g, REC_SR // g).astype(np.float32)


def record_until_enter(sd, device):
    frames = []

    def cb(indata, nframes, t, status):
        frames.append(indata.copy())

    with sd.InputStream(samplerate=REC_SR, channels=1, dtype="float32",
                        callback=cb, device=device):
        input("      ... parle, puis [Entree] pour ARRETER ")
    if not frames:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(frames)[:, 0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default="locuteur1",
                    help="nom du locuteur (sous-dossier de sortie)")
    ap.add_argument("--device", type=int, default=None)
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--max-n", type=int, default=25)
    args = ap.parse_args()

    import sounddevice as sd
    if args.list_devices:
        print(sd.query_devices())
        return

    import soundfile as sf
    import e2e_bench
    cases = e2e_bench.controller_cases(args.max_n)
    out_dir = os.path.join(HERE, "results", "human_audio", args.speaker)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": f"c{i:02d}", "text": c["phrase"]}
                   for i, c in enumerate(cases)], f, ensure_ascii=False, indent=1)

    print(f"\n=== Enregistrement locuteur '{args.speaker}' : "
          f"{len(cases)} phrases, sortie {out_dir} ===")
    print("Conseils : piece calme, micro habituel du PC, debit naturel de")
    print("phraseologie. Relis la phrase avant de lancer la prise.\n")

    i = args.start - 1
    while i < len(cases):
        case = cases[i]
        path = os.path.join(out_dir, f"c{i:02d}_clean.wav")
        deja = "  [deja enregistre, Entree pour refaire, 's' pour sauter]" \
            if os.path.exists(path) else ""
        print(f"\n--- Phrase {i + 1}/{len(cases)} ---{deja}")
        print(f'  >>> "{case["phrase"]}"')
        if deja:
            if input("      choix : ").strip().lower() == "s":
                i += 1
                continue
        input("      [Entree] pour COMMENCER la prise ")
        data = record_until_enter(sd, args.device)
        dur = len(data) / REC_SR
        peak = float(np.max(np.abs(data))) if len(data) else 0.0
        if dur < 1.0:
            print(f"      !! prise trop courte ({dur:.1f} s), on recommence")
            continue
        if peak < 0.02:
            print(f"      !! niveau tres faible (pic {peak:.3f}) : micro coupe ?"
                  " On recommence (verifie le peripherique avec --list-devices).")
            continue
        if peak > 0.99:
            print("      !! saturation probable, parle un peu moins fort")
        print(f"      prise : {dur:.1f} s, pic {peak:.2f}")
        while True:
            ch = input("      [Entree]=garder  r=reecouter  n=nouvelle prise : ") \
                .strip().lower()
            if ch == "r":
                sd.play(data, REC_SR)
                sd.wait()
                continue
            break
        if ch == "n":
            continue
        sf.write(path, to_16k(data), OUT_SR, subtype="PCM_16")
        print(f"      -> {os.path.basename(path)}")
        i += 1

    print(f"\n[OK] {len(cases)} phrases enregistrees dans {out_dir}")
    print("Etape suivante :")
    print("  bench\\bench-env\\Scripts\\python.exe bench\\human_e2e.py "
          f"--speaker {args.speaker}")


if __name__ == "__main__":
    main()
