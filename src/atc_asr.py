"""
Helpers ASR partages - Semaine 4
================================
Normalisation texte (identique baseline/FT pour un WER honnete), WER (jiwer),
chargement modele Whisper (+ adapter LoRA optionnel) et transcription par batch
avec le pre-traitement VHF S2.

Utilise par 07 (baseline), 09 (evaluation) et 10 (demo/integration).
"""
import os

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("HF_HOME", os.path.join(WORK, "hf_cache"))

import numpy as np
from atc_audio import preprocess_waveform, FS


def get_normalizer():
    """Normaliseur texte Whisper (minuscule, ponctuation retiree)."""
    try:
        from transformers.models.whisper.english_normalizer import BasicTextNormalizer
        return BasicTextNormalizer()
    except Exception:
        import re
        def _n(s):
            s = s.lower()
            s = re.sub(r"[^a-z0-9' ]+", " ", s)
            return re.sub(r"\s+", " ", s).strip()
        return _n


def compute_wer(refs, hyps):
    """WER global (jiwer) sur les paires a reference non vide. Renvoie une fraction."""
    import jiwer
    pairs = [(r, h) for r, h in zip(refs, hyps) if r and r.strip()]
    if not pairs:
        return float("nan")
    return jiwer.wer([r for r, _ in pairs], [h for _, h in pairs])


def build_inference_model(model_path="openai/whisper-small", adapter_path=None,
                          device="cuda", dtype=None):
    """Charge processor + modele Whisper ; fusionne un adapter LoRA si fourni."""
    import torch
    from transformers import WhisperProcessor, WhisperForConditionalGeneration
    if dtype is None:
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    proc_src = adapter_path if (adapter_path and os.path.exists(
        os.path.join(adapter_path, "preprocessor_config.json"))) else model_path
    processor = WhisperProcessor.from_pretrained(proc_src, language="en", task="transcribe")
    model = WhisperForConditionalGeneration.from_pretrained(model_path, torch_dtype=dtype)
    if adapter_path:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter_path)
        model = model.merge_and_unload()      # fusion pour une inference rapide
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []
    model.to(device).eval()
    return processor, model


def transcribe_arrays(model, processor, arrays, bandpass=True, batch_size=16,
                      language="en", max_new_tokens=128):
    """Transcrit une liste de formes d'onde 16 kHz. bandpass=True applique la chaine VHF S2."""
    import torch
    hyps = []
    fe = processor.feature_extractor
    with torch.no_grad():
        for i in range(0, len(arrays), batch_size):
            chunk = arrays[i:i + batch_size]
            wavs = [preprocess_waveform(np.asarray(a, dtype=np.float32),
                                        training=False) if bandpass
                    else np.asarray(a, dtype=np.float32) for a in chunk]
            feats = fe(wavs, sampling_rate=FS, return_tensors="pt").input_features
            feats = feats.to(model.device, dtype=model.dtype)
            gen = model.generate(feats, language=language, task="transcribe",
                                 max_new_tokens=max_new_tokens)
            hyps.extend(t.strip() for t in processor.batch_decode(gen, skip_special_tokens=True))
    return hyps
