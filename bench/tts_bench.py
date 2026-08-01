"""
Benchmark TTS - RTF, latence et intelligibilite objective
=========================================================
Moteurs evalues :
  - kokoro-82M (ONNX, local)     voix af_bella / am_adam / bf_emma / bm_george
  - Windows SAPI (System.Speech) voix installees en-* (baseline systeme)

Jeu de phrases : COLLATIONNEMENTS PILOTES produits par le generateur de
production src/readback.py (phraseologie OACI exacte de l'application) a
partir de 30 jeux d'ordres couvrant ALT (climb/descend), HDG, SPD, ADDWPT
et multi-ordres, indicatifs varies.

Metriques :
  - RTF = duree de synthese / duree audio produite (IC bootstrap) ;
  - latence de synthese par phrase (bootstrap) ;
  - intelligibilite objective ALLER-RETOUR : TTS -> juge STT fixe
    (faster-whisper small, greedy) -> WER vs texte source, en condition
    PROPRE et apres degradation VHF 300-3400 Hz du projet (atc_audio).
    Metrique RELATIVE (biais du juge partage par tous les moteurs).

Execution :  bench\\bench-env\\Scripts\\python.exe bench\\tts_bench.py
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

try:
    import torch
    _torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
    if os.name == "nt" and os.path.isdir(_torch_lib):
        os.add_dll_directory(_torch_lib)
except ImportError:
    torch = None

import readback
from atc_audio import preprocess_waveform
from bench_stats import bootstrap_ci_mean, latency_summary
from bench_textnorm import norm_radio

RESULTS_DIR = os.path.join(HERE, "results")
AUDIO_DIR = os.path.join(RESULTS_DIR, "tts_audio")

# 30 jeux d'ordres realistes -> phrases de collationnement via readback.py
ORDER_SETS = [
    ([{"callsign": "AFR1234", "action": "ALT", "value": 10000}], {"AFR1234": 13000}),
    ([{"callsign": "AFR1234", "action": "ALT", "value": 32000}], {"AFR1234": 24000}),
    ([{"callsign": "BAW57", "action": "HDG", "value": 270}], {}),
    ([{"callsign": "BAW57", "action": "ALT", "value": 8000}], {"BAW57": 15000}),
    ([{"callsign": "RYR9", "action": "ALT", "value": 24000}], {"RYR9": 9000}),
    ([{"callsign": "RYR9", "action": "ADDWPT", "wpt": "DELTA"}], {}),
    ([{"callsign": "EZY21", "action": "SPD", "value": 250}], {}),
    ([{"callsign": "EZY21", "action": "HDG", "value": 100}], {}),
    ([{"callsign": "DLH88", "action": "ALT", "value": 35000}], {"DLH88": 28000}),
    ([{"callsign": "DLH88", "action": "ADDWPT", "wpt": "EXIT_E"}], {}),
    ([{"callsign": "KLM123", "action": "HDG", "value": 220}], {}),
    ([{"callsign": "KLM123", "action": "SPD", "value": 280}], {}),
    ([{"callsign": "CSA1DZ", "action": "ALT", "value": 24000}], {"CSA1DZ": 30000}),
    ([{"callsign": "AAL63", "action": "HDG", "value": 120}], {}),
    ([{"callsign": "UAL451", "action": "ALT", "value": 33000}], {"UAL451": 29000}),
    ([{"callsign": "N123AB", "action": "ALT", "value": 9000}], {"N123AB": 12000}),
    ([{"callsign": "FGABC", "action": "ALT", "value": 15000}], {"FGABC": 10000}),
    ([{"callsign": "AFR1234", "action": "HDG", "value": 45}], {}),
    ([{"callsign": "BAW57", "action": "SPD", "value": 230}], {}),
    ([{"callsign": "EZY21", "action": "ADDWPT", "wpt": "BALMO"}], {}),
    ([{"callsign": "AFR1234", "action": "ALT", "value": 20000},
      {"callsign": "AFR1234", "action": "ADDWPT", "wpt": "CROSS"}], {"AFR1234": 26000}),
    ([{"callsign": "BAW57", "action": "HDG", "value": 90},
      {"callsign": "BAW57", "action": "ALT", "value": 11000}], {"BAW57": 20000}),
    ([{"callsign": "DLH88", "action": "ALT", "value": 31000},
      {"callsign": "DLH88", "action": "SPD", "value": 290}], {"DLH88": 26000}),
    ([{"callsign": "EZY21", "action": "HDG", "value": 180},
      {"callsign": "EZY21", "action": "SPD", "value": 240}], {}),
    ([{"callsign": "RYR9", "action": "HDG", "value": 225}], {}),
    ([{"callsign": "KLM123", "action": "ALT", "value": 18000}], {"KLM123": 24000}),
    ([{"callsign": "AFR1234", "action": "SPD", "value": 300}], {}),
    ([{"callsign": "CSA1DZ", "action": "HDG", "value": 210}], {}),
    ([{"callsign": "UAL451", "action": "ADDWPT", "wpt": "NORTH"}], {}),
    ([{"callsign": "AAL63", "action": "ALT", "value": 13000},
      {"callsign": "AAL63", "action": "SPD", "value": 220}], {"AAL63": 19000}),
]

KOKORO_VOICES = ["af_bella", "am_adam", "bf_emma", "bm_george"]


def phrases():
    out = []
    for i, (orders, cur_alt) in enumerate(ORDER_SETS):
        txt = readback.readback_text(orders, cur_alt)
        assert txt, f"readback vide pour le jeu {i}"
        out.append({"id": f"p{i:02d}", "text": txt})
    return out


# --- moteurs ---------------------------------------------------------------------
class KokoroEngine:
    def __init__(self):
        from kokoro_onnx import Kokoro
        self.k = Kokoro(os.path.join(HERE, "models", "kokoro-v1.0.onnx"),
                        os.path.join(HERE, "models", "voices-v1.0.bin"))

    def synth(self, text, voice):
        t0 = time.perf_counter()
        samples, sr = self.k.create(text, voice=voice, speed=1.0, lang="en-us")
        dt = time.perf_counter() - t0
        return np.asarray(samples, dtype=np.float32), int(sr), dt


class HttpTts:
    """Fournisseur TTS OpenAI-compatible en service (ex. XTTS sur ROMEO via
    tunnel). Latences client = synthese + reseau (realite de deploiement)."""

    def __init__(self, url, model_id="xtts-atc"):
        import ai_client
        os.environ["ATC_TTS_URL"] = url
        os.environ["ATC_TTS_KEY"] = ""
        os.environ["ATC_TTS_MODEL"] = model_id
        self.client = ai_client.TtsClient(ai_client.ProviderConfig.from_env("tts"))

    def synth(self, text, voice):
        import io as _io
        import soundfile as sf
        t0 = time.perf_counter()
        wav_bytes = self.client.speak(text, voice, response_format="wav")
        dt = time.perf_counter() - t0
        data, sr = sf.read(_io.BytesIO(wav_bytes), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        return np.asarray(data, dtype=np.float32), int(sr), dt


def sapi_voices():
    ps = ("Add-Type -AssemblyName System.Speech; "
          "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices()"
          " | ForEach-Object { $_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture.Name }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, timeout=60)
    voices = []
    for line in out.stdout.splitlines():
        if "|" in line:
            name, culture = line.strip().split("|", 1)
            if culture.lower().startswith("en"):
                voices.append(name)
    return voices


def sapi_synth_batch(phrase_list, voice, out_dir):
    """Synthese SAPI en UN process PowerShell (timings internes, sans cout de
    demarrage) -> [{id, wav, ms}]."""
    os.makedirs(out_dir, exist_ok=True)
    manifest = os.path.join(out_dir, "manifest.json")
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump(phrase_list, f)
    script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('{voice}')
$items = Get-Content -Raw '{manifest}' | ConvertFrom-Json
$res = @()
foreach ($it in $items) {{
  $wav = Join-Path '{out_dir}' ($it.id + '.wav')
  $synth.SetOutputToWaveFile($wav)
  $t = Measure-Command {{ $synth.Speak($it.text) }}
  $synth.SetOutputToNull()
  $res += [pscustomobject]@{{ id = $it.id; wav = $wav; ms = $t.TotalMilliseconds }}
}}
$synth.Dispose()
$res | ConvertTo-Json | Out-File -Encoding utf8 (Join-Path '{out_dir}' 'timings.json')
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", script],
                   capture_output=True, text=True, timeout=600, check=True)
    # PowerShell 5.1 ecrit l'UTF-8 AVEC BOM -> utf-8-sig obligatoire
    with open(os.path.join(out_dir, "timings.json"), encoding="utf-8-sig") as f:
        return json.load(f)


# --- juge STT fixe -----------------------------------------------------------------
class Judge:
    def __init__(self):
        from faster_whisper import WhisperModel
        try:
            self.m = WhisperModel("small", device="cuda", compute_type="float16")
            self.m.transcribe(np.zeros(1600, dtype=np.float32), language="en")
            self.device = "cuda"
        except Exception:
            self.m = WhisperModel("small", device="cpu", compute_type="int8")
            self.device = "cpu"

    def wer(self, wav_16k, ref_text):
        import jiwer
        segments, _ = self.m.transcribe(wav_16k, language="en", beam_size=1,
                                        condition_on_previous_text=False)
        hyp = " ".join(s.text.strip() for s in segments).strip()
        # normalisation SEMANTIQUE symetrique (nombres epeles -> chiffres) :
        # sans elle, « one zero zero » vs « 100 » gonfle le WER d'un facteur ~10
        r, h = norm_radio(ref_text), norm_radio(hyp)
        return (jiwer.wer([r], [h]) if r else float("nan")), hyp


def to_16k(samples, sr):
    from math import gcd
    from scipy.signal import resample_poly
    if sr == 16000:
        return samples
    g = gcd(int(sr), 16000)
    return resample_poly(samples, 16000 // g, int(sr) // g).astype(np.float32)


def eval_engine_outputs(items, judge):
    """items : [{text, samples(16k), sr_source, synth_s}] -> metriques."""
    durations = [len(it["samples_16k"]) / 16000.0 for it in items]
    rtfs = [it["synth_s"] / d for it, d in zip(items, durations) if d > 0]
    wers_clean, wers_vhf = [], []
    for it in items:
        w, _ = judge.wer(it["samples_16k"], it["text"])
        wers_clean.append(w)
        degraded = preprocess_waveform(it["samples_16k"], training=False)
        w2, _ = judge.wer(degraded, it["text"])
        wers_vhf.append(w2)
    lo_r, hi_r = bootstrap_ci_mean(rtfs)
    lo_c, hi_c = bootstrap_ci_mean(wers_clean)
    lo_v, hi_v = bootstrap_ci_mean(wers_vhf)
    return {
        "n": len(items),
        "rtf_moyen": float(np.mean(rtfs)), "ic95_rtf": [lo_r, hi_r],
        "latence_synthese": latency_summary([it["synth_s"] for it in items]),
        "duree_audio_moyenne_s": float(np.mean(durations)),
        "wer_aller_retour_propre": float(np.nanmean(wers_clean)),
        "ic95_wer_propre": [lo_c, hi_c],
        "wer_aller_retour_vhf": float(np.nanmean(wers_vhf)),
        "ic95_wer_vhf": [lo_v, hi_v],
        "per_utt": [{"text": it["text"], "rtf": round(it["synth_s"] / max(1e-9, len(it["samples_16k"]) / 16000.0), 3),
                     "wer_propre": round(wc, 3), "wer_vhf": round(wv, 3)}
                    for it, wc, wv in zip(items, wers_clean, wers_vhf)],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(RESULTS_DIR, "tts_bench.json"))
    ap.add_argument("--xtts-url", default="",
                    help="URL de la facade TTS distante (ex. http://localhost:8766 "
                         "= XTTS ROMEO via tunnel) ; voix pilot_1..3")
    ap.add_argument("--save-audio", action="store_true",
                    help="conserver les WAV de synthese (demo article)")
    args = ap.parse_args()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)

    import soundfile as sf
    ph = phrases()
    print(f"[tts_bench] {len(ph)} collationnements (readback.py), juge STT fixe...")
    judge = Judge()
    results = {"n_phrases": len(ph),
               "juge": f"faster-whisper small ({judge.device}, greedy)",
               "protocole": {
                   "phrases": "collationnements OACI de src/readback.py",
                   "vhf": "atc_audio.preprocess_waveform (Butterworth 6, 300-3400 Hz)",
                   "wer": "bench_textnorm.norm_radio (nombres epeles -> chiffres, "
                          "symetrique ref/hyp) + jiwer - metrique RELATIVE inter-moteurs"},
               "engines": {}}

    # --- kokoro -------------------------------------------------------------
    try:
        kok = KokoroEngine()
        for voice in KOKORO_VOICES:
            print(f"[tts_bench] kokoro / {voice} ...", flush=True)
            items = []
            for p in ph:
                samples, sr, dt = kok.synth(p["text"], voice)
                s16 = to_16k(samples, sr)
                items.append({"text": p["text"], "samples_16k": s16, "synth_s": dt})
                if args.save_audio:
                    sf.write(os.path.join(AUDIO_DIR, f"kokoro_{voice}_{p['id']}.wav"),
                             s16, 16000)
            r = eval_engine_outputs(items, judge)
            r["sr_natif"] = sr
            results["engines"][f"kokoro/{voice}"] = r
            print(f"    RTF={r['rtf_moyen']:.3f}  WER propre={r['wer_aller_retour_propre']:.1%}"
                  f"  WER VHF={r['wer_aller_retour_vhf']:.1%}")
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=1, ensure_ascii=False)
    except Exception as e:
        results["engines"]["kokoro"] = {"erreur": str(e)}
        print(f"[tts_bench] kokoro indisponible : {e}")

    # --- XTTS distant (facade ROMEO via tunnel), voix clonees pilot_* -----------
    if args.xtts_url:
        try:
            xt = HttpTts(args.xtts_url, model_id="xtts-atc")
            for voice in ("pilot_1", "pilot_2", "pilot_3"):
                print(f"[tts_bench] xtts-romeo / {voice} ...", flush=True)
                items = []
                for p in ph:
                    samples, sr, dt = xt.synth(p["text"], voice)
                    s16 = to_16k(samples, sr)
                    items.append({"text": p["text"], "samples_16k": s16, "synth_s": dt})
                    if args.save_audio:
                        sf.write(os.path.join(AUDIO_DIR, f"xtts_{voice}_{p['id']}.wav"),
                                 s16, 16000)
                r = eval_engine_outputs(items, judge)
                r["sr_natif"] = sr
                r["note"] = "synthese GH200 via tunnel SSH : latence reseau incluse"
                results["engines"][f"xtts-romeo/{voice}"] = r
                print(f"    RTF={r['rtf_moyen']:.3f}  WER propre={r['wer_aller_retour_propre']:.1%}"
                      f"  WER VHF={r['wer_aller_retour_vhf']:.1%}")
                with open(args.out, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=1, ensure_ascii=False)
        except Exception as e:
            results["engines"]["xtts-romeo"] = {"erreur": str(e)}
            print(f"[tts_bench] xtts-romeo indisponible : {e}")

    # --- SAPI ------------------------------------------------------------------
    try:
        voices = sapi_voices()
        print(f"[tts_bench] voix SAPI en-* : {voices}")
        for voice in voices[:3]:
            print(f"[tts_bench] sapi / {voice} ...", flush=True)
            with tempfile.TemporaryDirectory() as tmp:
                timings = sapi_synth_batch(ph, voice, tmp)
                if isinstance(timings, dict):
                    timings = [timings]
                items = []
                for t, p in zip(sorted(timings, key=lambda x: x["id"]), ph):
                    data, sr = sf.read(t["wav"], dtype="float32")
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    s16 = to_16k(data, sr)
                    items.append({"text": p["text"], "samples_16k": s16,
                                  "synth_s": t["ms"] / 1000.0})
                    if args.save_audio:
                        sf.write(os.path.join(
                            AUDIO_DIR, f"sapi_{voice.replace(' ', '_')}_{p['id']}.wav"),
                            s16, 16000)
            r = eval_engine_outputs(items, judge)
            r["sr_natif"] = sr
            results["engines"][f"sapi/{voice}"] = r
            print(f"    RTF={r['rtf_moyen']:.3f}  WER propre={r['wer_aller_retour_propre']:.1%}"
                  f"  WER VHF={r['wer_aller_retour_vhf']:.1%}")
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=1, ensure_ascii=False)
    except Exception as e:
        results["engines"]["sapi"] = {"erreur": str(e)}
        print(f"[tts_bench] SAPI indisponible : {e}")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    print(f"[OK] tts_bench -> {args.out}")


if __name__ == "__main__":
    main()
