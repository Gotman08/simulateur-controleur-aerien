"""
Validation 1 - Verification de la formule CPA par propriete
===========================================================
Deux mobiles en mouvement rectiligne uniforme (MRU) :
    position relative  r(t) = r0 + v t
    d^2(t) = |r0|^2 + 2 (r0.v) t + |v|^2 t^2   (polynome de degre 2, convexe)
    minimum en t* = -(r0.v)/|v|^2 (si |v| > 0),  d_CPA = |r0 + v t*|

Test par propriete : 100 000 geometries aleatoires ; on compare (t*, d*)
analytiques a un minimum numerique sur grille fine (dt = 0.05 s sur [0, 300 s]).
On verifie aussi que l'IMPLEMENTATION (atc_sim.SimManager._analyze) renvoie
exactement la prediction analytique (decision + valeurs arrondies).

Execution :  src\\bluesky-env\\Scripts\\python.exe validation\\01_cpa_analytique.py
"""
import os
import sys
import json
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from atc_sim import SimManager, SEP_NM, LOOKAHEAD_S  # noqa: E402

FIG_DIR = os.path.join(ROOT, "docs", "assets", "validation")
SEED = 42
N = 100_000          # geometries aleatoires
T_MAX = 300.0        # horizon de la grille (s)
DT = 0.05            # pas de la grille (s)


def save_results(key, payload):
    path = os.path.join(HERE, "results.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data[key] = payload
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    t_start = time.time()
    rng = np.random.default_rng(SEED)

    # --- geometries aleatoires : 2 mobiles, plan NM (x = est, y = nord) -----
    x1, y1, x2, y2 = rng.uniform(-80.0, 80.0, size=(4, N))
    h1, h2 = rng.uniform(0.0, 360.0, size=(2, N))
    s1, s2 = rng.uniform(150.0, 550.0, size=(2, N))      # vitesses sol (kt)

    def vel(spd_kt, hdg_deg):
        v = spd_kt / 3600.0                              # NM/s
        h = np.radians(hdg_deg)
        return v * np.sin(h), v * np.cos(h)              # convention atc_sim

    v1x, v1y = vel(s1, h1)
    v2x, v2y = vel(s2, h2)
    r0x, r0y = x1 - x2, y1 - y2
    vx, vy = v1x - v2x, v1y - v2y
    vv = vx * vx + vy * vy                               # coefficient de t^2

    # --- solution analytique ------------------------------------------------
    # d^2(t) est convexe (coefficient |v|^2 > 0) : t* est LE minimum global.
    n_degenere = int(np.sum(vv < 1e-12))                 # vitesse relative nulle
    tstar = np.where(vv > 1e-12, -(r0x * vx + r0y * vy) / np.maximum(vv, 1e-12), 0.0)
    dstar = np.hypot(r0x + vx * tstar, r0y + vy * tstar)
    tclamp = np.clip(tstar, 0.0, T_MAX)                  # minimum restreint a [0, T_MAX]
    d_analytique = np.hypot(r0x + vx * tclamp, r0y + vy * tclamp)

    # --- minimum numerique sur grille fine (par blocs, memoire bornee) -----
    grid = np.arange(0.0, T_MAX + DT / 2, DT)            # 6001 points
    d_grille = np.empty(N)
    t_grille = np.empty(N)
    chunk = 1000
    for i in range(0, N, chunk):
        sl = slice(i, min(i + chunk, N))
        gx = r0x[sl, None] + vx[sl, None] * grid[None, :]
        gy = r0y[sl, None] + vy[sl, None] * grid[None, :]
        d2 = gx * gx + gy * gy
        k = np.argmin(d2, axis=1)
        d_grille[sl] = np.sqrt(d2[np.arange(d2.shape[0]), k])
        t_grille[sl] = grid[k]

    err_d = np.abs(d_grille - d_analytique)              # >= 0 a l'arrondi pres
    interieur = (tstar > 0.0) & (tstar < T_MAX) & (vv > 1e-12)
    err_t_int = np.abs(t_grille[interieur] - tstar[interieur])

    print(f"[1] {N} geometries, grille dt={DT}s sur [0,{T_MAX:.0f}s]")
    print(f"    erreur d_CPA : max={err_d.max():.3e} NM  moyenne={err_d.mean():.3e} NM")
    print(f"    minima interieurs (0<t*<{T_MAX:.0f}s) : {int(interieur.sum())} cas, "
          f"erreur t* max={err_t_int.max():.3f}s (resolution grille {DT}s)")
    print(f"    cas degeneres |v|~0 : {n_degenere}  |  min |v|^2 = {vv.min():.3e} (NM/s)^2 > 0")

    # --- coherence de l'implementation SimManager._analyze ------------------
    # On rejoue chaque geometrie (meme altitude) dans le predicteur reel et on
    # verifie : meme decision (conflit predit / LoS / rien) et memes (t, d)
    # aux arrondis pres de l'implementation (t entier, d au dixieme de NM).
    dist0 = np.hypot(r0x, r0y)
    n_pred_attendu = 0
    n_pred_obtenu = 0
    n_mismatch = 0
    exemples_mismatch = []
    for i in range(N):
        a = {"id": "A", "x": float(x1[i]), "y": float(y1[i]), "alt_ft": 30000.0,
             "gs": float(s1[i]), "hdg": float(h1[i])}
        b = {"id": "B", "x": float(x2[i]), "y": float(y2[i]), "alt_ft": 30000.0,
             "gs": float(s2[i]), "hdg": float(h2[i])}
        los, pred = SimManager._analyze([a, b])
        attendu_los = dist0[i] < SEP_NM
        attendu_pred = (not attendu_los and vv[i] >= 1e-9
                        and 0.0 < tstar[i] <= LOOKAHEAD_S and dstar[i] < SEP_NM)
        n_pred_attendu += int(attendu_pred)
        n_pred_obtenu += len(pred)
        ok = True
        if attendu_los != bool(los):
            ok = False
        if attendu_pred != bool(pred):
            ok = False
        if pred and attendu_pred:
            t_p, d_p = pred[0]["t"], pred[0]["d"]
            if abs(t_p - tstar[i]) > 0.5 + 1e-6 or abs(d_p - dstar[i]) > 0.05 + 1e-6:
                ok = False
        if not ok:
            n_mismatch += 1
            if len(exemples_mismatch) < 5:
                exemples_mismatch.append({"i": i, "t*": float(tstar[i]),
                                          "d*": float(dstar[i]), "pred": pred, "los": los})
    print(f"[2] coherence implementation _analyze : {N} cas, "
          f"{n_pred_obtenu} predictions, {n_mismatch} desaccords")
    if exemples_mismatch:
        print("    exemples :", exemples_mismatch)

    # --- figure : distribution de l'erreur ----------------------------------
    os.makedirs(FIG_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(err_d, bins=80, color="#2c7fb8", edgecolor="white", linewidth=0.3)
    ax.set_yscale("log")
    ax.set_xlabel("Erreur |d_CPA analytique - d_CPA grille|  (NM)")
    ax.set_ylabel("Nombre de geometries (log)")
    ax.set_title(f"Formule CPA vs minimum sur grille fine ({N:,} geometries, dt={DT} s)"
                 .replace(",", " "))
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig_path = os.path.join(FIG_DIR, "fig_cpa_analytique_err.png")
    fig.savefig(fig_path, dpi=150)
    plt.close(fig)
    print(f"[3] figure : {fig_path}")

    duree = time.time() - t_start
    save_results("cpa_analytique", {
        "seed": SEED,
        "n_geometries": N,
        "grille": {"dt_s": DT, "horizon_s": T_MAX},
        "tirages": {"positions_nm": [-80, 80], "caps_deg": [0, 360],
                    "vitesses_sol_kt": [150, 550]},
        "erreur_dcpa_nm": {"max": float(err_d.max()), "moyenne": float(err_d.mean()),
                           "p99": float(np.percentile(err_d, 99))},
        "minima_interieurs": {"n": int(interieur.sum()),
                              "erreur_tcpa_max_s": float(err_t_int.max()),
                              "erreur_tcpa_moyenne_s": float(err_t_int.mean())},
        "convexite": {"min_v2": float(vv.min()), "cas_degeneres": n_degenere},
        "coherence_implementation": {"n_cas": N, "n_predictions": int(n_pred_obtenu),
                                     "n_predictions_attendues": int(n_pred_attendu),
                                     "n_desaccords": int(n_mismatch)},
        "figure": "fig_cpa_analytique_err.png",
        "duree_s": round(duree, 1),
    })
    print(f"[OK] 01_cpa_analytique termine en {duree:.1f}s -> results.json")


if __name__ == "__main__":
    main()
