# -*- coding: utf-8 -*-
"""
Validation 2 - Le predicteur CPA vs la realite simulee (campagne BlueSky)
=========================================================================
200 rencontres aleatoires de 2 avions au meme FL (FL200-FL360) :
  - positions initiales a 25-60 NM du centre Reims, vitesses CAS 220-300 kt ;
  - ~55 % des cas sont biaises "conflit" : les deux caps visent un point de
    croisement commun P atteint a des instants proches (geometrie du Par. 7
    du rapport), le reste est en caps uniformes (surtout des non-conflits) ;
  - prediction = atc_sim.SimManager._analyze sur l'etat BlueSky stabilise ;
  - verite terrain = distance horizontale minimale observee en laissant voler
    BlueSky 180 s sans aucune commande (pas d'enregistrement 2 s).

UNE seule init BlueSky par processus ; reset() entre deux rencontres.

Execution :  src\\bluesky-env\\Scripts\\python.exe validation\\02_cpa_vs_bluesky.py
"""
import os
import sys
import json
import math
import time
import random

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import bluesky_runtime as bsk                      # noqa: E402
from atc_sim import to_nm, from_nm, SimManager, SEP_NM, LOOKAHEAD_S  # noqa: E402

FIG_DIR = os.path.join(ROOT, "docs", "assets", "validation")
SEED = 42
N_ENC = 200            # nombre de rencontres
T_OBS = 180.0          # duree d'observation (s)
DT_OBS = 2.0           # pas d'enregistrement (s)
T_LOS_REEL = 130.0     # un LoS reel doit survenir avant 130 s
ACTYPE = "A320"


def save_results(key, payload):
    path = os.path.join(HERE, "results.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data[key] = payload
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def tas_nms(cas_kt, alt_ft):
    """CAS (kt) -> TAS (NM/s) en atmosphere standard (meme modele que BlueSky)."""
    from bluesky.tools.aero import vcas2tas, kts, ft
    return float(vcas2tas(cas_kt * kts, alt_ft * ft)) / kts / 3600.0


def bearing(p, q):
    """Cap (deg) du point p vers le point q dans le plan NM (x = est, y = nord)."""
    return math.degrees(math.atan2(q[0] - p[0], q[1] - p[1])) % 360.0


def make_encounter(rng):
    """Tire une rencontre : (fl_ft, [(x, y, hdg, cas), (x, y, hdg, cas)], kind)."""
    alt_ft = float(rng.choice(np.arange(200, 361, 10))) * 100.0
    cas1, cas2 = rng.uniform(220.0, 300.0, 2)
    v1, v2 = tas_nms(cas1, alt_ft), tas_nms(cas2, alt_ft)   # NM/s
    if rng.random() < 0.55:
        # --- cas biaise "conflit" : caps vers un point de croisement commun P
        for _ in range(300):
            tc = rng.uniform(35.0, 110.0)                   # arrivee de l'avion 1 a P
            delta = rng.uniform(-8.0, 8.0) if rng.random() < 0.6 else rng.uniform(-30.0, 30.0)
            ta1, ta2 = tc, max(20.0, tc + delta)            # decalage -> d_CPA varie
            R1, R2 = v1 * ta1, v2 * ta2                     # distances a P
            r1, th1 = rng.uniform(25.0, 60.0), rng.uniform(0.0, 2 * math.pi)
            p1 = (r1 * math.sin(th1), r1 * math.cos(th1))
            lo = max(8.0, abs(R1 - R2) + 0.7)
            hi = R1 + R2 - 0.7
            if lo >= hi:
                continue
            sep, phi = rng.uniform(lo, hi), rng.uniform(0.0, 2 * math.pi)
            p2 = (p1[0] + sep * math.sin(phi), p1[1] + sep * math.cos(phi))
            if not (25.0 <= math.hypot(*p2) <= 60.0):
                continue
            # intersection des cercles C(p1, R1) et C(p2, R2) -> point P
            a = (sep * sep + R1 * R1 - R2 * R2) / (2.0 * sep)
            h2 = R1 * R1 - a * a
            if h2 < 0.0:
                continue
            h = math.sqrt(h2) * (1.0 if rng.random() < 0.5 else -1.0)
            ux, uy = (p2[0] - p1[0]) / sep, (p2[1] - p1[1]) / sep
            P = (p1[0] + a * ux - h * uy, p1[1] + a * uy + h * ux)
            hdg1 = (bearing(p1, P) + rng.uniform(-2.0, 2.0)) % 360.0
            hdg2 = (bearing(p2, P) + rng.uniform(-2.0, 2.0)) % 360.0
            return alt_ft, [(p1[0], p1[1], hdg1, cas1), (p2[0], p2[1], hdg2, cas2)], "biaise"
    # --- cas aleatoire pur (surtout des non-conflits) ------------------------
    while True:
        r1, th1 = rng.uniform(25.0, 60.0), rng.uniform(0.0, 2 * math.pi)
        r2, th2 = rng.uniform(25.0, 60.0), rng.uniform(0.0, 2 * math.pi)
        p1 = (r1 * math.sin(th1), r1 * math.cos(th1))
        p2 = (r2 * math.sin(th2), r2 * math.cos(th2))
        if math.hypot(p1[0] - p2[0], p1[1] - p2[1]) > 8.0:
            break
    hdg1, hdg2 = rng.uniform(0.0, 360.0), rng.uniform(0.0, 360.0)
    return alt_ft, [(p1[0], p1[1], hdg1, cas1), (p2[0], p2[1], hdg2, cas2)], "aleatoire"


def run_encounter(idx, alt_ft, planes):
    """Joue une rencontre dans BlueSky ; renvoie (prediction, d_min, t_dmin, d0)."""
    bsk.reset()
    for k, (x, y, hdg, cas) in enumerate(planes):
        lat, lon = from_nm(x, y)
        bsk.create(f"AC{k + 1}", ACTYPE, lat, lon, hdg, alt_ft, cas)
    bsk.advance(2.0)                                  # stabilisation
    st = bsk.state()
    if len(st) != 2:
        return None
    if any(s.get("tas_kt", 0) == 0 for s in st):      # vitesse pas encore etablie
        bsk.advance(3.0)
        st = bsk.state()
    acs = []
    for s in st:
        x, y = to_nm(s["lat"], s["lon"])
        acs.append({"id": s["id"], "x": x, "y": y, "alt_ft": s["alt_ft"],
                    "gs": s["tas_kt"], "hdg": s["hdg"]})
    los, pred = SimManager._analyze(acs)              # LE predicteur a valider
    d0 = math.hypot(acs[0]["x"] - acs[1]["x"], acs[0]["y"] - acs[1]["y"])

    # vol libre 180 s, enregistrement de la distance toutes les 2 s
    t_rel, d_min, t_dmin = 0.0, d0, 0.0
    while t_rel < T_OBS - 1e-6:
        t_rel += bsk.advance(DT_OBS)
        st = bsk.state()
        if len(st) != 2:
            break
        (xa, ya), (xb, yb) = to_nm(st[0]["lat"], st[0]["lon"]), to_nm(st[1]["lat"], st[1]["lon"])
        d = math.hypot(xa - xb, ya - yb)
        if d < d_min:
            d_min, t_dmin = d, t_rel
    return {"idx": idx, "alt_ft": alt_ft, "los_initial": bool(los),
            "pred": (pred[0] if pred else None), "d0": round(d0, 2),
            "d_min": round(d_min, 3), "t_dmin": round(t_dmin, 1)}


def main():
    t_start = time.time()
    rng = np.random.default_rng(SEED)
    random.seed(SEED)

    print(f"[1] init BlueSky (headless, detached)...")
    bsk.bs()
    rows = []
    for i in range(N_ENC):
        alt_ft, planes, kind = make_encounter(rng)
        r = run_encounter(i, alt_ft, planes)
        if r is None:
            print(f"    rencontre {i}: etat invalide, ignoree")
            continue
        r["kind"] = kind
        rows.append(r)
        if (i + 1) % 20 == 0:
            print(f"    {i + 1}/{N_ENC} rencontres jouees "
                  f"({time.time() - t_start:.0f}s ecoulees)")

    # --- statistiques --------------------------------------------------------
    valides = [r for r in rows if not r["los_initial"]]
    pred_pos = [r for r in valides if r["pred"] is not None]      # conflit predit
    err_d = [r["pred"]["d"] - r["d_min"] for r in pred_pos]
    err_t = [r["pred"]["t"] - r["t_dmin"] for r in pred_pos]
    mae_d = float(np.mean(np.abs(err_d))) if err_d else None
    rmse_d = float(np.sqrt(np.mean(np.square(err_d)))) if err_d else None
    mae_t = float(np.mean(np.abs(err_t))) if err_t else None
    biais_d = float(np.mean(err_d)) if err_d else None

    def real_los(r):
        return r["d_min"] < SEP_NM and r["t_dmin"] <= T_LOS_REEL

    tp = sum(1 for r in valides if r["pred"] and real_los(r))
    fp = sum(1 for r in valides if r["pred"] and not real_los(r))
    fn = sum(1 for r in valides if not r["pred"] and real_los(r))
    tn = sum(1 for r in valides if not r["pred"] and not real_los(r))
    precision = tp / (tp + fp) if tp + fp else None
    rappel = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * rappel / (precision + rappel)
          if precision and rappel and (precision + rappel) > 0 else None)

    print(f"[2] {len(valides)} rencontres valides | {len(pred_pos)} conflits predits "
          f"| {tp + fn} LoS reels")
    print(f"    d_CPA : MAE={mae_d:.3f} NM  RMSE={rmse_d:.3f} NM  biais={biais_d:+.3f} NM")
    print(f"    t_CPA : MAE={mae_t:.2f} s")
    print(f"    confusion : TP={tp} FP={fp} FN={fn} TN={tn}")
    print(f"    precision={precision:.3f}  rappel={rappel:.3f}  F1={f1:.3f}")

    # --- figures -------------------------------------------------------------
    os.makedirs(FIG_DIR, exist_ok=True)
    # 1) scatter d_pred vs d_reel
    fig, ax = plt.subplots(figsize=(6.4, 6))
    dp = [r["pred"]["d"] for r in pred_pos]
    dr = [r["d_min"] for r in pred_pos]
    ax.scatter(dr, dp, s=28, c="#2c7fb8", alpha=0.75, edgecolors="none",
               label="conflit predit (d* < 5 NM, t* <= 120 s)")
    nop = [r for r in valides if r["pred"] is None]
    lim = 12.0
    ax.plot([0, lim], [0, lim], "k--", lw=1, label="diagonale (prediction parfaite)")
    ax.axhline(SEP_NM, color="#d7301f", lw=1, ls=":")
    ax.axvline(SEP_NM, color="#d7301f", lw=1, ls=":",
               label=f"seuil de separation {SEP_NM:.0f} NM")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("d_min reel observe dans BlueSky (NM)")
    ax.set_ylabel("d_CPA predit par SimManager._analyze (NM)")
    ax.set_title(f"Prediction CPA vs realite simulee ({len(pred_pos)} conflits predits)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig_bluesky_scatter.png"), dpi=150)
    plt.close(fig)

    # 2) histogrammes des erreurs
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].hist(err_d, bins=24, color="#2c7fb8", edgecolor="white")
    axes[0].axvline(0, color="k", lw=1, ls="--")
    axes[0].set_xlabel("Erreur d_CPA predit - d_min reel (NM)")
    axes[0].set_ylabel("Nombre de rencontres")
    axes[0].set_title(f"Erreur distance (MAE = {mae_d:.2f} NM)")
    axes[0].grid(alpha=0.3)
    axes[1].hist(err_t, bins=24, color="#41ab5d", edgecolor="white")
    axes[1].axvline(0, color="k", lw=1, ls="--")
    axes[1].set_xlabel("Erreur t_CPA predit - t(d_min) reel (s)")
    axes[1].set_title(f"Erreur temps (MAE = {mae_t:.1f} s)")
    axes[1].grid(alpha=0.3)
    fig.suptitle("Erreurs de prediction sur les conflits predits", y=1.0)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig_bluesky_erreurs.png"), dpi=150)
    plt.close(fig)
    print(f"[3] figures : fig_bluesky_scatter.png, fig_bluesky_erreurs.png")

    duree = time.time() - t_start
    save_results("cpa_vs_bluesky", {
        "seed": SEED,
        "n_rencontres": N_ENC,
        "n_valides": len(valides),
        "protocole": {"fl": [200, 360], "cas_kt": [220, 300],
                      "rayon_centre_nm": [25, 60], "stabilisation_s": 2.0,
                      "observation_s": T_OBS, "pas_obs_s": DT_OBS,
                      "part_biaisee_conflit": 0.55,
                      "seuil_pred": {"d_nm": SEP_NM, "t_s": LOOKAHEAD_S},
                      "seuil_reel": {"d_nm": SEP_NM, "t_s": T_LOS_REEL}},
        "conflits_predits": {"n": len(pred_pos), "mae_dcpa_nm": mae_d,
                             "rmse_dcpa_nm": rmse_d, "biais_dcpa_nm": biais_d,
                             "mae_tcpa_s": mae_t},
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                      "precision": precision, "rappel": rappel, "f1": f1},
        "figures": ["fig_bluesky_scatter.png", "fig_bluesky_erreurs.png"],
        "duree_s": round(duree, 1),
    })
    print(f"[OK] 02_cpa_vs_bluesky termine en {duree:.0f}s -> results.json")


if __name__ == "__main__":
    main()
