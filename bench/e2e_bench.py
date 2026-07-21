"""
Benchmark E2E — boucle vocale complete voix -> STT -> LLM -> validation -> TTS
==============================================================================
Reproduit la boucle de production de l'application (push-to-talk) :

  1. Un enonce CONTROLEUR est synthetise (voix Windows SAPI, jamais utilisee
     ailleurs dans le banc), puis degrade canal radio : passe-bande VHF
     300-3400 Hz + bruit additif SNR 12 dB (chaine atc_audio, graine fixee).
     => equivalent du WAV envoye par le micro du navigateur.
  2. AIClient.asr        (POST /v1/audio/transcriptions, facade locale)
  3. interpretation via la chaine de production (prompt + KB + validation
     deterministe des bornes / graphe secteur)
  4. collationnement readback.py -> AIClient.tts (voix stable par indicatif,
     degradation VHF cote client ATC_TTS_VHF=1) — chemin de production exact.

Verite terrain : TrafScript attendu du corpus (bench_corpus, cas EN in-grammar).
Conditions : VOIX (pipeline complet) vs TEXTE (sans STT, condition temoin).
Attribution des echecs : STT (transcription deviee) vs LLM (transcription
parfaite mais ordres faux). Latences par etage + totales (bootstrap).

Execution :
  bench\\bench-env\\Scripts\\python.exe bench\\e2e_bench.py --llm-gguf bench\\models\\X.gguf
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np
import requests

import bench_corpus
from bench_stats import latency_summary, wilson_ci

RESULTS_DIR = os.path.join(HERE, "results")
AUDIO_DIR = os.path.join(RESULTS_DIR, "e2e_audio")
ADAPTER = os.path.join(ROOT, "model", "whisper-lora-adapter")
SEED_NOISE = 7
SNR_DB = 12.0


def controller_cases(max_n=25):
    """Cas EN in-grammar positifs du corpus (prononcables par une voix SAPI en-*)."""
    cases = [c for c in bench_corpus.all_cases()
             if c["in_grammar"] and not c["negatif"]
             and c["categorie"] not in ("francais",)]
    return cases[:max_n]


def synth_controller_audio(cases, out_dir):
    """Synthese SAPI des enonces controleur -> [{case, wav_path}]."""
    os.makedirs(out_dir, exist_ok=True)
    ps = ("Add-Type -AssemblyName System.Speech; "
          "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices()"
          " | ForEach-Object { $_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture.Name }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, timeout=60)
    voice = next((line.split("|")[0] for line in out.stdout.splitlines()
                  if "|en-" in line.replace("|EN-", "|en-").lower()), None)
    if voice is None:
        raise RuntimeError("aucune voix SAPI en-* installee")
    manifest = [{"id": f"c{i:02d}", "text": c["phrase"]} for i, c in enumerate(cases)]
    mpath = os.path.join(out_dir, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('{voice}')
$items = Get-Content -Raw '{mpath}' | ConvertFrom-Json
foreach ($it in $items) {{
  $wav = Join-Path '{out_dir}' ($it.id + '_clean.wav')
  $synth.SetOutputToWaveFile($wav)
  $synth.Speak($it.text)
  $synth.SetOutputToNull()
}}
$synth.Dispose()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", script],
                   capture_output=True, text=True, timeout=600, check=True)
    return voice


def degrade_to_wav_bytes(clean_path, rng):
    """WAV SAPI -> 16 kHz mono + canal radio (bruit SNR 12 dB + passe-bande VHF)
    -> bytes WAV 16 kHz (equivalent micro navigateur apres canal radio)."""
    import soundfile as sf
    from math import gcd
    from scipy.signal import resample_poly
    from atc_audio import augment, preprocess_waveform
    data, sr = sf.read(clean_path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        g = gcd(int(sr), 16000)
        data = resample_poly(data, 16000 // g, int(sr) // g).astype(np.float32)
    noisy = augment(data, rng, snr_db=SNR_DB).astype(np.float32)
    vhf = preprocess_waveform(noisy, training=False)
    buf = io.BytesIO()
    sf.write(buf, vhf, 16000, format="WAV", subtype="PCM_16")
    return buf.getvalue()


class LocalFullServer:
    def __init__(self, llm_gguf, stt, port):
        self.llm_gguf, self.stt, self.port = llm_gguf, stt, port
        self.proc = None

    def __enter__(self):
        cmd = [sys.executable, os.path.join(HERE, "local_server.py"),
               "--role", "all", "--llm-gguf", self.llm_gguf,
               "--stt", self.stt, "--port", str(self.port), "--warm"]
        if "mistral" in os.path.basename(self.llm_gguf).lower():
            cmd.append("--merge-system")     # template v0.3 sans role system
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        deadline = time.time() + 900
        url = f"http://127.0.0.1:{self.port}/v1/models"
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"serveur mort (code {self.proc.returncode})")
            try:
                if requests.get(url, timeout=2).ok:
                    return self
            except requests.RequestException:
                pass
            time.sleep(1.0)
        raise TimeoutError("serveur E2E indisponible apres 900 s")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm-gguf", required=True)
    ap.add_argument("--stt", default="")
    ap.add_argument("--port", type=int, default=8905)
    ap.add_argument("--max-n", type=int, default=25)
    ap.add_argument("--out", default=os.path.join(RESULTS_DIR, "e2e_bench.json"))
    ap.add_argument("--save-audio", action="store_true")
    args = ap.parse_args()
    os.makedirs(RESULTS_DIR, exist_ok=True)

    if not args.stt:
        try:
            import torch
            args.stt = (f"hf-lora:{ADAPTER}" if torch.cuda.is_available() else "fw:small")
        except ImportError:
            args.stt = "fw:small"

    cases = controller_cases(args.max_n)
    print(f"[e2e] {len(cases)} enonces controleur ; synthese SAPI...")
    voice = synth_controller_audio(cases, AUDIO_DIR)
    rng = np.random.default_rng(SEED_NOISE)
    wavs = []
    for i in range(len(cases)):
        clean = os.path.join(AUDIO_DIR, f"c{i:02d}_clean.wav")
        b = degrade_to_wav_bytes(clean, rng)
        if args.save_audio:
            with open(os.path.join(AUDIO_DIR, f"c{i:02d}_radio.wav"), "wb") as f:
                f.write(b)
        wavs.append(b)

    llm_name = os.path.splitext(os.path.basename(args.llm_gguf))[0].lower()
    print(f"[e2e] serveur local : STT={args.stt}  LLM={llm_name}  TTS=kokoro")
    with LocalFullServer(args.llm_gguf, args.stt, args.port):
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
        import readback
        import voices as voices_mod
        from ai_client import AIClient, ProviderError
        from bench_textnorm import norm_radio
        AI = AIClient()
        sante = AI.health()
        print(f"[e2e] sante fournisseurs : {sante}")

        rows = []
        import jiwer
        for i, (case, wav) in enumerate(zip(cases, wavs)):
            expected = sorted(bench_corpus.expected_for_llm(case))
            row = {"phrase": case["phrase"], "attendu": expected}
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
                    audio = AI.tts(rb, v)
                    t_tts = time.perf_counter() - t3
                    if args.save_audio:
                        with open(os.path.join(AUDIO_DIR, f"c{i:02d}_readback.wav"),
                                  "wb") as f:
                            f.write(audio)
                got = sorted(out["trafscript"])
                # WER semantique (nombres epeles -> chiffres, symetrique) :
                # sert au diagnostic d'attribution, pas au protocole STT
                r_n, h_n = norm_radio(case["phrase"]), norm_radio(transcript)
                stt_wer = jiwer.wer([r_n], [h_n]) if r_n else float("nan")
                correct = got == expected
                stage = ("ok" if correct else
                         ("stt" if stt_wer > 0.15 else "llm"))
                row.update({"transcript": transcript, "obtenu": got,
                            "correct": bool(correct), "stt_wer": round(stt_wer, 3),
                            "etage_echec": None if correct else stage,
                            "readback": rb,
                            "latence_stt_s": t1 - t0, "latence_llm_s": t2 - t1,
                            "latence_tts_s": t_tts,
                            "latence_totale_s": (t2 - t0) + t_tts})
            except ProviderError as e:
                row.update({"correct": False, "erreur": str(e), "etage_echec": "provider"})
            rows.append(row)
            print(f"  [{i + 1:2d}/{len(cases)}] {'OK ' if row.get('correct') else 'KO '} "
                  f"stt_wer={row.get('stt_wer')}  {case['phrase'][:55]!r}", flush=True)

        # condition temoin TEXTE (sans STT) sur les memes cas
        temoin = []
        for case in cases:
            expected = sorted(bench_corpus.expected_for_llm(case))
            try:
                out = AI.interpret(case["phrase"])
                temoin.append(sorted(out["trafscript"]) == expected)
            except ProviderError:
                temoin.append(False)

    k = sum(r.get("correct", False) for r in rows)
    kt = sum(temoin)
    ok_rows = [r for r in rows if "latence_totale_s" in r]
    results = {
        "config": {"stt": args.stt, "llm": llm_name, "tts": "kokoro-82m",
                   "voix_controleur_sapi": voice, "snr_db": SNR_DB,
                   "seed_bruit": SEED_NOISE, "n": len(cases)},
        "voix": {"reussite": k / len(rows), "ic95": list(wilson_ci(k, len(rows))),
                 "k": k, "n": len(rows)},
        "texte_temoin": {"reussite": kt / len(temoin),
                         "ic95": list(wilson_ci(kt, len(temoin))), "k": kt,
                         "n": len(temoin)},
        "attribution_echecs": {
            "stt": sum(1 for r in rows if r.get("etage_echec") == "stt"),
            "llm": sum(1 for r in rows if r.get("etage_echec") == "llm"),
            "provider": sum(1 for r in rows if r.get("etage_echec") == "provider")},
        "stt_wer_moyen": float(np.nanmean([r["stt_wer"] for r in ok_rows]))
        if ok_rows else None,
        "latences": {
            "stt": latency_summary([r["latence_stt_s"] for r in ok_rows]),
            "llm": latency_summary([r["latence_llm_s"] for r in ok_rows]),
            "tts": latency_summary([r["latence_tts_s"] for r in ok_rows if r["latence_tts_s"]]),
            "totale": latency_summary([r["latence_totale_s"] for r in ok_rows])},
        "rows": rows,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    print(f"[OK] e2e_bench -> {args.out}")
    print(f"  voix  : {k}/{len(rows)} = {k / len(rows):.1%}")
    print(f"  texte : {kt}/{len(temoin)} = {kt / len(temoin):.1%}")


if __name__ == "__main__":
    main()
