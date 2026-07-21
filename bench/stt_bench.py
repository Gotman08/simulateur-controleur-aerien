"""
Benchmark STT - WER multi-modeles sur corpus ATC reels
======================================================
Corpus de test : enregistrements VHF REELS avec transcriptions de reference
  - Jzuluaga/atco2_corpus_1h  (ATCO2, domaine cible du projet)
  - Jzuluaga/uwb_atcc         (split test ; domaine d'entrainement du LoRA)
Echantillonnage seedable (graine 42), duree filtree [0.4, 30] s comme
src/atc_data.py. L'audio est decode via soundfile (decode=False + bytes),
independant du backend de la librairie datasets.

Systemes evalues :
  - hf-small        : openai/whisper-small (transformers) - baseline exacte
  - hf-small-lora   : whisper-small + adaptateur LoRA ATC du depot
                      (model/whisper-lora-adapter), CHAINE D'EVALUATION DU
                      PROJET (atc_asr.build_inference_model/transcribe_arrays)
  - fw-tiny/base/small : faster-whisper (CTranslate2), moteur de deploiement
                      local realiste (greedy, beam_size=1 = parite transformers)

Conditions : bandpass VHF 300-3400 Hz d'inference OFF/ON (protocole du projet
= ON, cf. server.py transcribe bandpass=True). Normalisation texte et WER =
PROTOCOLE HISTORIQUE du projet (atc_asr.get_normalizer + compute_wer), pour
comparabilite directe avec les WER publies (74.3 -> 29.2 sur ATCO2).

Metriques : WER corpus, WER moyen par extrait + IC bootstrap, RTF, latences ;
comparaison appariee LoRA vs vanilla (bootstrap de la difference).

Execution :  bench\\bench-env\\Scripts\\python.exe bench\\stt_bench.py
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

# ctranslate2 (faster-whisper) cherche les DLL CUDA/cuDNN : celles du wheel
# torch Windows font l'affaire si on les ajoute au repertoire de recherche.
try:
    import torch
    _torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
    if os.name == "nt" and os.path.isdir(_torch_lib):
        os.add_dll_directory(_torch_lib)
except ImportError:
    torch = None

import atc_asr
from atc_audio import preprocess_waveform
from bench_stats import bootstrap_ci_mean, latency_summary, paired_bootstrap_diff

RESULTS_DIR = os.path.join(HERE, "results")
ADAPTER = os.path.join(ROOT, "model", "whisper-lora-adapter")
SEED = 42

CORPORA = {
    "atco2": {"id": "Jzuluaga/atco2_corpus_1h", "prefer_split": "test"},
    "uwb_atcc": {"id": "Jzuluaga/uwb_atcc", "prefer_split": "test"},
}


# --- chargement corpus ----------------------------------------------------------
def _decode_audio(item):
    """Decode un element Audio(decode=False) -> (np.float32 16 kHz mono, duree_s)."""
    import soundfile as sf
    from scipy.signal import resample_poly
    from math import gcd
    raw = item["bytes"] if isinstance(item, dict) else None
    if raw is None and isinstance(item, dict) and item.get("path"):
        with open(item["path"], "rb") as f:
            raw = f.read()
    data, sr = sf.read(io.BytesIO(raw), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        g = gcd(int(sr), 16000)
        data = resample_poly(data, 16000 // g, int(sr) // g).astype(np.float32)
    return np.ascontiguousarray(data, dtype=np.float32), len(data) / 16000.0


def load_corpus(corpus_key, max_n, seed=SEED):
    """-> liste de {ref, wav (16 kHz float32), duree_s}. Echantillon seedable."""
    from datasets import Audio, load_dataset
    cfg = CORPORA[corpus_key]
    ds_all = load_dataset(cfg["id"])
    split = cfg["prefer_split"] if cfg["prefer_split"] in ds_all else list(ds_all.keys())[0]
    ds = ds_all[split].cast_column("audio", Audio(decode=False))
    text_col = next(c for c in ("text", "transcription", "sentence") if c in ds.column_names)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(ds))
    out = []
    for i in order:
        ex = ds[int(i)]
        ref = str(ex[text_col] or "").strip()
        if not ref:
            continue
        try:
            wav, dur = _decode_audio(ex["audio"])
        except Exception:
            continue
        if not (0.4 <= dur <= 30.0):
            continue
        out.append({"ref": ref, "wav": wav, "duree_s": dur})
        if len(out) >= max_n:
            break
    return out, split


# --- systemes STT -----------------------------------------------------------------
class HfWhisper:
    def __init__(self, adapter_path=None):
        device = "cuda" if (torch is not None and torch.cuda.is_available()) else "cpu"
        self.proc, self.model = atc_asr.build_inference_model(
            "openai/whisper-small", adapter_path=adapter_path, device=device)

    def transcribe_batch(self, wavs, bandpass):
        return atc_asr.transcribe_arrays(self.model, self.proc, wavs,
                                         bandpass=bandpass, batch_size=8)


class FasterWhisper:
    def __init__(self, size):
        from faster_whisper import WhisperModel
        self.device = "cuda"
        try:
            self.m = WhisperModel(size, device="cuda", compute_type="float16")
            self.m.transcribe(np.zeros(1600, dtype=np.float32), language="en")
        except Exception:
            self.device = "cpu"
            self.m = WhisperModel(size, device="cpu", compute_type="int8")

    def transcribe_one(self, wav, bandpass):
        x = preprocess_waveform(wav, training=False) if bandpass else wav
        segments, _ = self.m.transcribe(x, language="en", beam_size=1,
                                        condition_on_previous_text=False)
        return " ".join(s.text.strip() for s in segments).strip()


# --- evaluation ---------------------------------------------------------------------
def eval_hf(engine, corpus, bandpass, batch=8):
    normalizer = atc_asr.get_normalizer()
    hyps, times = [], []
    for i in range(0, len(corpus), batch):
        chunk = [c["wav"] for c in corpus[i:i + batch]]
        t0 = time.perf_counter()
        hyps.extend(engine.transcribe_batch(chunk, bandpass))
        times.append(time.perf_counter() - t0)
    proc_s = sum(times)
    return _score(corpus, hyps, normalizer, proc_s, per_utt_lat=None)


def eval_fw(engine, corpus, bandpass):
    normalizer = atc_asr.get_normalizer()
    hyps, lats = [], []
    for c in corpus:
        t0 = time.perf_counter()
        hyps.append(engine.transcribe_one(c["wav"], bandpass))
        lats.append(time.perf_counter() - t0)
    return _score(corpus, hyps, normalizer, sum(lats), per_utt_lat=lats)


def _score(corpus, hyps, normalizer, proc_s, per_utt_lat):
    import jiwer
    refs_n = [normalizer(c["ref"]) for c in corpus]
    hyps_n = [normalizer(h) for h in hyps]
    pairs = [(r, h) for r, h in zip(refs_n, hyps_n) if r]
    wer_corpus = atc_asr.compute_wer(refs_n, hyps_n)
    per_utt = [jiwer.wer([r], [h]) for r, h in pairs]
    audio_s = sum(c["duree_s"] for c in corpus)
    lo, hi = bootstrap_ci_mean(per_utt)
    res = {
        "n": len(pairs),
        "wer_corpus": float(wer_corpus),
        "wer_moyen_extrait": float(np.mean(per_utt)),
        "ic95_wer_moyen": [lo, hi],
        "audio_total_s": round(audio_s, 1),
        "traitement_total_s": round(proc_s, 1),
        "rtf": round(proc_s / audio_s, 4),
        "per_utt_wer": [round(w, 4) for w in per_utt],
        "exemples": [{"ref": r, "hyp": h} for r, h in pairs[:5]],
    }
    if per_utt_lat:
        res["latence"] = latency_summary(per_utt_lat)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-n", type=int, default=150, help="extraits par corpus")
    ap.add_argument("--corpora", default="atco2,uwb_atcc")
    ap.add_argument("--systems", default="hf-small,hf-small-lora,fw-tiny,fw-base,fw-small")
    ap.add_argument("--out", default=os.path.join(RESULTS_DIR, "stt_bench.json"))
    args = ap.parse_args()
    os.makedirs(RESULTS_DIR, exist_ok=True)

    results = {"seed": SEED, "protocole": {
        "normalisation": "atc_asr.get_normalizer (BasicTextNormalizer)",
        "wer": "jiwer, protocole historique du projet (comparable aux WER publies)",
        "decodage": "greedy (beam 1) pour tous les systemes",
        "duree_filtre_s": [0.4, 30.0],
        "gpu": (torch.cuda.get_device_name(0)
                if torch is not None and torch.cuda.is_available() else "cpu"),
    }, "corpora": {}}

    corpora = {}
    for key in args.corpora.split(","):
        key = key.strip()
        print(f"[stt_bench] chargement {key}...", flush=True)
        corpus, split = load_corpus(key, args.max_n)
        corpora[key] = corpus
        results["corpora"][key] = {
            "dataset": CORPORA[key]["id"], "split": split, "n": len(corpus),
            "audio_total_s": round(sum(c["duree_s"] for c in corpus), 1)}
        print(f"    {len(corpus)} extraits, "
              f"{results['corpora'][key]['audio_total_s']:.0f} s d'audio")

    systems = [s.strip() for s in args.systems.split(",")]
    results["systems"] = {}
    engines = {}

    def get_engine(name):
        if name not in engines:
            print(f"[stt_bench] chargement modele {name}...", flush=True)
            if name == "hf-small":
                engines[name] = ("hf", HfWhisper(adapter_path=None))
            elif name == "hf-small-lora":
                engines[name] = ("hf", HfWhisper(adapter_path=ADAPTER))
            elif name.startswith("fw-"):
                engines[name] = ("fw", FasterWhisper(name[3:]))
            else:
                raise ValueError(name)
        return engines[name]

    for name in systems:
        kind, engine = get_engine(name)
        results["systems"][name] = {}
        if kind == "fw":
            results["systems"][name]["device"] = engine.device
        for ckey, corpus in corpora.items():
            for bandpass in (False, True):
                cond = "vhf_bandpass" if bandpass else "brut"
                print(f"[stt_bench] {name} / {ckey} / {cond} ...", flush=True)
                t0 = time.perf_counter()
                r = (eval_hf(engine, corpus, bandpass) if kind == "hf"
                     else eval_fw(engine, corpus, bandpass))
                r["duree_eval_s"] = round(time.perf_counter() - t0, 1)
                results["systems"][name].setdefault(ckey, {})[cond] = r
                print(f"    WER corpus = {r['wer_corpus']:.1%}  RTF = {r['rtf']:.3f}")
                with open(args.out, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=1, ensure_ascii=False)
        # decharger les moteurs HF pour liberer la VRAM avant faster-whisper
        if kind == "hf":
            engines.pop(name, None)
            if torch is not None and torch.cuda.is_available():
                del engine
                torch.cuda.empty_cache()

    # comparaison appariee LoRA vs vanilla (meme corpus, meme condition)
    comp = {}
    s = results["systems"]
    if "hf-small" in s and "hf-small-lora" in s:
        for ckey in corpora:
            for cond in ("brut", "vhf_bandpass"):
                a = s["hf-small-lora"][ckey][cond]["per_utt_wer"]
                b = s["hf-small"][ckey][cond]["per_utt_wer"]
                comp[f"lora_vs_vanilla/{ckey}/{cond}"] = paired_bootstrap_diff(a, b)
    results["comparaisons_appariees"] = comp

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    print(f"[OK] stt_bench -> {args.out}")


if __name__ == "__main__":
    main()
