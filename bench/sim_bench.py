"""
Benchmark simulateur & geometrie - extension statistique de la validation
=========================================================================
Complements de rigueur a la campagne validation/ (qui reste la reference
historique gelee) :

  A. CPA analytique MULTI-GRAINES : 5 graines x 200 000 geometries (1 M au
     total), erreur |dCPA prédit - dCPA grille fine| (grille numerique
     INDEPENDANTE dt=0.05 s, vectorisee), accord de decision predire/ne pas
     predire. Robustesse au choix de graine.

  B. Conflit garanti par construction (NOUVEAU) : preuve statistique de la
     garantie de atc_exercise.make_conflict_pair sur 2 000 tirages - dCPA
     analytique ~= 0, tCPA ~= t_c annonce, t_c dans [240, 420] s.

  C. Montee en charge BlueSky REPETEE : 5 repetitions x N avions (5..200),
     facteur temps reel avec IC bootstrap (la validation historique n'avait
     qu'une mesure par point).

  D. Latence du parseur de reference : percentiles par interpolation numpy
     (correction du p95 approximatif de 05_performance).

Execution (venv de l'application, BlueSky requis pour C) :
  src\\bluesky-env\\Scripts\\python.exe bench\\sim_bench.py
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

from bench_stats import bootstrap_ci_mean, latency_summary

RESULTS_DIR = os.path.join(HERE, "results")
OUT = os.path.join(RESULTS_DIR, "sim_bench.json")

SEP_NM, SEP_FT, LOOKAHEAD_S = 5.0, 1000.0, 120.0
GRID_DT, GRID_HORIZON = 0.05, 300.0


# =============================================================================
#  A. CPA analytique multi-graines (grille numerique independante, vectorisee)
# =============================================================================
def cpa_campaign(seed, n):
    from atc_sim import SimManager
    rng = np.random.default_rng(seed)
    pos = rng.uniform(-80.0, 80.0, size=(n, 4))       # x1 y1 x2 y2 (NM)
    hdg = rng.uniform(0.0, 360.0, size=(n, 2))
    spd = rng.uniform(150.0, 550.0, size=(n, 2))      # kt (vitesse sol)

    # cinematique relative (NM/s) - meme convention que _vel_nm_s (cap nautique)
    v1 = np.stack([spd[:, 0] * np.sin(np.radians(hdg[:, 0])),
                   spd[:, 0] * np.cos(np.radians(hdg[:, 0]))], axis=1) / 3600.0
    v2 = np.stack([spd[:, 1] * np.sin(np.radians(hdg[:, 1])),
                   spd[:, 1] * np.cos(np.radians(hdg[:, 1]))], axis=1) / 3600.0
    dp = pos[:, 0:2] - pos[:, 2:4]
    dv = v1 - v2

    # grille fine INDEPENDANTE (echantillonnage temporel direct des distances)
    ts = np.arange(0.0, GRID_HORIZON + GRID_DT / 2, GRID_DT)
    grid_min_d = np.empty(n)
    grid_argmin_t = np.empty(n)
    chunk = 2000
    for i in range(0, n, chunk):
        dpx = dp[i:i + chunk, 0:1] + dv[i:i + chunk, 0:1] * ts[None, :]
        dpy = dp[i:i + chunk, 1:2] + dv[i:i + chunk, 1:2] * ts[None, :]
        d2 = dpx * dpx + dpy * dpy
        k = np.argmin(d2, axis=1)
        grid_min_d[i:i + chunk] = np.sqrt(d2[np.arange(d2.shape[0]), k])
        grid_argmin_t[i:i + chunk] = ts[k]

    # prediction de l'implementation REELLE (SimManager._analyze, paire a paire)
    err_dcpa, err_tcpa_int = [], []
    n_pred, n_pred_attendu, n_desaccords, n_los_initial = 0, 0, 0, 0
    for i in range(n):
        acs = [{"id": "A", "x": pos[i, 0], "y": pos[i, 1], "alt_ft": 30000.0,
                "hdg": hdg[i, 0], "gs": spd[i, 0]},
               {"id": "B", "x": pos[i, 2], "y": pos[i, 3], "alt_ft": 30000.0,
                "hdg": hdg[i, 1], "gs": spd[i, 1]}]
        current, predicted = SimManager._analyze(acs)
        d0 = math.hypot(dp[i, 0], dp[i, 1])
        if d0 < SEP_NM:
            n_los_initial += 1
            continue
        # decision attendue d'apres la grille (meme semantique que _analyze)
        vv = dv[i, 0] ** 2 + dv[i, 1] ** 2
        if vv < 1e-9:
            t_star = -1.0
        else:
            t_star = -(dp[i, 0] * dv[i, 0] + dp[i, 1] * dv[i, 1]) / vv
        interieur = 0.0 < grid_argmin_t[i] < GRID_HORIZON - GRID_DT
        attendu = bool(grid_min_d[i] < SEP_NM and 0.0 < t_star <= LOOKAHEAD_S)
        obtenu = bool(predicted)
        n_pred += int(obtenu)
        n_pred_attendu += int(attendu)
        if obtenu != attendu:
            n_desaccords += 1
        if obtenu and attendu:
            err_dcpa.append(abs(predicted[0]["d"] - grid_min_d[i]))
            if interieur:
                err_tcpa_int.append(abs(predicted[0]["t"] - grid_argmin_t[i]))
    ed = np.array(err_dcpa)
    et = np.array(err_tcpa_int)
    return {
        "seed": int(seed), "n": int(n), "n_los_initial": n_los_initial,
        "n_predictions": n_pred, "n_predictions_attendues": n_pred_attendu,
        "n_desaccords": n_desaccords,
        "erreur_dcpa_nm": {"max": float(ed.max()) if ed.size else None,
                           "moyenne": float(ed.mean()) if ed.size else None,
                           "p99": float(np.percentile(ed, 99)) if ed.size else None},
        "erreur_tcpa_s": {"max": float(et.max()) if et.size else None,
                          "moyenne": float(et.mean()) if et.size else None},
    }


# =============================================================================
#  B. Garantie de conflit par construction (make_conflict_pair)
# =============================================================================
def conflict_guarantee(n=2000):
    from atc_exercise import make_conflict_pair
    from atc_sim import to_nm
    dcpas, tcpas, tcs = [], [], []
    n_ok = 0
    for seed in range(n):
        rng = random.Random(seed)
        aircraft, t_c = make_conflict_pair(rng, ["AAA111", "BBB222"], 30000.0)
        st = []
        for a in aircraft:
            x, y = to_nm(a["lat"], a["lon"])
            v = a["spd_kt"] / 3600.0
            rad = math.radians(a["hdg"])
            st.append((x, y, v * math.sin(rad), v * math.cos(rad)))
        dx, dy = st[0][0] - st[1][0], st[0][1] - st[1][1]
        rvx, rvy = st[0][2] - st[1][2], st[0][3] - st[1][3]
        vv = rvx * rvx + rvy * rvy
        t = -(dx * rvx + dy * rvy) / vv if vv > 1e-12 else float("nan")
        dcpa = math.hypot(dx + rvx * t, dy + rvy * t)
        dcpas.append(dcpa)
        tcpas.append(t)
        tcs.append(t_c)
        n_ok += int(dcpa < SEP_NM and 240.0 <= t_c <= 420.0 and abs(t - t_c) < 10.0)
    d = np.array(dcpas)
    terr = np.abs(np.array(tcpas) - np.array(tcs))
    return {
        "n": n, "taux_garantie": n_ok / n,
        "dcpa_nm": {"max": float(d.max()), "moyenne": float(d.mean()),
                    "p99": float(np.percentile(d, 99))},
        "abs_err_tcpa_vs_tc_s": {"max": float(terr.max()),
                                 "moyenne": float(terr.mean()),
                                 "p99": float(np.percentile(terr, 99))},
        "t_c_s": {"min": float(np.min(tcs)), "max": float(np.max(tcs))},
        "critere": "dCPA < 5 NM, t_c dans [240,420] s, |tCPA - t_c| < 10 s",
    }


# =============================================================================
#  C. Montee en charge BlueSky (repetee)
# =============================================================================
def bluesky_scaling(reps=5, counts=(5, 10, 25, 50, 100, 200)):
    import bluesky_runtime as bsk
    rng = np.random.default_rng(4242)
    out = []
    bsk.bs()                                   # init (hors mesure)
    for n in counts:
        facteurs = []
        for _rep in range(reps):
            bsk.reset()
            for k in range(n):
                b = rng.uniform(0, 360)
                d = rng.uniform(5, 60)
                lat = 49.25 + (d * math.cos(math.radians(b))) / 60.0
                lon = 4.05 + (d * math.sin(math.radians(b))) / (60.0 * 0.653)
                bsk.create(f"TST{k:03d}", "A320", lat, lon,
                           rng.uniform(0, 360), 30000 + 1000 * (k % 10),
                           rng.uniform(220, 300))
            t0 = time.perf_counter()
            bsk.advance(10.0)
            wall = time.perf_counter() - t0
            facteurs.append(10.0 / wall)
        lo, hi = bootstrap_ci_mean(facteurs)
        out.append({"avions": n, "reps": reps,
                    "facteur_temps_reel_moyen": float(np.mean(facteurs)),
                    "ic95": [lo, hi],
                    "facteurs": [round(f, 1) for f in facteurs]})
        print(f"  N={n:3d} : x{np.mean(facteurs):.1f} temps reel "
              f"IC95=[{lo:.1f}, {hi:.1f}]", flush=True)
    bsk.reset()
    return out


# =============================================================================
#  D. Latence parseur de reference (percentiles numpy)
# =============================================================================
def parser_latency():
    from atc_ai import local_interpret
    phrases = [
        "air france one two three four descend flight level one zero zero",
        "speedbird five seven turn right heading two seven zero",
        "ryanair niner climb flight level two four zero reduce speed two five zero",
        "AFR1234 proceed direct CROSS",
        "DLH88 descendez niveau 1 8 0 reduisez vitesse 2 4 0",
        "easyjet two one turn left heading 050 climb FL310",
        "KLM405 maintain flight level two eight zero",
        "BAW57 expedite descend flight level one two zero",
    ]
    local_interpret(phrases[0])                       # echauffement
    lats = []
    for _ in range(50):
        for ph in phrases:
            t0 = time.perf_counter()
            local_interpret(ph)
            lats.append(time.perf_counter() - t0)
    return latency_summary(lats)


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results = {}

    print("[sim_bench] A. CPA multi-graines (5 x 200 000)...", flush=True)
    t0 = time.time()
    camp = [cpa_campaign(seed, 200_000) for seed in (42, 43, 44, 45, 46)]
    results["cpa_multi_graines"] = {
        "campagnes": camp,
        "total_geometries": sum(c["n"] for c in camp),
        "total_desaccords": sum(c["n_desaccords"] for c in camp),
        "pire_erreur_dcpa_nm": max(c["erreur_dcpa_nm"]["max"] for c in camp
                                   if c["erreur_dcpa_nm"]["max"] is not None),
        "grille": {"dt_s": GRID_DT, "horizon_s": GRID_HORIZON},
        "duree_s": round(time.time() - t0, 1)}
    print(f"    {results['cpa_multi_graines']['total_geometries']} geometries, "
          f"{results['cpa_multi_graines']['total_desaccords']} desaccords, "
          f"pire erreur dCPA = {results['cpa_multi_graines']['pire_erreur_dcpa_nm']:.2e} NM")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)

    print("[sim_bench] B. garantie de conflit (2 000 tirages)...", flush=True)
    results["conflit_garanti"] = conflict_guarantee(2000)
    print(f"    taux de garantie = {results['conflit_garanti']['taux_garantie']:.1%}, "
          f"dCPA max = {results['conflit_garanti']['dcpa_nm']['max']:.3f} NM")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)

    print("[sim_bench] D. latence parseur de reference...", flush=True)
    results["latence_parseur"] = parser_latency()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)

    print("[sim_bench] C. montee en charge BlueSky (5 reps)...", flush=True)
    results["bluesky_scaling"] = bluesky_scaling()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    print(f"[OK] sim_bench -> {OUT}")


if __name__ == "__main__":
    main()
