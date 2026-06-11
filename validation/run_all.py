"""
Campagne de validation complete - enchaine les scripts 1 a 4
============================================================
Chaque script tourne dans son PROPRE processus (BlueSky ne supporte qu'une
seule init par processus) et fusionne sa section dans validation/results.json.

Execution :  src\\bluesky-env\\Scripts\\python.exe validation\\run_all.py
Duree totale ~ 12-15 min (domine par la campagne BlueSky du script 2).
"""
import os
import sys
import json
import time
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SCRIPTS = [
    "01_cpa_analytique.py",
    "02_cpa_vs_bluesky.py",
    "03_parseur_eval.py",
    "04_generateur_eval.py",
]

FIGURES = [
    "fig_cpa_analytique_err.png",
    "fig_bluesky_scatter.png",
    "fig_bluesky_erreurs.png",
    "fig_parseur_categories.png",
    "fig_generateur_contraintes.png",
]


def main():
    t0 = time.time()
    python = sys.executable
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for script in SCRIPTS:
        path = os.path.join(HERE, script)
        print(f"\n===== {script} =====")
        r = subprocess.run([python, path], cwd=ROOT, env=env)
        if r.returncode != 0:
            print(f"[ERREUR] {script} a echoue (code {r.returncode})")
            sys.exit(r.returncode)

    # --- verification : sections + figures presentes -------------------------
    res_path = os.path.join(HERE, "results.json")
    with open(res_path, encoding="utf-8") as f:
        data = json.load(f)
    attendues = ["cpa_analytique", "cpa_vs_bluesky", "parseur", "generateur"]
    manquantes = [k for k in attendues if k not in data]
    fig_dir = os.path.join(ROOT, "docs", "assets", "validation")
    figs_absentes = [f for f in FIGURES if not os.path.exists(os.path.join(fig_dir, f))]

    data["meta"] = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version.split()[0],
        "seed": 42,
        "duree_totale_s": round(time.time() - t0, 1),
        "commande": "src\\bluesky-env\\Scripts\\python.exe validation\\run_all.py",
    }
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("\n===== SYNTHESE =====")
    c = data["cpa_analytique"]
    print(f"  CPA analytique  : erreur max {c['erreur_dcpa_nm']['max']:.2e} NM "
          f"sur {c['n_geometries']} geometries, "
          f"{c['coherence_implementation']['n_desaccords']} desaccord(s) implementation")
    b = data["cpa_vs_bluesky"]
    print(f"  CPA vs BlueSky  : MAE d_CPA {b['conflits_predits']['mae_dcpa_nm']:.3f} NM, "
          f"MAE t_CPA {b['conflits_predits']['mae_tcpa_s']:.1f} s, "
          f"precision {b['confusion']['precision']:.3f}, "
          f"rappel {b['confusion']['rappel']:.3f}, F1 {b['confusion']['f1']:.3f}")
    p = data["parseur"]
    print(f"  Parseur         : exactitude globale {p['exactitude_globale']:.1%} "
          f"({p['n_phrases']} phrases), rejet negatifs {p['taux_rejet_negatifs']:.0%}")
    g = data["generateur"]
    print(f"  Generateur      : conformite {g['taux_global']:.1%} "
          f"({g['n_contraintes_ok']}/{g['n_contraintes_verifiees']} contraintes)")
    if manquantes or figs_absentes:
        print(f"  [ATTENTION] sections manquantes: {manquantes}, figures absentes: {figs_absentes}")
        sys.exit(1)
    print(f"  Figures OK ({len(FIGURES)}) dans docs/assets/validation/")
    print(f"[OK] campagne complete en {data['meta']['duree_totale_s']:.0f}s -> {res_path}")


if __name__ == "__main__":
    main()
