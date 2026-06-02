"""
Preuve - Semaine 4 (T2) : baseline WER zero-shot de Whisper
===========================================================
Transcrit le jeu de test avec openai/whisper-small BRUT (sans fine-tuning) et
calcule le WER. C'est le point de reference "avant" : il remplace enfin les
paires d'exemple de la S3 par de la VRAIE inference (cf. transcribe() qui etait
un squelette NotImplementedError en S3).

A lancer sur un noeud armgpu :
  srun -p short --account=r250127 --constraint=armgpu --gres=gpu:h100:1 --mem=64G -c 16 -t 0:30:00 \
    $ENV/bin/python 07_baseline_wer.py

Sorties : resultats_baseline_s4.csv, baseline_predictions_s4.json
"""
import os
import sys
import csv
import json
import argparse

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("HF_HOME", os.path.join(WORK, "hf_cache"))

import atc_asr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(WORK, "data_proc"))
    ap.add_argument("--model", default="openai/whisper-small")
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int, default=None, help="nb max d'extraits (debug)")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--no-bandpass", action="store_true", help="desactive la bande passante VHF")
    ap.add_argument("--out", default="resultats_baseline_s4.csv")
    args = ap.parse_args()

    import jiwer
    import atc_data

    dd = atc_data.load_splits()
    ds = dd[args.split]
    if args.limit:
        ds = ds.select(range(min(args.limit, len(ds))))
    print(f"[*] {args.split} : {len(ds)} extraits | modele {args.model} | "
          f"bandpass={'non' if args.no_bandpass else 'oui'}")

    normalizer = atc_asr.get_normalizer()
    processor, model = atc_asr.build_inference_model(args.model)
    print(f"[*] modele charge sur {model.device} (dtype={model.dtype})")

    arrays = [ex["array"] for ex in ds["audio"]]
    refs = [normalizer(t) for t in ds["text"]]
    sources = ds["source"]

    print("[*] transcription en cours...")
    hyps_raw = atc_asr.transcribe_arrays(model, processor, arrays,
                                         bandpass=not args.no_bandpass,
                                         batch_size=args.batch_size)
    hyps = [normalizer(h) for h in hyps_raw]

    wer_global = atc_asr.compute_wer(refs, hyps)

    # WER par source
    by_src = {}
    for s, r, h in zip(sources, refs, hyps):
        by_src.setdefault(s, ([], []))
        by_src[s][0].append(r)
        by_src[s][1].append(h)

    print("\n=== BASELINE WER (zero-shot) ===")
    print(f"  GLOBAL : {wer_global*100:5.1f} %  (n={len(refs)})")
    for s, (rs, hs) in sorted(by_src.items()):
        print(f"  {s:14s}: {atc_asr.compute_wer(rs, hs)*100:5.1f} %  (n={len(rs)})")

    # sauvegardes
    preds = [{"source": s, "ref": r, "hyp": h, "wer": round(jiwer.wer([r], [h]), 4)}
             for s, r, h in zip(sources, refs, hyps) if r.strip()]
    with open("baseline_predictions_s4.json", "w", encoding="utf-8") as f:
        json.dump({"model": args.model, "wer_global": wer_global, "preds": preds},
                  f, ensure_ascii=False, indent=2)
    print("[OK] baseline_predictions_s4.json")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["modele", "portee", "n", "wer_pct"])
        wr.writerow([args.model, "global", len(refs), round(wer_global * 100, 2)])
        for s, (rs, hs) in sorted(by_src.items()):
            wr.writerow([args.model, s, len(rs), round(atc_asr.compute_wer(rs, hs) * 100, 2)])
    print(f"[OK] {args.out}")

    print("\n  Exemples (ref -> hyp) :")
    for p in preds[:5]:
        print(f"    REF: {p['ref'][:80]}")
        print(f"    HYP: {p['hyp'][:80]}   (wer={p['wer']:.2f})")
    print("\n[T2] baseline terminee.")


if __name__ == "__main__":
    main()
