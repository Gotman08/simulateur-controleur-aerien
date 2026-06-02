"""
Preuve - Semaine 6 (V1) : voix de reference pour le clonage XTTS
===============================================================
Extrait quelques courts segments du corpus ATCO2 (test) pour servir de voix de
reference (pilotes/controleurs varies) au clonage zero-shot XTTS.

Tourne dans l'env whisper-atc (a `datasets`). Sortie : <tts_data>/voices/*.wav (16 kHz)
"""
import os

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("HF_HOME", os.path.join(WORK, "hf_cache"))
VOICES = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(WORK, "tts_data")), "voices")


def main():
    import numpy as np
    import soundfile as sf
    from datasets import load_dataset, Audio

    ds = load_dataset("Jzuluaga/atco2_corpus_1h", split="test")
    ds = ds.cast_column("audio", Audio(sampling_rate=16000))
    os.makedirs(VOICES, exist_ok=True)

    saved = []
    target = 3
    for i in range(len(ds)):
        arr = np.asarray(ds[i]["audio"]["array"], dtype=np.float32)
        dur = len(arr) / 16000.0
        if 4.0 <= dur <= 9.0 and np.max(np.abs(arr)) > 0.05:   # duree + non silencieux
            p = os.path.join(VOICES, f"pilot_{len(saved) + 1}.wav")
            sf.write(p, arr, 16000)
            saved.append((os.path.basename(p), round(dur, 1)))
            if len(saved) >= target:
                break

    print(f"[V1] {len(saved)} voix de reference -> {VOICES}")
    for name, dur in saved:
        print(f"  - {name} ({dur}s)")
    assert saved, "aucune voix de reference extraite"


if __name__ == "__main__":
    main()
