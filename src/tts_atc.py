"""
Synthese vocale ATC - Semaine 6 (V1)
====================================
XTTS-v2 (clonage zero-shot) : synthetise une lecture en clonant une voix de
reference, puis applique la degradation VHF (Butterworth S2) pour un rendu radio
realiste (fermeture du fosse sim-to-real). Sortie wav 16 kHz (entree pipeline).

Tourne dans l'env tts-env (coqui-tts). Reutilise atc_audio.preprocess_waveform.
"""
import os

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("XDG_DATA_HOME", os.path.join(WORK, "tts_data"))
os.environ.setdefault("COQUI_TOS_AGREED", "1")

import numpy as np
from scipy.signal import resample_poly
from atc_audio import preprocess_waveform, FS

XTTS_SR = 24000          # XTTS-v2 sort a 24 kHz
_TTS = {}


def _load():
    if "m" not in _TTS:
        import torch
        import tts_compat
        tts_compat.patch()                       # shim transformers 5.x avant d'importer TTS
        from TTS.api import TTS
        # ATC_TTS_DEVICE=cpu force le CPU (contourne le bug cuFFT torchaudio/GH200
        # dans le speaker-encoder XTTS). Sinon GPU si dispo.
        dev = os.environ.get("ATC_TTS_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
        _TTS["m"] = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(dev)
    return _TTS["m"]


def synth(text, ref_wav, out_path=None, language="en", vhf=True):
    """Synthetise `text` en clonant `ref_wav` ; renvoie un np.float32 16 kHz (+ ecrit out_path)."""
    import soundfile as sf
    tts = _load()
    wav = np.asarray(tts.tts(text=text, speaker_wav=ref_wav, language=language), dtype=np.float32)
    wav16 = resample_poly(wav, FS, XTTS_SR).astype(np.float32)        # 24k -> 16k
    peak = np.max(np.abs(wav16)) + 1e-9
    if peak > 1.0:
        wav16 = wav16 / peak
    if vhf:
        wav16 = preprocess_waveform(wav16, training=False)            # bande passante VHF 300-3400 Hz
    if out_path:
        sf.write(out_path, wav16, FS)
    return wav16


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="air france one two three four descend flight level one hundred")
    ap.add_argument("--ref", required=True, help="wav de voix de reference (clonage)")
    ap.add_argument("--out", default=os.path.join(os.environ["XDG_DATA_HOME"], "synth.wav"))
    ap.add_argument("--no-vhf", action="store_true")
    args = ap.parse_args()
    w = synth(args.text, args.ref, args.out, vhf=not args.no_vhf)
    print(f"[V1] synth {len(w)/FS:.1f}s -> {args.out} (vhf={'non' if args.no_vhf else 'oui'})")
