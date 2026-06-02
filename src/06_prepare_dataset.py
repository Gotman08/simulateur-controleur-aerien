"""
Preuve - Semaine 4 (T1) : verification du corpus ATC pour le fine-tuning
========================================================================
Construit le DatasetDict {train, val, test} (via atc_data, sans copie disque),
verifie la chaine (splits, 16 kHz, transcriptions, bande passante VHF) et produit
des stats + une figure de controle mel "avant/apres bande passante".

NB : pas de save_to_disk (quota disque 20 Go) -> 07/08/09/10 reconstruisent le
DatasetDict a la volee depuis le cache HF via atc_data.load_splits().

Exemples :
  python 06_prepare_dataset.py --smoke              # peek streaming (valide IDs/schemas)
  python 06_prepare_dataset.py                      # stats + figure de controle
  python 06_prepare_dataset.py --max-per-source 200 # version reduite (debug)

Sorties : fig_mel_avant_apres_s4.png, corpus_stats_s4.csv
"""
import os
import csv
import argparse

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("HF_HOME", os.path.join(WORK, "hf_cache"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import atc_data
from atc_audio import preprocess_waveform, FS
from atc_asr import get_normalizer


def smoke_peek():
    """Valide rapidement IDs/schemas via streaming (pas de telechargement complet)."""
    from datasets import load_dataset
    allsrc = {**atc_data.TRAIN_SOURCES, **atc_data.TEST_SOURCES}
    for name, ids in allsrc.items():
        ok = False
        for ds_id in ids:
            try:
                ex, used = None, None
                for sp in ("train", "test", "validation"):
                    try:
                        ex = next(iter(load_dataset(ds_id, split=sp, streaming=True)))
                        used = sp; break
                    except Exception:
                        continue
                if ex is None:
                    raise RuntimeError("aucun split exploitable")
                cols = list(ex.keys())
                tcol = next((c for c in atc_data.TEXT_CANDIDATES if c in cols), "??")
                print(f"[OK] {name:8s} <- {ds_id} [split={used}]")
                print(f"        colonnes : {cols}")
                print(f"        texte ({tcol}) : {str(ex.get(tcol, ''))[:80]!r}")
                ok = True
                break
            except Exception as e:
                print(f"[..] {name:8s} {ds_id} : {type(e).__name__}: {str(e)[:90]}")
        if not ok:
            print(f"[!!] {name:8s} : aucun id n'a fonctionne")
    print("[T1-smoke] termine.")


def make_control_figure(sample_array, path="fig_mel_avant_apres_s4.png"):
    """Mel log d'un extrait : brut vs apres bande passante VHF (validation chaine S2)."""
    from transformers import WhisperFeatureExtractor
    fe = WhisperFeatureExtractor.from_pretrained("openai/whisper-small")
    raw = np.asarray(sample_array, dtype=np.float32)
    bp = preprocess_waveform(raw, training=False)
    mel_raw = fe(raw, sampling_rate=FS).input_features[0]
    mel_bp = fe(bp, sampling_rate=FS).input_features[0]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0), sharey=True)
    for ax, mel, title in zip(axes, [mel_raw, mel_bp],
                              ["Mel - audio brut", "Mel - apres bande passante VHF 300-3400 Hz"]):
        ax.imshow(mel, origin="lower", aspect="auto", cmap="magma")
        ax.set_title(title)
        ax.set_xlabel("Trames temporelles")
    axes[0].set_ylabel("Canaux mel (80)")
    fig.suptitle("Controle du pre-traitement (T1) sur un extrait du corpus", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"[OK] {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--max-per-source", type=int, default=None)
    ap.add_argument("--val-size", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.smoke:
        smoke_peek()
        return

    dd = atc_data.load_splits(max_per_source=args.max_per_source,
                              val_size=args.val_size, seed=args.seed)
    normalizer = get_normalizer()

    rows = []
    print("\n=== STATS CORPUS (T1) ===")
    for split in ("train", "val", "test"):
        ds = dd[split]
        srcs = {}
        for s in ds["source"]:
            srcs[s] = srcs.get(s, 0) + 1
        h = sum(float(d) for d in ds["duration"]) / 3600.0 if "duration" in ds.column_names else float("nan")
        print(f"  {split:5s}: {len(ds):6d} extraits | {h:6.2f} h | sources={srcs}")
        rows.append({"split": split, "n": len(ds), "heures": round(h, 3), "sources": str(srcs)})

    # controle sr + exemples
    ex0 = dd["test"][0]
    sr0 = ex0["audio"]["sampling_rate"]
    print(f"\n  sr (test[0]) = {sr0} (attendu 16000)")
    assert sr0 == FS, "sampling rate != 16000 !"
    print("  Exemples (test) :")
    for i in range(min(3, len(dd["test"]))):
        ex = dd["test"][i]
        print(f"    [{ex['source']}] ({float(ex['duration']):.1f}s) {normalizer(ex['text'])[:90]!r}")

    with open("corpus_stats_s4.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=["split", "n", "heures", "sources"])
        wr.writeheader()
        wr.writerows(rows)
    print("[OK] corpus_stats_s4.csv")

    make_control_figure(ex0["audio"]["array"])
    print("\n[T1] verification terminee (DatasetDict construit a la volee, sans copie disque).")


if __name__ == "__main__":
    main()
