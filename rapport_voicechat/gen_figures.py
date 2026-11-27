"""
Figures du rapport VoiceChat-11B
=================================
Lit `bench/results/voicechat_romeo.json` (+ les references de la cascade) et
produit `rapport_voicechat/figures/*.png`. Meme convention que
`bench/figures.py` : palette Okabe-Ito, dpi 180, aucune valeur saisie a la main.

Execution :  bench\\bench-env\\Scripts\\python.exe rapport_voicechat\\gen_figures.py
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "bench", "results")
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

C = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"]
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3,
                     "figure.dpi": 100, "savefig.dpi": 180,
                     "axes.spines.top": False, "axes.spines.right": False})

ETIQ = {"sapi_radio": "SAPI\n+ canal radio", "sapi_propre": "SAPI\npropre",
        "humain_micro": "humain\nmicro brut", "humain_radio": "humain\n+ canal radio"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)
    print(f"  [fig] {name}")


def main():
    d = load(os.path.join(RES, "voicechat_romeo.json"))
    conds = [c for c in ("sapi_radio", "sapi_propre", "humain_micro", "humain_radio")
             if c in d["rows"]]

    # references appariees de la cascade (memes cas, meme cluster)
    ref = {}
    e2e = load(os.path.join(RES, "e2e_bench_romeo.json"))
    ref["sapi_radio"] = e2e["voix"]["k"] / e2e["voix"]["n"]
    hum = load(os.path.join(RES, "human_e2e.json"))["par_locuteur"]["nicolas"]
    ref["humain_micro"] = hum["micro"]["reussite"]
    ref["humain_radio"] = hum["radio"]["reussite"]

    # ------------------------------------------------------------------
    # Figure 1 : comprehension par condition, VoiceChat vs cascade
    # ------------------------------------------------------------------
    complet, instr, err_lo, err_hi, casc = [], [], [], [], []
    for c in conds:
        rows = d["rows"][c]
        s = d["resume"][c]
        complet.append(s["collationnement_correct"])
        lo, hi = s["ic95_collationnement"]
        err_lo.append(s["collationnement_correct"] - lo)
        err_hi.append(hi - s["collationnement_correct"])
        instr.append(np.mean([all(x["action"] and x["valeur"]
                                  for x in r["collationnement_detail"]) for r in rows]))
        casc.append(ref.get(c, np.nan))

    x = np.arange(len(conds))
    w = 0.27
    fig, ax = plt.subplots(figsize=(7.6, 4.1))
    ax.bar(x - w, complet, w, color=C[0], yerr=[err_lo, err_hi], capsize=3,
           label="VoiceChat : collationnement complet (action + valeur + indicatif)")
    ax.bar(x, instr, w, color=C[1],
           label="VoiceChat : instruction seule (action + valeur)")
    ax.bar(x + w, casc, w, color=C[2],
           label="Cascade Whisper-LoRA $\\rightarrow$ Mistral (ordre TrafScript exact)")
    for i, v in enumerate(casc):
        if np.isnan(v):
            ax.text(x[i] + w, 0.02, "n.d.", ha="center", fontsize=7, color="gray")
    for xi, v in zip(x - w, complet):
        ax.text(xi, v + 0.015, f"{v:.0%}", ha="center", fontsize=7.5)
    for xi, v in zip(x, instr):
        ax.text(xi, v + 0.015, f"{v:.0%}", ha="center", fontsize=7.5)
    for xi, v in zip(x + w, casc):
        if not np.isnan(v):
            ax.text(xi, v + 0.015, f"{v:.0%}", ha="center", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels([ETIQ[c] for c in conds])
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("taux de reussite")
    ax.set_title("Comprehension des 25 clairances du banc, par condition\n"
                 "(barres d'erreur : IC 95 % de Wilson)", fontsize=10)
    ax.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              ncol=1, frameon=False)
    save(fig, "fig_voicechat_conditions.png")

    # ------------------------------------------------------------------
    # Figure 2 : structure des echecs (ce qui manque au collationnement)
    # ------------------------------------------------------------------
    cles = ["indicatif", "action", "valeur"]
    vals = np.array([[d["resume"][c]["collationnement_manques"].get(k, 0)
                      for c in conds] for k in cles], dtype=float)
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    bas = np.zeros(len(conds))
    for i, k in enumerate(cles):
        ax.bar(np.arange(len(conds)), vals[i], 0.5, bottom=bas, color=C[i],
               label=k)
        bas += vals[i]
    ax.set_xticks(np.arange(len(conds)))
    ax.set_xticklabels([ETIQ[c] for c in conds])
    ax.set_ylabel("constituants manquants (sur 25 cas)")
    ax.set_title("Structure des echecs de collationnement")
    ax.legend(fontsize=8)
    save(fig, "fig_voicechat_echecs.png")

    # ------------------------------------------------------------------
    # Figure 3 : intelligibilite de la parole generee (WER aller-retour)
    # ------------------------------------------------------------------
    audio = os.path.join(RES, "voicechat_audio", "voicechat_audio_score.json")
    tts = os.path.join(RES, "tts_bench_romeo.json")
    if os.path.exists(audio) and os.path.exists(tts):
        a = load(audio)["resume"]["sapi_radio"]
        # cles de la forme « moteur/voix » dans tts_bench
        t = load(tts)["engines"]
        noms, wers, cols = ["VoiceChat-11B\n(n = 3)"], [a["wer_aller_retour"]], [C[0]]
        for moteur, etq, col in (("sapi", "SAPI", C[3]), ("kokoro", "Kokoro-82M", C[2]),
                                 ("xtts-romeo", "XTTS clone", C[4])):
            v = [x["wer_aller_retour_propre"] for k, x in t.items()
                 if k.split("/")[0] == moteur and "wer_aller_retour_propre" in x]
            if v:
                noms.append(f"{etq}\n(n = {len(v)} voix)")
                wers.append(float(np.mean(v)))
                cols.append(col)
        fig, ax = plt.subplots(figsize=(6.2, 3.2))
        ax.bar(noms, wers, 0.5, color=cols)
        for i, v in enumerate(wers):
            ax.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
        ax.set_ylabel("WER aller-retour (juge STT fixe)")
        ax.set_title("Intelligibilite de la voix produite (plus bas = mieux)")
        ax.set_ylim(0, max(wers) * 1.25)
        save(fig, "fig_voicechat_tts.png")

    print("[OK] figures ->", FIG)


if __name__ == "__main__":
    main()
