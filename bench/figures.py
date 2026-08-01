"""
Generation des figures du banc de benchmark (article + docs)
============================================================
Lit bench/results/*.json et produit bench/figures/*.png (dpi 180).
Robuste aux resultats partiels : chaque figure n'est generee que si son
fichier de resultats existe. Palette adaptee au daltonisme (Okabe-Ito).

Execution :  bench\\bench-env\\Scripts\\python.exe bench\\figures.py
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

# palette Okabe-Ito
C = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"]

plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3,
                     "figure.dpi": 100, "savefig.dpi": 180,
                     "axes.spines.top": False, "axes.spines.right": False})


def load(name):
    path = os.path.join(RES, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)
    print(f"  [fig] {name}")


# =============================================================================
#  STT
# =============================================================================
def fig_stt():
    d = load("stt_bench.json")
    if not d or "systems" not in d:
        return
    extra = load("stt_bench_romeo.json")
    if extra:
        for k, v in extra.get("systems", {}).items():
            d["systems"].setdefault(k, v)
    systems = list(d["systems"].keys())
    corpora = list(d["corpora"].keys())

    # --- WER par modele x corpus x condition --------------------------------
    fig, axes = plt.subplots(1, len(corpora), figsize=(5.2 * len(corpora), 3.8),
                             sharey=True)
    axes = np.atleast_1d(axes)
    width = 0.38
    for ax, ckey in zip(axes, corpora):
        xs = np.arange(len(systems))
        for k, cond in enumerate(("brut", "vhf_bandpass")):
            vals, err_lo, err_hi = [], [], []
            for s in systems:
                r = d["systems"][s].get(ckey, {}).get(cond)
                if not r:
                    vals.append(np.nan)
                    err_lo.append(0)
                    err_hi.append(0)
                    continue
                m = 100 * r["wer_moyen_extrait"]
                lo, hi = r["ic95_wer_moyen"]
                vals.append(m)
                err_lo.append(m - 100 * lo)
                err_hi.append(100 * hi - m)
            ax.bar(xs + (k - 0.5) * width, vals, width,
                   yerr=[err_lo, err_hi], capsize=3,
                   label="brut" if k == 0 else "passe-bande VHF",
                   color=C[k], edgecolor="white")
            # WER corpus en marqueur losange
            corp = [100 * d["systems"][s].get(ckey, {}).get(cond, {}).get("wer_corpus", np.nan)
                    for s in systems]
            ax.scatter(xs + (k - 0.5) * width, corp, marker="D", s=18, zorder=3,
                       color="black", label="WER corpus" if (k == 0 and ckey == corpora[0]) else None)
        ax.set_xticks(xs)
        ax.set_xticklabels(systems, rotation=20, ha="right")
        ax.set_title(f"{ckey} (n={d['corpora'][ckey]['n']})")
    axes[0].set_ylabel("WER moyen par extrait (%) - IC 95 % bootstrap")
    axes[0].legend(fontsize=8)
    fig.suptitle("STT : WER par modele, corpus ATC reels, avec/sans passe-bande VHF", y=1.02)
    save(fig, "fig_stt_wer.png")

    # --- RTF ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    xs = np.arange(len(systems))
    for k, ckey in enumerate(corpora):
        rtfs = [d["systems"][s].get(ckey, {}).get("vhf_bandpass", {}).get("rtf", np.nan)
                for s in systems]
        ax.bar(xs + (k - 0.5) * 0.38, rtfs, 0.38, label=ckey, color=C[k + 2],
               edgecolor="white")
    ax.axhline(1.0, color="red", lw=1, ls="--", label="temps reel (RTF=1)")
    ax.set_yscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels(systems, rotation=20, ha="right")
    ax.set_ylabel("RTF (traitement / duree audio, log)")
    ax.set_title(f"STT : facteur temps reel - {d['protocole'].get('gpu', '?')}")
    ax.legend(fontsize=8)
    save(fig, "fig_stt_rtf.png")


# =============================================================================
#  LLM
# =============================================================================
def _sysname(s):
    if s == "mistral-7b-atc-romeo":
        return "Mistral-7B\nROMEO bf16"
    return (s.replace("-instruct", "").replace("-q4_k_m", "")
            .replace("qwen2.5", "Qwen2.5").replace("llama-3.2", "Llama-3.2")
            .replace("mistral-7b", "Mistral-7B").replace("rules-parser", "Parseur regles"))


def fig_llm():
    d = load("llm_bench.json")
    if not d or "systems" not in d:
        return
    extra = load("llm_bench_romeo.json")
    if extra:
        for k, v in extra.get("systems", {}).items():
            if k != "rules-parser":
                d["systems"].setdefault(k, v)
    systems = list(d["systems"].keys())
    labels = [_sysname(s) for s in systems]

    # --- exactitude globale + par strate ---------------------------------------
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    xs = np.arange(len(systems))
    strates = ["in_grammar", "hors_grammaire"]
    width = 0.27
    g = [100 * d["systems"][s]["exactitude"]["globale"] for s in systems]
    glo = [100 * d["systems"][s]["exactitude"]["ic95"][0] for s in systems]
    ghi = [100 * d["systems"][s]["exactitude"]["ic95"][1] for s in systems]
    ax.bar(xs - width, g, width, yerr=[np.array(g) - glo, np.array(ghi) - g],
           capsize=3, label=f"globale (n={d['n_cas']})", color=C[0], edgecolor="white")
    for k, strate in enumerate(strates):
        vals, elo, ehi = [], [], []
        for s in systems:
            st = d["systems"][s]["par_strate"].get(strate)
            if not st:
                vals.append(np.nan)
                elo.append(0)
                ehi.append(0)
                continue
            v = 100 * st["exactitude"]
            vals.append(v)
            elo.append(v - 100 * st["ic95"][0])
            ehi.append(100 * st["ic95"][1] - v)
        lbl = "phraseologie standard" if strate == "in_grammar" else "hors grammaire / adversarial"
        ax.bar(xs + k * width, vals, width, yerr=[elo, ehi], capsize=3,
               label=lbl, color=C[k + 1], edgecolor="white")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Exactitude TrafScript exacte (%) - IC 95 % Wilson")
    ax.set_ylim(0, 118)
    ax.set_title("Extraction d'intention : exactitude par systeme (chaine de production complete)")
    ax.legend(fontsize=8, loc="upper center", ncol=3, framealpha=0.9)
    save(fig, "fig_llm_exactitude.png")

    # --- heatmap categories -------------------------------------------------------
    cats = sorted({c for s in systems for c in d["systems"][s]["par_categorie"]})
    M = np.full((len(cats), len(systems)), np.nan)
    for j, s in enumerate(systems):
        for i, c in enumerate(cats):
            v = d["systems"][s]["par_categorie"].get(c)
            if v:
                M[i, j] = 100 * v["exactitude"]
    fig, ax = plt.subplots(figsize=(1.1 * len(systems) + 3, 0.34 * len(cats) + 1.6))
    im = ax.imshow(M, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(systems)))
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_yticks(range(len(cats)))
    ax.set_yticklabels(cats)
    for i in range(len(cats)):
        for j in range(len(systems)):
            if not np.isnan(M[i, j]):
                ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center", fontsize=7,
                        color="black")
    ax.grid(False)
    fig.colorbar(im, label="exactitude (%)")
    ax.set_title("Exactitude par categorie de clairance")
    save(fig, "fig_llm_categories.png")

    # --- latence + debit -----------------------------------------------------------
    llms = [s for s in systems if s != "rules-parser"]
    if llms:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.4))
        xs = np.arange(len(llms))
        means = [d["systems"][s]["latence"].get("moyenne_s", np.nan) for s in llms]
        p95s = [d["systems"][s]["latence"].get("p95_s", np.nan) for s in llms]
        ax1.bar(xs - 0.19, means, 0.38, label="moyenne", color=C[0], edgecolor="white")
        ax1.bar(xs + 0.19, p95s, 0.38, label="p95", color=C[1], edgecolor="white")
        ax1.set_xticks(xs)
        ax1.set_xticklabels([_sysname(s) for s in llms], rotation=15, ha="right")
        ax1.set_ylabel("Latence interpretation (s)")
        ax1.set_title("Latence par clairance")
        ax1.legend(fontsize=8)
        tps = [d["systems"][s].get("tokens", {}).get("tokens_generes_par_s_moyen", np.nan)
               for s in llms]
        ax2.bar(xs, tps, 0.5, color=C[2], edgecolor="white")
        ax2.set_xticks(xs)
        ax2.set_xticklabels([_sysname(s) for s in llms], rotation=15, ha="right")
        ax2.set_ylabel("Tokens generes / s")
        ax2.set_title("Debit de generation")
        save(fig, "fig_llm_latence.png")

    # --- scenarios ---------------------------------------------------------------------
    have = [s for s in systems if "scenarios" in d["systems"][s]]
    if have:
        fig, ax = plt.subplots(figsize=(6.8, 3.4))
        xs = np.arange(len(have))
        vals = [100 * d["systems"][s]["scenarios"]["taux_contraintes"] for s in have]
        los = [100 * d["systems"][s]["scenarios"]["ic95_taux"][0] for s in have]
        his = [100 * d["systems"][s]["scenarios"]["ic95_taux"][1] for s in have]
        ax.bar(xs, vals, 0.5, yerr=[np.array(vals) - los, np.array(his) - np.array(vals)],
               capsize=3, color=C[3], edgecolor="white")
        for x, s in zip(xs, have):
            sc = d["systems"][s]["scenarios"]
            ax.text(x, 3, f"{sc['descriptions_conformes']}/{sc['n_descriptions']}\nconformes",
                    ha="center", fontsize=7)
        ax.set_xticks(xs)
        ax.set_xticklabels([_sysname(s) for s in have], rotation=15, ha="right")
        ax.set_ylabel("Contraintes respectees (%) - IC 95 % Wilson")
        ax.set_ylim(0, 105)
        ax.set_title("Generation de situations : conformite aux contraintes (20 descriptions)")
        save(fig, "fig_llm_scenarios.png")


# =============================================================================
#  TTS
# =============================================================================
def fig_tts():
    d = load("tts_bench.json")
    if not d or "engines" not in d:
        return
    extra = load("tts_bench_romeo.json")
    if extra:
        for k, v in extra.get("engines", {}).items():
            if k.startswith("xtts") and "erreur" not in v:
                d["engines"].setdefault(k, v)
    engines = [(k, v) for k, v in d["engines"].items() if "erreur" not in v]
    if not engines:
        return
    names = [k for k, _ in engines]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.6))
    xs = np.arange(len(engines))
    rtf = [v["rtf_moyen"] for _, v in engines]
    rlo = [v["ic95_rtf"][0] for _, v in engines]
    rhi = [v["ic95_rtf"][1] for _, v in engines]
    ax1.bar(xs, rtf, 0.5, yerr=[np.array(rtf) - rlo, np.array(rhi) - np.array(rtf)],
            capsize=3, color=C[0], edgecolor="white")
    ax1.axhline(1.0, color="red", lw=1, ls="--", label="temps reel")
    ax1.set_xticks(xs)
    ax1.set_xticklabels(names, rotation=25, ha="right", fontsize=7)
    ax1.set_ylabel("RTF synthese")
    ax1.set_title("Cout de synthese (RTF, IC 95 %)")
    ax1.legend(fontsize=8)
    for k, cond, lab in ((0, "wer_aller_retour_propre", "propre"),
                         (1, "wer_aller_retour_vhf", "apres VHF")):
        vals = [100 * v[cond] for _, v in engines]
        ic = [v["ic95_wer_propre" if k == 0 else "ic95_wer_vhf"] for _, v in engines]
        elo = [val - 100 * c[0] for val, c in zip(vals, ic)]
        ehi = [100 * c[1] - val for val, c in zip(vals, ic)]
        ax2.bar(xs + (k - 0.5) * 0.38, vals, 0.38, yerr=[elo, ehi], capsize=3,
                label=lab, color=C[k + 1], edgecolor="white")
    ax2.set_xticks(xs)
    ax2.set_xticklabels(names, rotation=25, ha="right", fontsize=7)
    ax2.set_ylabel("WER aller-retour (%)")
    ax2.set_title(f"Intelligibilite objective (juge : {d.get('juge', '?')})")
    ax2.legend(fontsize=8)
    save(fig, "fig_tts.png")


# =============================================================================
#  E2E
# =============================================================================
def fig_e2e():
    d = load("e2e_bench.json")
    if not d:
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.6),
                                   gridspec_kw={"width_ratios": [1.6, 1]})
    # reussite : toutes les conditions mesurees disponibles
    conds = [(d["voix"], "SAPI\npile locale", C[0]),
             (d["texte_temoin"], "texte temoin\n(sans STT)", C[2])]
    romeo = load("e2e_bench_romeo.json")
    if romeo:
        conds.insert(1, (romeo["voix"], "SAPI\npile ROMEO", C[5]))
    human = load("human_e2e.json")
    if human:
        for spk, per in human.get("par_locuteur", {}).items():
            if per.get("micro"):
                conds.append((per["micro"], f"humain ({spk})\nmicro brut", C[1]))
            if per.get("radio"):
                conds.append((per["radio"], f"humain ({spk})\ncanal radio", C[3]))
    xs = np.arange(len(conds))
    vals = [100 * c[0]["reussite"] for c in conds]
    los = [100 * c[0]["ic95"][0] for c in conds]
    his = [100 * c[0]["ic95"][1] for c in conds]
    ax1.bar(xs, vals, 0.55, yerr=[np.array(vals) - los, np.array(his) - np.array(vals)],
            capsize=4, color=[c[2] for c in conds], edgecolor="white")
    for x, c in zip(xs, conds):
        ax1.text(x, 5, f"{c[0]['k']}/{c[0]['n']}", ha="center", fontsize=8,
                 color="white", fontweight="bold")
    ax1.set_xticks(xs)
    ax1.set_xticklabels([c[1] for c in conds], fontsize=7.5)
    ax1.set_ylabel("Clairances correctement executees (%)")
    ax1.set_ylim(0, 105)
    ax1.set_title("Reussite E2E par condition - IC 95 % Wilson")
    # latences par etage : pile locale et, si mesuree, pile ROMEO (tunnel inclus)
    stages = [("stt", "STT"), ("llm", "LLM"), ("tts", "TTS")]
    piles = [("locale", d)] + ([("ROMEO", romeo)] if romeo else [])
    for xi, (_plbl, dd) in enumerate(piles):
        bottom = 0.0
        for k, (s, lbl) in enumerate(stages):
            m = dd["latences"][s]["moyenne_s"]
            ax2.bar([xi], [m], 0.5, bottom=[bottom], color=C[k], edgecolor="white",
                    label=f"{lbl}" if xi == 0 else None)
            bottom += m
        tot = dd["latences"]["totale"]
        ax2.errorbar([xi], [bottom], yerr=[[0], [max(0.0, tot["p95_s"] - bottom)]],
                     fmt="none", ecolor="black", capsize=5,
                     label="p95 total" if xi == 0 else None)
        ax2.text(xi, bottom + 0.25, f"{tot['moyenne_s']:.1f} s", ha="center", fontsize=8)
    ax2.set_xticks(range(len(piles)))
    ax2.set_xticklabels([f"pile {p}" for p, _ in piles], fontsize=8)
    ax2.set_xlim(-0.7, len(piles) - 0.3 + 0.9)
    ax2.set_ylabel("Latence (s)")
    ax2.set_title("Latence vocale par etage")
    ax2.legend(fontsize=8, loc="center right")
    fig.suptitle(f"Boucle vocale complete - 25 clairances, canal SNR {d['config']['snr_db']} dB "
                 f"(graine commune a toutes les conditions)", y=1.03, fontsize=9)
    save(fig, "fig_e2e.png")


# =============================================================================
#  Simulateur
# =============================================================================
def fig_sim():
    d = load("sim_bench.json")
    if not d:
        return
    if "bluesky_scaling" in d:
        rows = d["bluesky_scaling"]
        fig, ax = plt.subplots(figsize=(6.2, 3.4))
        ns = [r["avions"] for r in rows]
        ms = [r["facteur_temps_reel_moyen"] for r in rows]
        lo = [r["ic95"][0] for r in rows]
        hi = [r["ic95"][1] for r in rows]
        ax.plot(ns, ms, "o-", color=C[0])
        ax.fill_between(ns, lo, hi, alpha=0.25, color=C[0], label="IC 95 % (5 reps)")
        ax.axhline(1.0, color="red", lw=1, ls="--", label="temps reel")
        ax.set_xlabel("Nombre d'avions")
        ax.set_ylabel("Facteur temps reel (x)")
        ax.set_title("BlueSky headless : montee en charge (10 s simulees)")
        ax.legend(fontsize=8)
        save(fig, "fig_sim_scaling.png")
    if "cpa_multi_graines" in d:
        camp = d["cpa_multi_graines"]["campagnes"]
        fig, ax = plt.subplots(figsize=(6.2, 3.2))
        seeds = [str(c["seed"]) for c in camp]
        worst = [c["erreur_dcpa_nm"]["max"] for c in camp]
        p99 = [c["erreur_dcpa_nm"]["p99"] for c in camp]
        xs = np.arange(len(seeds))
        ax.bar(xs - 0.19, worst, 0.38, label="max", color=C[3], edgecolor="white")
        ax.bar(xs + 0.19, p99, 0.38, label="p99", color=C[0], edgecolor="white")
        ax.set_yscale("log")
        ax.axhline(0.1, color="gray", ls=":", lw=1, label="0,1 NM (2 % de la norme)")
        ax.set_xticks(xs)
        ax.set_xticklabels([f"graine {s}" for s in seeds])
        ax.set_ylabel("Erreur dCPA vs grille fine (NM, log)")
        ax.set_title(f"Prediction CPA vs verite numerique - "
                     f"{d['cpa_multi_graines']['total_geometries']:,} geometries, "
                     f"{d['cpa_multi_graines']['total_desaccords']} desaccords".replace(",", " "))
        ax.legend(fontsize=8)
        save(fig, "fig_cpa_multiseed.png")
    if "conflit_garanti" in d:
        g = d["conflit_garanti"]
        fig, ax = plt.subplots(figsize=(5.6, 3.2))
        ax.bar(["dCPA max", "dCPA p99", "dCPA moyen"],
               [g["dcpa_nm"]["max"], g["dcpa_nm"]["p99"], g["dcpa_nm"]["moyenne"]],
               color=[C[3], C[1], C[0]], edgecolor="white")
        ax.axhline(5.0, color="red", ls="--", lw=1, label="norme de separation (5 NM)")
        ax.set_ylabel("dCPA analytique (NM)")
        ax.set_title(f"Conflits generes par construction : garantie {g['taux_garantie']:.1%} "
                     f"(n={g['n']})")
        ax.legend(fontsize=8)
        save(fig, "fig_conflit_garanti.png")


if __name__ == "__main__":
    print("[figures] generation...")
    fig_stt()
    fig_llm()
    fig_tts()
    fig_e2e()
    fig_sim()
    print("[OK] figures ->", FIG)
