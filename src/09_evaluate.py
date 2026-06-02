"""
Preuve - Semaine 4 (T6) : evaluation finale baseline vs fine-tune
=================================================================
Transcrit le jeu de test avec (1) whisper-small BRUT puis (2) le modele
fine-tune (adapter LoRA fusionne), calcule les WER, produit la figure de
comparaison (style S3), un CSV et des exemples qualitatifs.

A lancer sur un noeud armgpu (GPU). Sortie : fig_wer_s4.png, resultats_wer_s4.csv,
evaluation_s4.json
"""
import os
import csv
import json
import argparse

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("HF_HOME", os.path.join(WORK, "hf_cache"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import atc_asr


def wer_by_source(refs, hyps, sources):
    out = {}
    for s, r, h in zip(sources, refs, hyps):
        out.setdefault(s, ([], []))
        out[s][0].append(r)
        out[s][1].append(h)
    return {s: atc_asr.compute_wer(rs, hs) for s, (rs, hs) in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(WORK, "data_proc"))
    ap.add_argument("--model", default="openai/whisper-small")
    ap.add_argument("--adapter", default=os.path.join(WORK, "outputs", "lora_small", "adapter"))
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch-size", type=int, default=16)
    args = ap.parse_args()

    import torch
    import atc_data

    dd = atc_data.load_splits()
    ds = dd[args.split]
    if args.limit:
        ds = ds.select(range(min(args.limit, len(ds))))
    normalizer = atc_asr.get_normalizer()
    refs = [normalizer(t) for t in ds["text"]]
    sources = ds["source"]
    arrays = [ex["array"] for ex in ds["audio"]]
    print(f"[*] test : {len(refs)} extraits")

    # --- baseline (brut) -----------------------------------------------------
    proc, model = atc_asr.build_inference_model(args.model)
    base_hyps = [normalizer(h) for h in
                 atc_asr.transcribe_arrays(model, proc, arrays, batch_size=args.batch_size)]
    del model
    torch.cuda.empty_cache()

    # --- fine-tune (adapter LoRA) -------------------------------------------
    proc, model = atc_asr.build_inference_model(args.model, adapter_path=args.adapter)
    ft_hyps = [normalizer(h) for h in
               atc_asr.transcribe_arrays(model, proc, arrays, batch_size=args.batch_size)]
    del model
    torch.cuda.empty_cache()

    wer_base = atc_asr.compute_wer(refs, base_hyps)
    wer_ft = atc_asr.compute_wer(refs, ft_hyps)
    gain = 100.0 * (wer_base - wer_ft) / wer_base if wer_base else float("nan")

    print("\n=== EVALUATION FINALE (T6) ===")
    print(f"  Whisper-small BRUT     : {wer_base*100:5.1f} %")
    print(f"  Whisper-small FINE-TUNE: {wer_ft*100:5.1f} %")
    print(f"  Gain relatif           : {gain:5.1f} %")
    sb, sf = wer_by_source(refs, base_hyps, sources), wer_by_source(refs, ft_hyps, sources)
    for s in sorted(sb):
        print(f"    [{s}] brut={sb[s]*100:5.1f}%  ft={sf[s]*100:5.1f}%")

    # --- figure (style S3) ---------------------------------------------------
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    names = ["Whisper-small\n(brut)", "Whisper-small\n(fine-tune LoRA)"]
    vals = [wer_base * 100, wer_ft * 100]
    bars = ax.bar(names, vals, color=["#dc2626", "#16a34a"], edgecolor="black")
    ax.bar_label(bars, fmt="%.1f %%", padding=3, fontsize=11)
    ax.set_ylabel("WER (%)")
    ax.set_title(f"S4 - WER sur le test ATC ({len(refs)} extraits) | gain {gain:.0f} % relatif")
    ax.set_ylim(0, max(vals) * 1.35 + 1)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig("fig_wer_s4.png", dpi=150)
    print("[OK] fig_wer_s4.png")

    # --- CSV -----------------------------------------------------------------
    with open("resultats_wer_s4.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["modele", "portee", "n", "wer_pct"])
        wr.writerow(["whisper-small-brut", "global", len(refs), round(wer_base * 100, 2)])
        wr.writerow(["whisper-small-ft", "global", len(refs), round(wer_ft * 100, 2)])
        for s in sorted(sb):
            n = sum(1 for x in sources if x == s)
            wr.writerow(["whisper-small-brut", s, n, round(sb[s] * 100, 2)])
            wr.writerow(["whisper-small-ft", s, n, round(sf[s] * 100, 2)])
    print("[OK] resultats_wer_s4.csv")

    # --- exemples qualitatifs ------------------------------------------------
    examples = []
    for i in range(min(8, len(refs))):
        examples.append({"ref": refs[i], "brut": base_hyps[i], "ft": ft_hyps[i]})
    with open("evaluation_s4.json", "w", encoding="utf-8") as f:
        json.dump({"wer_base": wer_base, "wer_ft": wer_ft, "gain_relatif_pct": gain,
                   "by_source_base": sb, "by_source_ft": sf, "examples": examples}, f,
                  ensure_ascii=False, indent=2)
    print("[OK] evaluation_s4.json")

    print("\n  Exemples (REF / BRUT / FT) :")
    for e in examples[:5]:
        print(f"    REF : {e['ref'][:80]}")
        print(f"    BRUT: {e['brut'][:80]}")
        print(f"    FT  : {e['ft'][:80]}")
        print("    " + "-" * 40)
    print("\n[T6] evaluation terminee.")


if __name__ == "__main__":
    main()
