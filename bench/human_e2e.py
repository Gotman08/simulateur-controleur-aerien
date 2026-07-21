"""
Boucle vocale complete avec locuteur HUMAIN reel
================================================
Rejoue la chaine EXACTE de e2e_bench.py (facade locale : Whisper-LoRA +
Mistral GGUF + Kokoro ; prompt + KB + validation deterministe ; memes 25
cas, meme graine de bruit) sur des enregistrements humains produits par
bench/human_record.py, dans deux conditions :

  - "radio" : canal simule identique au banc (bruit SNR 12 dB, graine 7,
              puis passe-bande VHF) -> directement comparable au chiffre
              SAPI publie (76 %).
  - "micro" : enregistrement brut 16 kHz, tel que l'application entend le
              push-to-talk (condition d'usage reel).

Sortie : bench/results/human_e2e.json (reussites + IC de Wilson par
condition et par locuteur, attribution des echecs, latences).

Execution :
  bench\\bench-env\\Scripts\\python.exe bench\\human_e2e.py --speaker nicolas
  (plusieurs locuteurs : --speaker nicolas --speaker alice ; defaut : tous
   les sous-dossiers de bench/results/human_audio/)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

import bench_corpus
import e2e_bench
from bench_stats import latency_summary, wilson_ci

RESULTS_DIR = os.path.join(HERE, "results")
HUMAN_DIR = os.path.join(RESULTS_DIR, "human_audio")
DEFAULT_GGUF = os.path.join(HERE, "models", "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf")


def wav_bytes_brut(path):
    """WAV 16 kHz mono PCM_16 (condition micro, sans canal simule)."""
    import soundfile as sf
    data, sr = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(int(sr), 16000)
        data = resample_poly(data, 16000 // g, int(sr) // g).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, data, 16000, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def run_condition(AI, cases, wavs, label):
    """Meme boucle de mesure que e2e_bench (STT -> interpret -> readback/TTS)."""
    import jiwer
    import readback
    import voices as voices_mod
    from ai_client import ProviderError
    from bench_textnorm import norm_radio

    rows = []
    for i, (case, wav) in enumerate(zip(cases, wavs)):
        expected = sorted(bench_corpus.expected_for_llm(case))
        row = {"phrase": case["phrase"], "attendu": expected}
        if wav is None:
            row.update({"correct": False, "etage_echec": "absent"})
            rows.append(row)
            continue
        try:
            t0 = time.perf_counter()
            transcript = AI.asr(wav)
            t1 = time.perf_counter()
            out = AI.interpret(transcript)
            t2 = time.perf_counter()
            rb = readback.readback_text(out["orders"])
            t_tts = 0.0
            if rb:
                v = voices_mod.voice_for_callsign(out["orders"][0].get("callsign"),
                                                  AI.tts_pool)
                t3 = time.perf_counter()
                AI.tts(rb, v)
                t_tts = time.perf_counter() - t3
            got = sorted(out["trafscript"])
            r_n, h_n = norm_radio(case["phrase"]), norm_radio(transcript)
            stt_wer = jiwer.wer([r_n], [h_n]) if r_n else float("nan")
            correct = got == expected
            stage = "ok" if correct else ("stt" if stt_wer > 0.15 else "llm")
            row.update({"transcript": transcript, "obtenu": got,
                        "correct": bool(correct), "stt_wer": round(stt_wer, 3),
                        "etage_echec": None if correct else stage,
                        "latence_stt_s": t1 - t0, "latence_llm_s": t2 - t1,
                        "latence_tts_s": t_tts,
                        "latence_totale_s": (t2 - t0) + t_tts})
        except ProviderError as e:
            row.update({"correct": False, "erreur": str(e),
                        "etage_echec": "provider"})
        rows.append(row)
        print(f"  [{label} {i + 1:2d}/{len(cases)}] "
              f"{'OK ' if row.get('correct') else 'KO '}"
              f"stt_wer={row.get('stt_wer')}  {case['phrase'][:52]!r}", flush=True)
    return rows


def summarize(rows):
    k = sum(r.get("correct", False) for r in rows)
    n = len(rows)
    ok_rows = [r for r in rows if "latence_totale_s" in r]
    return {
        "reussite": k / n if n else None, "k": k, "n": n,
        "ic95": list(wilson_ci(k, n)) if n else None,
        "attribution_echecs": {
            e: sum(1 for r in rows if r.get("etage_echec") == e)
            for e in ("stt", "llm", "provider", "absent")},
        "stt_wer_moyen": float(np.nanmean([r["stt_wer"] for r in ok_rows]))
        if ok_rows else None,
        "latence_totale": latency_summary(
            [r["latence_totale_s"] for r in ok_rows]) if ok_rows else None,
        "rows": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", action="append", default=None,
                    help="locuteur(s) a evaluer (defaut : tous)")
    ap.add_argument("--llm-gguf", default=DEFAULT_GGUF)
    ap.add_argument("--stt", default=f"hf-lora:{os.path.join(ROOT, 'model', 'whisper-lora-adapter')}")
    ap.add_argument("--port", type=int, default=8906)
    ap.add_argument("--max-n", type=int, default=25)
    ap.add_argument("--out", default=os.path.join(RESULTS_DIR, "human_e2e.json"))
    args = ap.parse_args()

    if args.speaker:
        speakers = args.speaker
    elif os.path.isdir(HUMAN_DIR):
        speakers = sorted(d for d in os.listdir(HUMAN_DIR)
                          if os.path.isdir(os.path.join(HUMAN_DIR, d)))
    else:
        speakers = []
    if not speakers:
        sys.exit("Aucun enregistrement : lance d'abord bench/human_record.py")

    cases = e2e_bench.controller_cases(args.max_n)
    llm_name = os.path.splitext(os.path.basename(args.llm_gguf))[0].lower()
    print(f"[human-e2e] locuteurs={speakers}  STT={args.stt}  LLM={llm_name}")

    with e2e_bench.LocalFullServer(args.llm_gguf, args.stt, args.port):
        base = f"http://127.0.0.1:{args.port}"
        for name in ("STT", "LLM", "TTS"):
            os.environ[f"ATC_{name}_URL"] = base
            os.environ[f"ATC_{name}_KEY"] = ""
        os.environ["ATC_STT_MODEL"] = args.stt
        os.environ["ATC_LLM_MODEL"] = llm_name
        os.environ["ATC_TTS_MODEL"] = "kokoro-82m"
        os.environ["ATC_TTS_VOICES"] = "af_bella,am_adam,bm_george"
        os.environ["ATC_TTS_VHF"] = "1"
        os.environ["ATC_TTS_FORMAT"] = "wav"
        from ai_client import AIClient
        AI = AIClient()
        print(f"[human-e2e] sante fournisseurs : {AI.health()}")

        par_locuteur = {}
        for sp in speakers:
            d = os.path.join(HUMAN_DIR, sp)
            paths = [os.path.join(d, f"c{i:02d}_clean.wav")
                     for i in range(len(cases))]
            manquants = [p for p in paths if not os.path.exists(p)]
            if manquants:
                print(f"[!] {sp} : {len(manquants)} phrase(s) non enregistree(s),"
                      " comptees en echec 'absent'")
            # condition radio : meme canal et meme graine que e2e_bench
            rng = np.random.default_rng(e2e_bench.SEED_NOISE)
            wavs_radio = [e2e_bench.degrade_to_wav_bytes(p, rng)
                          if os.path.exists(p) else None for p in paths]
            wavs_brut = [wav_bytes_brut(p) if os.path.exists(p) else None
                         for p in paths]
            print(f"\n=== {sp} / condition RADIO (SNR 12 dB + VHF, graine "
                  f"{e2e_bench.SEED_NOISE}) ===")
            radio = run_condition(AI, cases, wavs_radio, "radio")
            print(f"\n=== {sp} / condition MICRO (brut, comme l'application) ===")
            micro = run_condition(AI, cases, wavs_brut, "micro")
            par_locuteur[sp] = {"radio": summarize(radio),
                                "micro": summarize(micro)}

    # agregat tous locuteurs
    agg = {}
    for cond in ("radio", "micro"):
        rows = [r for sp in speakers for r in par_locuteur[sp][cond]["rows"]]
        agg[cond] = summarize(rows)
        agg[cond].pop("rows")

    results = {
        "config": {"stt": args.stt, "llm": llm_name, "tts": "kokoro-82m",
                   "snr_db": e2e_bench.SNR_DB, "seed_bruit": e2e_bench.SEED_NOISE,
                   "n_cas": len(cases), "locuteurs": speakers,
                   "reference_sapi": "bench/results/e2e_bench.json (76 %)"},
        "par_locuteur": par_locuteur,
        "agrege": agg,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)

    print(f"\n[OK] human_e2e -> {args.out}")
    for sp in speakers:
        for cond in ("radio", "micro"):
            s = par_locuteur[sp][cond]
            lo, hi = s["ic95"]
            print(f"  {sp:12s} {cond:5s} : {s['k']}/{s['n']} = {s['reussite']:.1%}"
                  f"  IC95 [{lo:.1%} ; {hi:.1%}]")
    print("  (reference voix synthetique SAPI, condition radio : 19/25 = 76 %)")


if __name__ == "__main__":
    main()
