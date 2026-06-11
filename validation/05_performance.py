# -*- coding: utf-8 -*-
"""
Volet 5 - Etude de performance : latences IA (local vs ROMEO) et montee en
charge du simulateur BlueSky.

  A. IA locale (hors-ligne)  : latence de local_interpret / local_scenario.
  B. IA ROMEO (tunnel SSH)   : latence /interpret, /asr (+RTF), /tts (+RTF),
                               /scenario. Mesure uniquement si le tunnel est
                               ouvert (localhost:8765/8766), sinon ignore.
  C. Simulateur BlueSky      : temps mur pour avancer 10 s de simulation avec
                               N avions (N = 5..200), facteur temps reel.

Sortie : validation/results_perf.json + docs/assets/validation/fig_perf_*.png
Relancer :  src\\bluesky-env\\Scripts\\python.exe validation\\05_performance.py
"""
import io
import json
import math
import os
import statistics as st
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
FIGS = os.path.join(ROOT, "docs", "assets", "validation")
os.makedirs(FIGS, exist_ok=True)

RESULTS = {}

PHRASES = [
    "air france one two three four descend flight level one zero zero",
    "speedbird five seven turn right heading two seven zero",
    "ryanair niner climb flight level two four zero reduce speed two five zero",
    "AFR1234 proceed direct CROSS",
    "DLH88 descendez niveau 1 8 0 reduisez vitesse 2 4 0",
    "easyjet two one turn left heading 050 climb FL310",
    "KLM405 maintain flight level two eight zero",
    "BAW57 expedite descend flight level one two zero",
]
DESCRIPTIONS = [
    "three A320 from the north at FL300 heading 180, 8 miles apart",
    "two B738 from the west at FL240 and one A319 from the south at FL120",
    "trois A320 venant du nord au niveau 320 espaces de 9 milles",
    "one B744 from the east at FL340",
]


def bench(fn, args_list, reps=1):
    """Applique fn a chaque arg (reps fois), renvoie les latences en secondes."""
    out = []
    for a in args_list:
        for _ in range(reps):
            t0 = time.perf_counter()
            fn(a)
            out.append(time.perf_counter() - t0)
    return out


def stats_ms(lat):
    lat_ms = sorted(x * 1000 for x in lat)
    return {"n": len(lat_ms),
            "moyenne_ms": round(st.mean(lat_ms), 2),
            "mediane_ms": round(st.median(lat_ms), 2),
            "p95_ms": round(lat_ms[max(0, int(0.95 * len(lat_ms)) - 1)], 2),
            "max_ms": round(lat_ms[-1], 2)}


# =============================================================================
#  A. IA locale
# =============================================================================
def bench_local():
    import atc_ai
    lat_i = bench(atc_ai.local_interpret, PHRASES, reps=25)
    lat_s = bench(atc_ai.local_scenario, DESCRIPTIONS, reps=25)
    RESULTS["local"] = {"interpret": stats_ms(lat_i), "scenario": stats_ms(lat_s)}
    print(f"[A] local_interpret : {RESULTS['local']['interpret']}")
    print(f"[A] local_scenario  : {RESULTS['local']['scenario']}")


# =============================================================================
#  B. IA ROMEO (si le tunnel est ouvert)
# =============================================================================
def _wav_duration(path):
    import soundfile as sf
    d, sr = sf.read(path)
    return len(d) / sr


def bench_romeo():
    import requests
    try:
        requests.get("http://localhost:8765/health", timeout=3).raise_for_status()
    except Exception:
        print("[B] tunnel ROMEO ferme -> volet ROMEO ignore")
        RESULTS["romeo"] = None
        return

    # /interpret (Mistral+RAG) - 1 appel de chauffe puis mesure
    requests.post("http://localhost:8765/interpret", json={"text": PHRASES[0]}, timeout=300)
    lat_i = []
    for p in PHRASES:
        t0 = time.perf_counter()
        requests.post("http://localhost:8765/interpret", json={"text": p}, timeout=300)
        lat_i.append(time.perf_counter() - t0)

    # /asr : wavs du projet + RTF (latence / duree audio)
    wavs = [os.path.join(ROOT, "audio", w) for w in
            ("exchange_1.wav", "exchange_2.wav", "exchange_3.wav")]
    wavs = [w for w in wavs if os.path.isfile(w)]
    lat_a, rtf_a = [], []
    for w in wavs:
        dur = _wav_duration(w)
        with open(w, "rb") as f:
            data = f.read()
        t0 = time.perf_counter()
        requests.post("http://localhost:8765/asr",
                      files={"file": ("u.wav", data, "audio/wav")}, timeout=300)
        dt = time.perf_counter() - t0
        lat_a.append(dt)
        rtf_a.append(dt / dur)

    # /tts : 3 collationnements + RTF (latence / duree audio produite)
    texts = ["descend flight level one eight zero, air france three zero zero",
             "heading two seven zero, speedbird five seven",
             "climb flight level two four zero, ryanair niner"]
    lat_t, rtf_t = [], []
    for txt in texts:
        t0 = time.perf_counter()
        r = requests.post("http://localhost:8766/tts", json={"text": txt, "vhf": True},
                          timeout=300)
        dt = time.perf_counter() - t0
        import soundfile as sf
        d, sr = sf.read(io.BytesIO(r.content))
        lat_t.append(dt)
        rtf_t.append(dt / (len(d) / sr))

    # /scenario (Mistral) : 2 appels
    lat_s = []
    for d in DESCRIPTIONS[:2]:
        t0 = time.perf_counter()
        requests.post("http://localhost:8765/scenario", json={"description": d}, timeout=300)
        lat_s.append(time.perf_counter() - t0)

    RESULTS["romeo"] = {
        "interpret_s": {"n": len(lat_i), "moyenne": round(st.mean(lat_i), 2),
                        "min": round(min(lat_i), 2), "max": round(max(lat_i), 2)},
        "asr_s": {"n": len(lat_a), "moyenne": round(st.mean(lat_a), 2),
                  "rtf_moyen": round(st.mean(rtf_a), 2)},
        "tts_s": {"n": len(lat_t), "moyenne": round(st.mean(lat_t), 2),
                  "rtf_moyen": round(st.mean(rtf_t), 2)},
        "scenario_s": {"n": len(lat_s), "moyenne": round(st.mean(lat_s), 2),
                       "max": round(max(lat_s), 2)},
    }
    print(f"[B] ROMEO : {json.dumps(RESULTS['romeo'], indent=1)}")


# =============================================================================
#  C. Montee en charge BlueSky
# =============================================================================
def bench_sim():
    import bluesky_runtime as bsk
    bsk.bs()
    bsk.reset()
    rows = []
    for n in (5, 10, 25, 50, 100, 200):
        bsk.reset()
        for k in range(n):
            ang = 2 * math.pi * k / n
            bsk.bs().stack.stack(
                f"CRE T{k:03d} A320 {48.6 + 0.9 * math.sin(ang):.4f} "
                f"{3.0 + 1.4 * math.cos(ang):.4f} {int(math.degrees(ang)) % 360} "
                f"{20000 + (k % 5) * 2000} 250")
        bsk.advance(0.5)                      # stabilisation
        t0 = time.perf_counter()
        simdt = bsk.advance(10.0)             # 10 s de temps simule
        wall = time.perf_counter() - t0
        rt = simdt / wall if wall > 0 else float("inf")
        rows.append({"avions": n, "sim_s": round(simdt, 1), "mur_s": round(wall, 3),
                     "facteur_temps_reel": round(rt, 1)})
        print(f"[C] {n:4d} avions : 10 s simulees en {wall:.3f} s mur "
              f"-> x{rt:.0f} temps reel")
    RESULTS["simulateur"] = rows


# =============================================================================
#  Figures + sauvegarde
# =============================================================================
def make_figures():
    # latences IA : barres log (local vs ROMEO)
    fig, ax = plt.subplots(figsize=(7.2, 4))
    labels, vals, colors = [], [], []
    loc = RESULTS.get("local") or {}
    if loc:
        labels += ["interpret\n(local)", "scenario\n(local)"]
        vals += [loc["interpret"]["moyenne_ms"] / 1000, loc["scenario"]["moyenne_ms"] / 1000]
        colors += ["#38d97f"] * 2
    rom = RESULTS.get("romeo")
    if rom:
        labels += ["interpret\n(ROMEO)", "scenario\n(ROMEO)", "ASR\n(ROMEO)", "TTS\n(ROMEO)"]
        vals += [rom["interpret_s"]["moyenne"], rom["scenario_s"]["moyenne"],
                 rom["asr_s"]["moyenne"], rom["tts_s"]["moyenne"]]
        colors += ["#3fc6d6"] * 4
    ax.bar(labels, vals, color=colors)
    ax.set_yscale("log")
    ax.set_ylabel("latence moyenne (s, echelle log)")
    ax.set_title("Latence des briques IA : repli local vs serveur ROMEO (GH200, tunnel SSH)")
    for i, v in enumerate(vals):
        ax.text(i, v * 1.15, f"{v:.3g} s", ha="center", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig_perf_latences.png"), dpi=130)

    # montee en charge simulateur
    rows = RESULTS.get("simulateur") or []
    if rows:
        fig, ax = plt.subplots(figsize=(7.2, 4))
        ax.plot([r["avions"] for r in rows], [r["facteur_temps_reel"] for r in rows],
                "o-", color="#3fc6d6")
        ax.axhline(1, color="#ff5868", ls="--", label="limite temps réel (x1)")
        ax.set_xlabel("nombre d'avions simulés")
        ax.set_ylabel("facteur temps réel (sim/mur, 10 s simulées)")
        ax.set_title("Montée en charge BlueSky headless (pas de 10 s, CD StateBased active)")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.grid(alpha=0.3, which="both")
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(FIGS, "fig_perf_simulateur.png"), dpi=130)


def main():
    t0 = time.time()
    bench_local()
    bench_romeo()
    bench_sim()
    make_figures()
    RESULTS["duree_totale_s"] = round(time.time() - t0, 1)
    out = os.path.join(_HERE, "results_perf.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=1)
    print(f"[OK] resultats -> {out}")


if __name__ == "__main__":
    main()
