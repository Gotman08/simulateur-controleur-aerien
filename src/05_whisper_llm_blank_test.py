"""
Preuve - Semaine 3 : harnais de tests "à blanc" Whisper + LLM open-source
=========================================================================
Objectif S3 : valider le comportement BRUT des modèles sur notre corpus,
AVANT tout fine-tuning. Ce script :
  - implémente une métrique WER (Word Error Rate) correcte (distance de
    Levenshtein au niveau des mots),
  - l'exécute sur des paires (référence, hypothèse) d'exemple,
  - agrège les résultats par modèle et produit un graphique + un CSV.

NB : les hypothèses ci-dessous sont des EXEMPLES illustratifs servant à
valider le harnais de mesure. Le branchement réel sur les modèles se fait
via la fonction transcribe() (squelette fourni, désactivé par défaut).

Exécution :  python 05_whisper_llm_blank_test.py
Sorties   :  resultats_tests_blanc.csv, fig_wer_baseline.png
"""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def wer(ref: str, hyp: str) -> float:
    """Word Error Rate = (S + D + I) / N, via distance d'édition sur les mots."""
    r, h = ref.lower().split(), hyp.lower().split()
    n, m = len(r), len(h)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if r[i - 1] == h[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1,        # suppression
                          d[i][j - 1] + 1,        # insertion
                          d[i - 1][j - 1] + cost) # substitution
    return d[n][m] / max(1, n)


# --- squelette de branchement réel (désactivé : pas de GPU/modèle ici) -----
def transcribe(audio_path, model_name):           # pragma: no cover
    raise NotImplementedError(
        "Brancher ici whisper / faster-whisper. "
        "Ex : faster_whisper.WhisperModel(model_name).transcribe(audio_path)")


# --- jeu d'évaluation d'exemple (validation du harnais) --------------------
# (référence, hypothèse_whisper_base, hypothèse_llm_postcorr)
EVAL = [
    ("air france one two three four turn right heading two seven zero",
     "air france one two tree four turn right heading to seven zero",
     "air france one two three four turn right heading two seven zero"),
    ("speedbird five seven climb flight level three five zero",
     "speed bird five seven climb flight level tree five zero",
     "speedbird five seven climb flight level three five"),        # résiduel : 'zero' omis
    ("lufthansa eight eight descend flight level two four zero",
     "lufthansa eight eight the send flight level two four zero",
     "lufthansa eight eight descend flight level two four oh"),    # résiduel : oh / zero
    ("ryanair niner contact approach one one niner decimal seven",
     "ryanair nine contact approach one one nine decimal seven",
     "ryanair niner contact approach one one niner decimal seven"),
]

MODELS = {
    "Whisper-base (brut)":      [w[1] for w in EVAL],
    "Whisper + post-corr. LLM": [w[2] for w in EVAL],
}
REFS = [w[0] for w in EVAL]


def main():
    rows = []
    summary = {}
    for model, hyps in MODELS.items():
        wers = [wer(r, h) for r, h in zip(REFS, hyps)]
        summary[model] = sum(wers) / len(wers)
        for i, (r, h, e) in enumerate(zip(REFS, hyps, wers)):
            rows.append({"modele": model, "echantillon": f"S3-{i+1:02d}",
                         "wer": round(e, 4)})

    with open("resultats_tests_blanc.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=["modele", "echantillon", "wer"])
        wr.writeheader(); wr.writerows(rows)
    print("[OK] resultats_tests_blanc.csv")

    for model, mean in summary.items():
        print(f"  {model:28s} WER moyen = {mean*100:5.1f} %")

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    names = list(summary.keys())
    vals = [summary[n] * 100 for n in names]
    bars = ax.bar(names, vals, color=["#dc2626", "#16a34a"], edgecolor="black")
    ax.bar_label(bars, fmt="%.1f %%", padding=3, fontsize=10)
    ax.set_ylabel("WER moyen (%)")
    ax.set_title("Tests à blanc S3 : WER de référence (données d'exemple)")
    ax.set_ylim(0, max(vals) * 1.4)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig("fig_wer_baseline.png", dpi=150)
    print("[OK] fig_wer_baseline.png")


if __name__ == "__main__":
    main()
