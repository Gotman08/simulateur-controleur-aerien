# -*- coding: utf-8 -*-
"""
Validation 3 - Precision du parseur de clairances local (atc_ai.local_interpret)
================================================================================
Jeu de test de 67 phrases avec verite terrain TrafScript, couvrant : cap,
niveau, vitesse, direct (fix du secteur : ENTRY_W, BALMO, CROSS, DELTA,
EXIT_E, ENTRY_S, NORTH), taux de montee/descente, multi-ordres, chiffres
epeles vs compacts, indicatifs en telephonie, variantes francaises, et
10 cas NEGATIFS qui doivent etre rejetes (aucune commande emise).

Verite terrain calibree sur le FORMAT reel de sortie (ALT en pieds :
FL100 -> 'ALT CS 10000' ; HDG/SPD en valeur entiere ; VS signe en ft/min).
La comparaison est insensible a l'ordre des commandes (multi-ensemble).

Execution :  src\\bluesky-env\\Scripts\\python.exe validation\\03_parseur_eval.py
"""
import os
import sys
import json
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from atc_ai import local_interpret  # noqa: E402

FIG_DIR = os.path.join(ROOT, "docs", "assets", "validation")


def save_results(key, payload):
    path = os.path.join(HERE, "results.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data[key] = payload
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --- jeu de test --------------------------------------------------------------
# (categorie, phrase, trafscript attendu, negatif?)
CASES = [
    # --- CAP (8) --------------------------------------------------------------
    ("cap", "air france one two three four turn left heading two seven zero",
     ["HDG AFR1234 270"], False),
    ("cap", "speedbird five seven turn right heading 090", ["HDG BAW57 90"], False),
    ("cap", "AFR1234 fly heading three six zero", ["HDG AFR1234 360"], False),
    ("cap", "EZY21 fly heading 100", ["HDG EZY21 100"], False),
    ("cap", "lufthansa eight eight heading one eight zero", ["HDG DLH88 180"], False),
    ("cap", "ryanair niner turn right heading two two five", ["HDG RYR9 225"], False),
    ("cap", "AFR1234 hdg 045", ["HDG AFR1234 45"], False),
    ("cap", "BAW57 turn left heading 310", ["HDG BAW57 310"], False),
    # --- NIVEAU (10) -----------------------------------------------------------
    ("niveau", "air france one two three four descend flight level one zero zero",
     ["ALT AFR1234 10000"], False),
    ("niveau", "csa one delta zulu climb flight level two four zero",
     ["ALT CSA1DZ 24000"], False),
    ("niveau", "AFR1234 climb FL320", ["ALT AFR1234 32000"], False),
    ("niveau", "BAW57 descend to flight level 80", ["ALT BAW57 8000"], False),
    ("niveau", "EZY21 climb 5 thousand feet", ["ALT EZY21 5000"], False),
    ("niveau", "AFR1234 descend altitude 6000 feet", ["ALT AFR1234 6000"], False),
    ("niveau", "air france one two three four climb to flight level three two zero",
     ["ALT AFR1234 32000"], False),
    ("niveau", "BAW57 maintain flight level 100", ["ALT BAW57 10000"], False),
    ("niveau", "DLH88 descend 4000 feet", ["ALT DLH88 4000"], False),
    ("niveau", "speedbird five seven climb flight level one five zero",
     ["ALT BAW57 15000"], False),
    # --- VITESSE (7) -----------------------------------------------------------
    ("vitesse", "AFR1234 reduce speed two five zero knots", ["SPD AFR1234 250"], False),
    ("vitesse", "AFR1234 increase speed 300", ["SPD AFR1234 300"], False),
    ("vitesse", "RYR9 increase speed to 280 knots", ["SPD RYR9 280"], False),
    ("vitesse", "easyjet two one reduce speed two two zero", ["SPD EZY21 220"], False),
    ("vitesse", "BAW57 speed 250", ["SPD BAW57 250"], False),
    ("vitesse", "csa one delta zulu reduce 230", ["SPD CSA1DZ 230"], False),
    ("vitesse", "AFR1234 maintain 250 knots", ["SPD AFR1234 250"], False),
    # --- DIRECT (6) : fix reels du secteur (secteur_graphe.json) ---------------
    ("direct", "ryanair niner proceed direct delta", ["ADDWPT RYR9 DELTA"], False),
    ("direct", "AFR1234 direct CROSS", ["ADDWPT AFR1234 CROSS"], False),
    ("direct", "AFR1234 proceed direct to NORTH", ["ADDWPT AFR1234 NORTH"], False),
    ("direct", "BAW57 proceed direct ENTRY_W", ["ADDWPT BAW57 ENTRY_W"], False),
    ("direct", "EZY21 direct BALMO", ["ADDWPT EZY21 BALMO"], False),
    ("direct", "DLH88 proceed direct EXIT_E", ["ADDWPT DLH88 EXIT_E"], False),
    # --- TAUX (5) ---------------------------------------------------------------
    ("taux", "AFR1234 climb FL320 expedite",
     ["ALT AFR1234 32000", "VS AFR1234 3000"], False),
    ("taux", "BAW57 descend flight level 80 rate 1500",
     ["ALT BAW57 8000", "VS BAW57 -1500"], False),
    ("taux", "AFR1234 descend flight level 80 1500 feet per minute",
     ["ALT AFR1234 8000", "VS AFR1234 -1500"], False),
    ("taux", "AFR1234 climb flight level 240 rate 2 thousand",
     ["ALT AFR1234 24000", "VS AFR1234 2000"], False),
    ("taux", "EZY21 expedite climb flight level 200",
     ["ALT EZY21 20000", "VS EZY21 3000"], False),
    # --- MULTI-ORDRES (6) --------------------------------------------------------
    ("multi", "csa one delta zulu climb flight level two four zero reduce speed two five zero",
     ["ALT CSA1DZ 24000", "SPD CSA1DZ 250"], False),
    ("multi", "AFR1234 turn left heading 050 descend flight level 90 reduce speed 230",
     ["ALT AFR1234 9000", "HDG AFR1234 50", "SPD AFR1234 230"], False),
    ("multi", "speedbird five seven turn right heading two seven zero descend flight level one one zero",
     ["ALT BAW57 11000", "HDG BAW57 270"], False),
    ("multi", "DLH88 climb flight level 350 increase speed 290",
     ["ALT DLH88 35000", "SPD DLH88 290"], False),
    ("multi", "EZY21 fly heading 180 reduce speed 240",
     ["HDG EZY21 180", "SPD EZY21 240"], False),
    ("multi", "AFR1234 descend flight level 200 proceed direct CROSS",
     ["ALT AFR1234 20000", "ADDWPT AFR1234 CROSS"], False),
    # --- INDICATIFS en telephonie (6) --------------------------------------------
    ("indicatif", "speedbird five seven turn right heading two seven zero",
     ["HDG BAW57 270"], False),
    ("indicatif", "ryanair niner fly heading one two zero", ["HDG RYR9 120"], False),
    ("indicatif", "lufthansa eight eight climb flight level three one zero",
     ["ALT DLH88 31000"], False),
    ("indicatif", "easyjet two one descend flight level one three zero",
     ["ALT EZY21 13000"], False),
    ("indicatif", "csa one delta zulu fly heading two one zero",
     ["HDG CSA1DZ 210"], False),
    ("indicatif", "air france one two three four reduce speed two four zero",
     ["SPD AFR1234 240"], False),
    # --- CHIFFRES epeles vs compacts (4) ------------------------------------------
    ("chiffres", "AFR1234 fly heading one zero zero", ["HDG AFR1234 100"], False),
    ("chiffres", "AFR1234 fly heading 100", ["HDG AFR1234 100"], False),
    ("chiffres", "BAW57 climb flight level one zero zero", ["ALT BAW57 10000"], False),
    ("chiffres", "BAW57 climb flight level 100", ["ALT BAW57 10000"], False),
    # --- FRANCAIS (6) ---------------------------------------------------------------
    ("francais", "AFR1234 descend niveau 1 0 0", ["ALT AFR1234 10000"], False),
    ("francais", "lufthansa eight eight monter niveau 2 4 0", ["ALT DLH88 24000"], False),
    ("francais", "DLH88 descendre niveau 1 0 0", ["ALT DLH88 10000"], False),
    ("francais", "EZY21 cap 180", ["HDG EZY21 180"], False),
    ("francais", "AFR1234 monter niveau 310", ["ALT AFR1234 31000"], False),
    ("francais", "BAW57 descendre au niveau 2 4 0", ["ALT BAW57 24000"], False),
    # --- NEGATIFS (10) : aucune commande ne doit etre emise --------------------------
    ("negatif", "turn left heading 180", [], True),                  # pas d'indicatif
    ("negatif", "descend flight level one zero zero", [], True),    # pas d'indicatif
    ("negatif", "AFR1234 climb flight level 9 9 9", [], True),      # ALT 99900 > 45000 ft
    ("negatif", "AFR1234 climb flight level 460", [], True),        # ALT 46000 > 45000 ft
    ("negatif", "AFR1234 descend flight level five five five", [], True),  # hors bornes
    ("negatif", "AFR1234 speed 400", [], True),                     # SPD 400 > 350 kt
    ("negatif", "AFR1234 proceed direct NOWHERE", [], True),        # waypoint inconnu
    ("negatif", "", [], True),                                      # phrase vide
    ("negatif", "bonjour la tour", [], True),                       # bruit
    ("negatif", "uh radar contact good evening", [], True),         # bruit
]


def main():
    t_start = time.time()
    par_cat = defaultdict(lambda: {"n": 0, "ok": 0})
    details = []
    n_neg_rejet_explicite = 0
    for cat, text, attendu, negatif in CASES:
        r = local_interpret(text)
        obtenu = list(r["trafscript"])
        if negatif:
            ok = (obtenu == [])                       # securite : rien n'est emis
            if ok and r["rejected"]:
                n_neg_rejet_explicite += 1            # rejet signale explicitement
        else:
            ok = sorted(obtenu) == sorted(attendu)    # sortie TrafScript exacte
        par_cat[cat]["n"] += 1
        par_cat[cat]["ok"] += int(ok)
        details.append({"categorie": cat, "phrase": text, "attendu": attendu,
                        "obtenu": obtenu, "rejets": r["rejected"], "ok": ok})
        flag = "OK " if ok else "ECHEC"
        print(f"  [{flag}] ({cat}) {text!r}")
        if not ok:
            print(f"          attendu={attendu}  obtenu={obtenu}  rejets={r['rejected']}")

    positifs = [d for d in details if d["categorie"] != "negatif"]
    negatifs = [d for d in details if d["categorie"] == "negatif"]
    acc_pos = sum(d["ok"] for d in positifs) / len(positifs)
    acc_neg = sum(d["ok"] for d in negatifs) / len(negatifs)
    acc_glob = sum(d["ok"] for d in details) / len(details)

    print(f"\n[1] {len(CASES)} phrases : exactitude globale = {acc_glob:.1%}")
    print(f"    positifs : {sum(d['ok'] for d in positifs)}/{len(positifs)} = {acc_pos:.1%}")
    print(f"    negatifs correctement rejetes : "
          f"{sum(d['ok'] for d in negatifs)}/{len(negatifs)} = {acc_neg:.1%} "
          f"(dont {n_neg_rejet_explicite} avec message de rejet explicite)")
    for cat, st in par_cat.items():
        print(f"    {cat:10s} : {st['ok']}/{st['n']} = {st['ok'] / st['n']:.1%}")

    # --- figure : barres par categorie ---------------------------------------
    os.makedirs(FIG_DIR, exist_ok=True)
    ordre = ["cap", "niveau", "vitesse", "direct", "taux", "multi",
             "indicatif", "chiffres", "francais", "negatif"]
    labels = {"cap": "Cap", "niveau": "Niveau", "vitesse": "Vitesse",
              "direct": "Direct fix", "taux": "Taux (VS)", "multi": "Multi-ordres",
              "indicatif": "Indicatifs", "chiffres": "Chiffres",
              "francais": "Francais", "negatif": "Negatifs (rejet)"}
    cats = [c for c in ordre if c in par_cat]
    vals = [100.0 * par_cat[c]["ok"] / par_cat[c]["n"] for c in cats]
    ns = [par_cat[c]["n"] for c in cats]
    colors = ["#d7301f" if v < 50 else ("#fd8d3c" if v < 100 else "#2c7fb8") for v in vals]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar([labels[c] for c in cats], vals, color=colors, edgecolor="white")
    for b, v, n in zip(bars, vals, ns):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}%\n(n={n})",
                ha="center", va="bottom", fontsize=8)
    ax.set_ylim(0, 115)
    ax.set_ylabel("Exactitude (%)")
    ax.set_title(f"Parseur local de clairances : exactitude par categorie "
                 f"({len(CASES)} phrases)")
    ax.grid(axis="y", alpha=0.3)
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig_parseur_categories.png"), dpi=150)
    plt.close(fig)
    print(f"[2] figure : fig_parseur_categories.png")

    duree = time.time() - t_start
    save_results("parseur", {
        "n_phrases": len(CASES),
        "n_positifs": len(positifs),
        "n_negatifs": len(negatifs),
        "exactitude_globale": acc_glob,
        "exactitude_positifs": acc_pos,
        "taux_rejet_negatifs": acc_neg,
        "negatifs_rejet_explicite": n_neg_rejet_explicite,
        "par_categorie": {c: {"n": par_cat[c]["n"], "ok": par_cat[c]["ok"],
                              "exactitude": par_cat[c]["ok"] / par_cat[c]["n"]}
                          for c in cats},
        "echecs": [d for d in details if not d["ok"]],
        "figure": "fig_parseur_categories.png",
        "duree_s": round(duree, 1),
    })
    print(f"[OK] 03_parseur_eval termine en {duree:.1f}s -> results.json")


if __name__ == "__main__":
    main()
