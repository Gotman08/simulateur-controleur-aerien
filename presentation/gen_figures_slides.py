"""
Figures de la soutenance : memes donnees, typographie lisible en projection
==========================================================================
Reutilise telles quelles les fonctions de bench/figures.py (memes JSON, memes
courbes) en changeant seulement deux choses :
  - la taille de police (9 pt pour un rapport A4 -> 15 pt pour un ecran) ;
  - le dossier de sortie (presentation/figures/).
Les figures du rapport et de l'article ne sont donc pas modifiees.

Execution :
  bench\\bench-env\\Scripts\\python.exe presentation\\gen_figures_slides.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BENCH = os.path.join(ROOT, "bench")
sys.path.insert(0, BENCH)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import figures as F

# --- sortie vers la presentation, pas vers bench/figures -------------------
F.FIG = os.path.join(HERE, "figures")
os.makedirs(F.FIG, exist_ok=True)

# --- typographie d'ecran ---------------------------------------------------
plt.rcParams.update({
    "font.size": 15,
    "axes.titlesize": 15,
    "axes.labelsize": 14,
    "xtick.labelsize": 13,
    "ytick.labelsize": 13,
    "legend.fontsize": 12,
    "figure.titlesize": 16,
    "lines.linewidth": 2.0,
    "patch.linewidth": 1.2,
    "savefig.dpi": 200,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# --- formats plus larges : un ecran est en 16:9, pas en colonne A4 ---------
_subplots = plt.subplots


def subplots_ecran(*a, **kw):
    """Agrandit les figures d'environ 45 % et aplatit le ratio."""
    fs = kw.get("figsize")
    if fs:
        kw["figsize"] = (fs[0] * 1.45, fs[1] * 1.45)
    return _subplots(*a, **kw)


F.plt.subplots = subplots_ecran

if __name__ == "__main__":
    for nom, fonction in [("STT", F.fig_stt), ("LLM", F.fig_llm),
                          ("TTS", F.fig_tts), ("E2E", F.fig_e2e),
                          ("simulateur", F.fig_sim)]:
        try:
            fonction()
            print(f"  [ok] figures {nom}")
        except Exception as e:                     # resultats partiels
            print(f"  [--] figures {nom} ignorees : {e}")
    print(f"[OK] figures de soutenance -> {F.FIG}")
