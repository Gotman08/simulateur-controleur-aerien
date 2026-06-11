"""
Validation 4 - Conformite du generateur de situations local (atc_ai.local_scenario)
====================================================================================
20 descriptions variees (EN et FR) ; pour chacune on verifie que les avions
generes respectent les contraintes demandees :
  - nombre : nombre d'avions exact ;
  - niveau : alt_ft = FL demande x 100 (ou pieds demandes) ;
  - cap    : cap demande, sinon cap d'entree coherent (direction + 180) ;
  - direction : azimut des positions = direction demandee (tolerance 2 deg) ;
  - vitesse : spd_kt demande ;
  - espacement : distance entre avions consecutifs (via to_nm, tolerance 0.5 NM) ;
  - type   : type avion demande.
Chaque contrainte n'est verifiee que si la description la demande.

Execution :  src\\bluesky-env\\Scripts\\python.exe validation\\04_generateur_eval.py
"""
import os
import sys
import json
import math
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from atc_ai import local_scenario  # noqa: E402
from atc_sim import to_nm          # noqa: E402

FIG_DIR = os.path.join(ROOT, "docs", "assets", "validation")
TOL_SPACING_NM = 0.5
TOL_DIR_DEG = 2.0


def save_results(key, payload):
    path = os.path.join(HERE, "results.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data[key] = payload
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --- jeu de test ---------------------------------------------------------------
# Chaque test : description + liste de GROUPES attendus (une clause = un groupe).
# Cles possibles d'un groupe : count, type, alt_ft, hdg, dir_deg, spd, spacing.
# 'hdg' absent + 'dir_deg' present -> cap d'entree attendu = (dir_deg + 180) % 360.
TESTS = [
    ("three A320 from the north at FL300 heading 180, 8 miles apart",
     [{"count": 3, "type": "A320", "alt_ft": 30000, "hdg": 180, "dir_deg": 0, "spacing": 8}]),
    ("two B738 from the south at flight level 240",
     [{"count": 2, "type": "B738", "alt_ft": 24000, "dir_deg": 180}]),
    ("un A319 venant de l ouest au niveau 120",
     [{"count": 1, "type": "A319", "alt_ft": 12000, "dir_deg": 270}]),
    ("four aircraft from the north east at FL350, 6 miles apart, speed 270 knots",
     [{"count": 4, "alt_ft": 35000, "dir_deg": 45, "spacing": 6, "spd": 270}]),
    ("one B77W from the east at FL360 heading 270 speed 290 knots",
     [{"count": 1, "type": "B77W", "alt_ft": 36000, "hdg": 270, "dir_deg": 90, "spd": 290}]),
    ("six A320 from the west at FL280, 10 miles apart",
     [{"count": 6, "type": "A320", "alt_ft": 28000, "dir_deg": 270, "spacing": 10}]),
    ("deux A321 venant du sud est au niveau 310 espaces de 7 milles",
     [{"count": 2, "type": "A321", "alt_ft": 31000, "dir_deg": 135, "spacing": 7}]),
    ("trois B738 venant du nord au niveau 300 cap 180 espaces de 8 milles",
     [{"count": 3, "type": "B738", "alt_ft": 30000, "hdg": 180, "dir_deg": 0, "spacing": 8}]),
    ("a single E190 from the north west at FL330",
     [{"count": 1, "type": "E190", "alt_ft": 33000, "dir_deg": 315}]),
    ("two aircraft from the south west at flight level 250, 12 miles apart",
     [{"count": 2, "alt_ft": 25000, "dir_deg": 225, "spacing": 12}]),
    ("cinq A320 venant de l est au niveau 290",
     [{"count": 5, "type": "A320", "alt_ft": 29000, "dir_deg": 90}]),
    ("one CRJ9 from the south at FL200 speed 230 knots",
     [{"count": 1, "type": "CRJ9", "alt_ft": 20000, "dir_deg": 180, "spd": 230}]),
    ("four B744 from the east at FL340 heading 270",
     [{"count": 4, "type": "B744", "alt_ft": 34000, "hdg": 270, "dir_deg": 90}]),
    ("two A359 from the north at FL380 9 miles apart",
     [{"count": 2, "type": "A359", "alt_ft": 38000, "dir_deg": 0, "spacing": 9}]),
    ("trois A320 du nord est au niveau 320 vitesse 260",
     [{"count": 3, "type": "A320", "alt_ft": 32000, "dir_deg": 45, "spd": 260}]),
    ("one B789 from the west at 11000 feet heading 090",
     [{"count": 1, "type": "B789", "alt_ft": 11000, "hdg": 90, "dir_deg": 270}]),
    ("two E170 from the north at FL310, 5 miles in trail",
     [{"count": 2, "type": "E170", "alt_ft": 31000, "dir_deg": 0, "spacing": 5}]),
    ("deux A333 venant du sud au niveau 360 espaces de 10 milles",
     [{"count": 2, "type": "A333", "alt_ft": 36000, "dir_deg": 180, "spacing": 10}]),
    ("five aircraft from the south east at FL270 heading 300 speed 250 knots 6 miles apart",
     [{"count": 5, "alt_ft": 27000, "hdg": 300, "dir_deg": 135, "spd": 250, "spacing": 6}]),
    ("two B738 from the south at flight level 240 and one A319 from the west at fl120",
     [{"count": 2, "type": "B738", "alt_ft": 24000, "dir_deg": 180},
      {"count": 1, "type": "A319", "alt_ft": 12000, "dir_deg": 270}]),
]


def azimut(x, y):
    return math.degrees(math.atan2(x, y)) % 360.0


def ang_err(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def check_group(group, acs, stats, fails, desc):
    """Verifie les contraintes d'un groupe sur la liste d'avions correspondante."""
    def tally(name, ok, info=""):
        stats[name]["n"] += 1
        stats[name]["ok"] += int(ok)
        if not ok:
            fails.append({"description": desc, "contrainte": name, "detail": info})

    if "type" in group:
        tally("type", all(a["type"] == group["type"] for a in acs),
              f"types={[a['type'] for a in acs]} attendu={group['type']}")
    if "alt_ft" in group:
        tally("niveau", all(abs(a["alt_ft"] - group["alt_ft"]) < 1 for a in acs),
              f"alt={[a['alt_ft'] for a in acs]} attendu={group['alt_ft']}")
    if "spd" in group:
        tally("vitesse", all(abs(a["spd_kt"] - group["spd"]) < 1 for a in acs),
              f"spd={[a['spd_kt'] for a in acs]} attendu={group['spd']}")
    hdg_attendu = group.get("hdg")
    if hdg_attendu is None and "dir_deg" in group:
        hdg_attendu = (group["dir_deg"] + 180.0) % 360.0       # cap d'entree coherent
    if hdg_attendu is not None:
        tally("cap", all(ang_err(a["hdg"], hdg_attendu) <= 0.5 for a in acs),
              f"hdg={[a['hdg'] for a in acs]} attendu={hdg_attendu}")
    if "dir_deg" in group:
        pos = [to_nm(a["lat"], a["lon"]) for a in acs]
        tally("direction", all(ang_err(azimut(x, y), group["dir_deg"]) <= TOL_DIR_DEG
                               for x, y in pos),
              f"azimuts={[round(azimut(x, y), 1) for x, y in pos]} attendu={group['dir_deg']}")
    if "spacing" in group and len(acs) >= 2:
        pos = [to_nm(a["lat"], a["lon"]) for a in acs]
        dists = [math.hypot(pos[i + 1][0] - pos[i][0], pos[i + 1][1] - pos[i][1])
                 for i in range(len(pos) - 1)]
        tally("espacement", all(abs(d - group["spacing"]) <= TOL_SPACING_NM for d in dists),
              f"dists={[round(d, 2) for d in dists]} attendu={group['spacing']}")


def main():
    t_start = time.time()
    stats = defaultdict(lambda: {"n": 0, "ok": 0})
    fails = []
    n_tests_ok = 0
    for desc, groups in TESTS:
        acs = local_scenario(desc)
        n_attendu = sum(g["count"] for g in groups)
        ok_count = (len(acs) == n_attendu)
        stats["nombre"]["n"] += 1
        stats["nombre"]["ok"] += int(ok_count)
        before = len(fails)
        if not ok_count:
            fails.append({"description": desc, "contrainte": "nombre",
                          "detail": f"{len(acs)} avions, attendu {n_attendu}"})
        else:
            i = 0
            for g in groups:
                check_group(g, acs[i:i + g["count"]], stats, fails, desc)
                i += g["count"]
        test_ok = ok_count and len(fails) == before
        n_tests_ok += int(test_ok)
        print(f"  [{'OK ' if test_ok else 'ECHEC'}] {desc!r} -> {len(acs)} avion(s)")

    n_checks = sum(s["n"] for s in stats.values())
    n_ok = sum(s["ok"] for s in stats.values())
    print(f"\n[1] {len(TESTS)} descriptions, {n_checks} contraintes verifiees, "
          f"{n_ok} respectees ({n_ok / n_checks:.1%})")
    print(f"    descriptions entierement conformes : {n_tests_ok}/{len(TESTS)}")
    for k, s in stats.items():
        print(f"    {k:11s} : {s['ok']}/{s['n']} = {s['ok'] / s['n']:.1%}")
    if fails:
        print("    echecs :", fails)

    # --- figure ---------------------------------------------------------------
    os.makedirs(FIG_DIR, exist_ok=True)
    ordre = ["nombre", "niveau", "cap", "direction", "vitesse", "espacement", "type"]
    cats = [c for c in ordre if c in stats]
    vals = [100.0 * stats[c]["ok"] / stats[c]["n"] for c in cats]
    ns = [stats[c]["n"] for c in cats]
    colors = ["#d7301f" if v < 50 else ("#fd8d3c" if v < 100 else "#41ab5d") for v in vals]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    bars = ax.bar([c.capitalize() for c in cats], vals, color=colors, edgecolor="white")
    for b, v, n in zip(bars, vals, ns):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}%\n(n={n})",
                ha="center", va="bottom", fontsize=8)
    ax.set_ylim(0, 115)
    ax.set_ylabel("Taux de conformite (%)")
    ax.set_title(f"Generateur de situations : conformite par contrainte "
                 f"({len(TESTS)} descriptions)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig_generateur_contraintes.png"), dpi=150)
    plt.close(fig)
    print("[2] figure : fig_generateur_contraintes.png")

    duree = time.time() - t_start
    save_results("generateur", {
        "n_descriptions": len(TESTS),
        "n_contraintes_verifiees": n_checks,
        "n_contraintes_ok": n_ok,
        "taux_global": n_ok / n_checks,
        "descriptions_conformes": n_tests_ok,
        "tolerances": {"espacement_nm": TOL_SPACING_NM, "direction_deg": TOL_DIR_DEG},
        "par_contrainte": {c: {"n": stats[c]["n"], "ok": stats[c]["ok"],
                               "taux": stats[c]["ok"] / stats[c]["n"]} for c in cats},
        "echecs": fails,
        "figure": "fig_generateur_contraintes.png",
        "duree_s": round(duree, 1),
    })
    print(f"[OK] 04_generateur_eval termine en {duree:.1f}s -> results.json")


if __name__ == "__main__":
    main()
