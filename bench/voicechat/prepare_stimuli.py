"""
Preparation du jeu de stimuli pour la campagne VoiceChat-11B
===========================================================
Reconstruit, avec le code EXACT du banc (`bench/e2e_bench.py`), les enonces
controleur deja utilises pour mesurer la chaine en cascade, de facon a
obtenir une comparaison APPARIEE (meme phrase, meme audio, meme bruit) :

  sapi_radio    voix SAPI + canal radio (passe-bande VHF 300-3400 Hz,
                bruit additif SNR 12 dB, graine 7)  -> apparie avec les
                76 % de `e2e_bench_romeo.json`
  sapi_propre   voix SAPI sans degradation          -> isole l'effet du canal
  humain_micro  locuteur humain (nicolas), micro brut -> apparie avec les 80 %
                de `human_e2e.json`
  humain_radio  locuteur humain + meme canal radio    -> apparie avec les 72 %

Sortie : <staging>/wav/<condition>/cNN.wav (16 kHz mono PCM16) + manifest.json
puis une archive tar.gz transferee vers le disque RAM du noeud ROMEO.

Usage : bench\\bench-env\\Scripts\\python.exe bench\\voicechat\\prepare_stimuli.py
"""
from __future__ import annotations

import argparse
import json
import io
import os
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.dirname(HERE)
ROOT = os.path.dirname(BENCH)
for p in (BENCH, os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
import soundfile as sf
from math import gcd
from scipy.signal import resample_poly

import bench_corpus
import e2e_bench

E2E_AUDIO = os.path.join(BENCH, "results", "e2e_audio")
HUMAN_AUDIO = os.path.join(BENCH, "results", "human_audio", "nicolas")
STAGING = os.path.join(BENCH, "results", "voicechat_stimuli")
CLUSTER_ROOT = "/dev/shm/vc/stim"


def to_16k_mono(path):
    """Lecture + reechantillonnage 16 kHz mono, sans degradation (temoin)."""
    data, sr = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        g = gcd(int(sr), 16000)
        data = resample_poly(data, 16000 // g, int(sr) // g).astype(np.float32)
    return data


def pad(samples, avant_s, apres_s):
    """Silence avant/apres l'enonce.

    NECESSAIRE, pas cosmetique : VoiceChat est un modele full-duplex
    SYNCHRONE A LA TRAME - il emet une trame de sortie par trame d'entree.
    Sans silence apres la clairance, le modele n'a aucune trame disponible
    pour prononcer son collationnement ni pour terminer son appel d'outil.
    Les echantillons officiels de NVIDIA portent 3,9 s (sample_general) a
    4,7 s (sample_fc) de silence final : on retient 6 s, ce qui correspond
    aussi a la realite operationnelle (le controleur relache l'alternat, la
    frequence reste ouverte pendant que le pilote collationne).
    Le signal de PAROLE reste bit a bit celui de la cascade : seul du
    silence numerique est ajoute autour."""
    n_av = int(round(avant_s * 16000))
    n_ap = int(round(apres_s * 16000))
    return np.concatenate([np.zeros(n_av, dtype=np.float32),
                           np.asarray(samples, dtype=np.float32),
                           np.zeros(n_ap, dtype=np.float32)])


def wav_bytes_to_samples(b):
    data, sr = sf.read(io.BytesIO(b), dtype="float32")
    assert sr == 16000, sr
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--silence-avant", type=float, default=0.25)
    ap.add_argument("--silence-apres", type=float, default=6.0,
                    help="silence final : le modele full-duplex y place sa reponse")
    args = ap.parse_args()

    cases = e2e_bench.controller_cases(25)
    os.makedirs(STAGING, exist_ok=True)

    conditions = {}

    # --- 1. SAPI + canal radio : on REUTILISE le code du banc (graine 7) ----
    rng = np.random.default_rng(e2e_bench.SEED_NOISE)
    sapi_radio = []
    for i in range(len(cases)):
        clean = os.path.join(E2E_AUDIO, f"c{i:02d}_clean.wav")
        sapi_radio.append(wav_bytes_to_samples(
            e2e_bench.degrade_to_wav_bytes(clean, rng)))
    conditions["sapi_radio"] = sapi_radio

    # --- 2. SAPI propre -----------------------------------------------------
    conditions["sapi_propre"] = [
        to_16k_mono(os.path.join(E2E_AUDIO, f"c{i:02d}_clean.wav"))
        for i in range(len(cases))]

    # --- 3/4. locuteur humain : micro brut, puis meme canal radio -----------
    if os.path.isdir(HUMAN_AUDIO):
        conditions["humain_micro"] = [
            to_16k_mono(os.path.join(HUMAN_AUDIO, f"c{i:02d}_clean.wav"))
            for i in range(len(cases))]
        rng2 = np.random.default_rng(e2e_bench.SEED_NOISE)
        conditions["humain_radio"] = [
            wav_bytes_to_samples(e2e_bench.degrade_to_wav_bytes(
                os.path.join(HUMAN_AUDIO, f"c{i:02d}_clean.wav"), rng2))
            for i in range(len(cases))]
    else:
        print(f"[!] corpus humain absent ({HUMAN_AUDIO}) - conditions ignorees")

    manifest = []
    for cond, blobs in conditions.items():
        outdir = os.path.join(STAGING, "wav", cond)
        os.makedirs(outdir, exist_ok=True)
        for i, (case, blob) in enumerate(zip(cases, blobs)):
            path = os.path.join(outdir, f"c{i:02d}.wav")
            sf.write(path, pad(blob, args.silence_avant, args.silence_apres),
                     16000, subtype="PCM_16")
            manifest.append({
                "id": f"{cond}_c{i:02d}",
                "condition": cond,
                "cas": i,
                "wav": f"{CLUSTER_ROOT}/wav/{cond}/c{i:02d}.wav",
                "wav_local": path,
                "phrase": case["phrase"],
                "categorie": case["categorie"],
                "attendu": sorted(bench_corpus.expected_for_llm(case)),
                "silence_avant_s": args.silence_avant,
                "silence_apres_s": args.silence_apres,
            })

    mpath = os.path.join(STAGING, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)

    # --- archive prete a etre poussee sur le disque RAM du noeud ------------
    tarpath = os.path.join(STAGING, "stimuli.tar.gz")
    with tarfile.open(tarpath, "w:gz") as tar:
        tar.add(mpath, arcname="manifest.json")
        tar.add(os.path.join(STAGING, "wav"), arcname="wav")

    total = sum(sf.info(m["wav_local"]).duration for m in manifest)
    print(f"[OK] {len(manifest)} stimuli / {len(conditions)} conditions "
          f"({', '.join(conditions)})")
    print(f"     duree totale {total:.0f} s ; archive {os.path.getsize(tarpath) / 1e6:.1f} Mo")
    print(f"     -> {tarpath}")


if __name__ == "__main__":
    main()
