"""
Preuve - Semaine 4 (T7) : inference & integration dans le harnais S3
====================================================================
Implemente la VRAIE fonction transcribe() laissee en squelette
(NotImplementedError) dans Preuves_Semaines_1-3/05_whisper_llm_blank_test.py,
en utilisant le modele Whisper fine-tune (adapter LoRA).

- transcribe(audio_path) : entree audio -> texte (point d'entree du pipeline,
  pret pour la post-correction LLM de la S5).
- demo : transcrit quelques extraits du test et rejoue la mesure WER du harnais
  S3 sur le VRAI modele (au lieu des paires d'exemple).

A lancer sur un noeud armgpu (GPU).
  python 10_inference_demo.py                      # demo sur le test
  python 10_inference_demo.py --wav mon_extrait.wav  # sur un fichier audio
"""
import os
import argparse

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("HF_HOME", os.path.join(WORK, "hf_cache"))

import numpy as np
import atc_asr
from atc_audio import FS

_MODEL_CACHE = {}


def _load(adapter_path, model_base="openai/whisper-small"):
    key = (model_base, adapter_path)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = atc_asr.build_inference_model(model_base, adapter_path=adapter_path)
    return _MODEL_CACHE[key]


def transcribe(audio_path, adapter_path=None, model_base="openai/whisper-small"):
    """
    Transcrit un fichier audio avec le Whisper fine-tune ATC.
    Remplit le contrat transcribe() du harnais S3 (05_whisper_llm_blank_test.py).
    """
    import librosa
    wav, _ = librosa.load(audio_path, sr=FS, mono=True)
    proc, model = _load(adapter_path, model_base)
    hyp = atc_asr.transcribe_arrays(model, proc, [wav], bandpass=True, batch_size=1)[0]
    return hyp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(WORK, "data_proc"))
    ap.add_argument("--adapter", default=os.path.join(WORK, "outputs", "lora_small", "adapter"))
    ap.add_argument("--model", default="openai/whisper-small")
    ap.add_argument("--wav", default=None, help="transcrire un fichier audio precis")
    ap.add_argument("--n", type=int, default=6, help="nb d'extraits de demo")
    args = ap.parse_args()

    adapter = args.adapter if os.path.exists(args.adapter) else None
    if adapter is None:
        print(f"[!] adapter introuvable ({args.adapter}) -> demo sur le modele BRUT")

    # --- cas 1 : fichier audio fourni ---------------------------------------
    if args.wav:
        txt = transcribe(args.wav, adapter_path=adapter, model_base=args.model)
        print(f"\n[transcribe] {args.wav}\n  -> {txt!r}")
        print("\n[T7] (fichier) la sortie est prete pour la post-correction LLM (S5).")
        return

    # --- cas 2 : demo + harnais WER S3 sur le vrai modele -------------------
    import jiwer
    import atc_data
    normalizer = atc_asr.get_normalizer()
    ds = atc_data.load_splits()["test"].select(range(args.n))
    arrays = [ex["array"] for ex in ds["audio"]]
    refs = [normalizer(t) for t in ds["text"]]

    proc, model = _load(adapter, args.model)
    hyps = [normalizer(h) for h in atc_asr.transcribe_arrays(model, proc, arrays, bandpass=True)]

    print("\n=== Harnais S3 rejoue sur le VRAI modele (T7) ===")
    for r, h in zip(refs, hyps):
        print(f"  REF: {r[:80]}")
        print(f"  HYP: {h[:80]}   (wer={jiwer.wer([r],[h]):.2f})")
        print("  " + "-" * 40)
    print(f"  WER moyen demo ({len(refs)} extraits) : {atc_asr.compute_wer(refs, hyps)*100:.1f} %")
    print("\n[T7] transcribe() reelle operationnelle ; interface prete pour la S5 (LLM/RAG).")


if __name__ == "__main__":
    main()
