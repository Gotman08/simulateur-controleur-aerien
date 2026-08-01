"""
Outils statistiques du banc de benchmark
========================================
Rigueur scientifique minimale commune a tous les benchs :
  - IC 95 % bootstrap percentile (B=10 000, graine fixee) pour toute moyenne ;
  - IC de Wilson pour les proportions (exactitude, taux de rejet) ;
  - test de McNemar exact (binomial) pour comparer deux modeles apparies
    sur le meme corpus (issues binaires correct/incorrect) ;
  - bootstrap apparie de la difference de moyennes (WER modele A vs B).

Toutes les fonctions sont pures et seedees : memes entrees -> memes IC.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

BOOT_B = 10_000
BOOT_SEED = 123


def bootstrap_ci_mean(values, b=BOOT_B, seed=BOOT_SEED, alpha=0.05):
    """IC percentile bootstrap de la moyenne. -> (lo, hi) ; (nan, nan) si vide."""
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        return float("nan"), float("nan")
    if arr.size == 1:
        return float(arr[0]), float(arr[0])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(b, arr.size))
    means = arr[idx].mean(axis=1)
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def wilson_ci(k, n, alpha=0.05):
    """IC de Wilson pour une proportion k/n. -> (lo, hi) ; (nan, nan) si n=0."""
    if n == 0:
        return float("nan"), float("nan")
    z = sps.norm.ppf(1 - alpha / 2)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def mcnemar_exact(a_correct, b_correct):
    """Test de McNemar exact (binomial) entre deux modeles apparies.

    a_correct, b_correct : listes de booleens de MEME longueur (item i = le
    modele a-t-il ete correct sur le cas i du corpus).
    -> {n01, n10, p_value} ou n01 = A correct/B faux, n10 = A faux/B correct.
    """
    a = list(map(bool, a_correct))
    b = list(map(bool, b_correct))
    if len(a) != len(b):
        raise ValueError("corpus apparies de tailles differentes")
    n01 = sum(1 for x, y in zip(a, b) if x and not y)
    n10 = sum(1 for x, y in zip(a, b) if not x and y)
    n = n01 + n10
    if n == 0:
        p = 1.0
    else:
        p = float(sps.binomtest(min(n01, n10), n, 0.5).pvalue)
    return {"n01": n01, "n10": n10, "p_value": p}


def holm_correction(pvalues):
    """Correction de Holm-Bonferroni (famille de tests) : liste de p bruts ->
    liste de p ajustes (meme ordre). Monotone et bornee a 1."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvalues[i])
        adj[i] = min(1.0, running)
    return adj


def paired_bootstrap_diff(values_a, values_b, b=BOOT_B, seed=BOOT_SEED, alpha=0.05):
    """IC bootstrap de mean(A) - mean(B) sur echantillons APPARIES (meme corpus).

    -> {diff, lo, hi, significatif} (significatif = 0 hors de l'IC).
    """
    a = np.asarray(list(values_a), dtype=float)
    v = np.asarray(list(values_b), dtype=float)
    if a.size != v.size or a.size == 0:
        raise ValueError("echantillons apparies invalides")
    d = a - v
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(b, d.size))
    diffs = d[idx].mean(axis=1)
    lo, hi = np.percentile(diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"diff": float(d.mean()), "lo": float(lo), "hi": float(hi),
            "significatif": bool(lo > 0 or hi < 0)}


def latency_summary(seconds):
    """Resume de latences (s) : moyenne, mediane, p95 par interpolation lineaire
    (numpy percentile, correct meme pour petits n - contrairement a un index
    approximatif), min, max, n, et IC bootstrap de la moyenne."""
    arr = np.asarray(list(seconds), dtype=float)
    if arr.size == 0:
        return {"n": 0}
    lo, hi = bootstrap_ci_mean(arr)
    return {
        "n": int(arr.size),
        "moyenne_s": float(arr.mean()),
        "mediane_s": float(np.median(arr)),
        "p95_s": float(np.percentile(arr, 95)),
        "min_s": float(arr.min()),
        "max_s": float(arr.max()),
        "ic95_moyenne_s": [lo, hi],
    }
