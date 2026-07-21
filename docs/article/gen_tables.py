"""
Generation des tableaux LaTeX et macros numeriques de l'article
===============================================================
Lit bench/results/*.json et produit :
  - docs/article/numbers.tex   (macros \\nXxx utilisees dans la prose)
  - docs/article/tables/*.tex  (tableaux booktabs)

AUCUN chiffre de l'article n'est saisi a la main : ce script est la seule
source. Valeur manquante (bench non execute) -> macro '??' et tableau
placeholder, pour que l'article compile toujours.

Execution : python docs/article/gen_tables.py   (stdlib uniquement)
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(ROOT, "bench", "results")
TABLES = os.path.join(HERE, "tables")
os.makedirs(TABLES, exist_ok=True)

MACROS = {}


def load(name):
    path = os.path.join(RES, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fr(x, nd=1):
    """Format francais : virgule decimale, insecables pour milliers."""
    if x is None:
        return "??"
    s = f"{x:,.{nd}f}".replace(",", " ").replace(".", ",")
    return s


def pct(x, nd=1):
    return "??" if x is None else fr(100 * x, nd) + "\\,\\%"


def secs(x, nd=1):
    return "??" if x is None else fr(x, nd) + "\\,s"


def macro(name, value):
    MACROS[name] = value


def sysname(s):
    return (s.replace("-instruct", "").replace("-q4_k_m", "")
            .replace("qwen2.5", "Qwen2.5").replace("llama-3.2", "Llama-3.2")
            .replace("mistral-7b", "Mistral-7B").replace("-v0.3", "")
            .replace("rules-parser", "Parseur à règles"))


def write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [tex] {os.path.relpath(path, HERE)}")


def placeholder(path, caption, label):
    write(path, "\\begin{table}[t]\\centering\\small\n"
                f"\\caption{{{caption} (bench non exécuté)}}\\label{{{label}}}\n"
                "\\begin{tabular}{l}\\toprule --- \\\\ \\bottomrule\\end{tabular}\n"
                "\\end{table}\n")


# =============================================================================
#  sim_bench
# =============================================================================
def gen_sim():
    d = load("sim_bench.json")
    if not d:
        for m in ("nCPAGeoms", "nCPADesaccords", "nCPAErrMax", "nConflitGarantie",
                  "nConflitDcpaMax", "nConflitDcpaMoy", "nConflitTerrMax",
                  "nScalingCinq", "nScalingDeuxCents"):
            macro(m, "??")
        return
    c = d["cpa_multi_graines"]
    macro("nCPAGeoms", fr(c["total_geometries"], 0))
    macro("nCPADesaccords", str(c["total_desaccords"]))
    macro("nCPAErrMax", fr(c["pire_erreur_dcpa_nm"], 2))
    g = d["conflit_garanti"]
    macro("nConflitGarantie", pct(g["taux_garantie"], 1))
    macro("nConflitDcpaMax", fr(g["dcpa_nm"]["max"], 3))
    macro("nConflitDcpaMoy", fr(g["dcpa_nm"]["moyenne"], 3))
    macro("nConflitTerrMax", fr(g["abs_err_tcpa_vs_tc_s"]["max"], 1))
    sc = {r["avions"]: r for r in d.get("bluesky_scaling", [])}
    macro("nScalingCinq", fr(sc.get(5, {}).get("facteur_temps_reel_moyen"), 0))
    macro("nScalingDeuxCents", fr(sc.get(200, {}).get("facteur_temps_reel_moyen"), 0))


# =============================================================================
#  stt_bench
# =============================================================================
def gen_stt():
    d = load("stt_bench.json")
    path = os.path.join(TABLES, "tab_stt.tex")
    if not d or "systems" not in d:
        for m in ("nWERVanillaAtcoVhf", "nWERLoraAtcoVhf", "nWERGainRel",
                  "nWERLoraUwbVhf"):
            macro(m, "??")
        placeholder(path, "STT", "tab:stt")
        return
    s = d["systems"]

    def wer(sy, ck, cond):
        return s.get(sy, {}).get(ck, {}).get(cond, {}).get("wer_corpus")

    v = wer("hf-small", "atco2", "vhf_bandpass")
    lo_ = wer("hf-small-lora", "atco2", "vhf_bandpass")
    macro("nWERVanillaAtcoVhf", pct(v))
    macro("nWERLoraAtcoVhf", pct(lo_))
    macro("nWERGainRel", pct((v - lo_) / v, 0) if (v and lo_) else "??")
    macro("nWERLoraUwbVhf", pct(wer("hf-small-lora", "uwb_atcc", "vhf_bandpass")))

    corpora = list(d["corpora"].keys())
    lines = [
        "\\begin{table}[t]\\centering\\small",
        "\\caption{STT : WER corpus (\\%) et RTF par système, corpus VHF réels, "
        "sans/avec passe-bande VHF d'inférence. Normalisation du protocole "
        "historique du projet ; décodage greedy.}",
        "\\label{tab:stt}",
        "\\begin{tabular}{l" + "rrr" * len(corpora) + "}",
        "\\toprule",
        " & " + " & ".join(
            f"\\multicolumn{{3}}{{c}}{{{ck.replace('_', chr(92) + '_')} "
            f"(n={d['corpora'][ck]['n']})}}"
            for ck in corpora) + " \\\\",
        " & " + " & ".join("brut & VHF & RTF" for _ in corpora) + " \\\\",
        "\\midrule",
    ]
    for sy in s:
        row = [sysname(sy)]
        for ck in corpora:
            b = wer(sy, ck, "brut")
            vv = wer(sy, ck, "vhf_bandpass")
            rtf = s.get(sy, {}).get(ck, {}).get("vhf_bandpass", {}).get("rtf")
            row += [fr(100 * b, 1) if b is not None else "--",
                    fr(100 * vv, 1) if vv is not None else "--",
                    fr(rtf, 3) if rtf is not None else "--"]
        lines.append(" & ".join(row) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    write(path, "\n".join(lines) + "\n")


# =============================================================================
#  llm_bench
# =============================================================================
def gen_llm():
    d = load("llm_bench.json")
    path = os.path.join(TABLES, "tab_llm.tex")
    mpath = os.path.join(TABLES, "tab_mcnemar.tex")
    if not d or "systems" not in d:
        for m in ("nLLMBestName", "nLLMBestAcc", "nLLMWorstName", "nLLMWorstAcc",
                  "nParserInGrammar", "nParserHorsGram", "nLLMSweetName",
                  "nLLMSweetAcc", "nLLMSweetLat", "nScenParser", "nScenBest"):
            macro(m, "??")
        placeholder(path, "LLM", "tab:llm")
        placeholder(mpath, "McNemar", "tab:mcnemar")
        return
    s = d["systems"]
    llms = {k: v for k, v in s.items() if k != "rules-parser"}
    best = max(llms, key=lambda k: llms[k]["exactitude"]["globale"])
    worst = min(llms, key=lambda k: llms[k]["exactitude"]["globale"])
    macro("nLLMBestName", sysname(best))
    macro("nLLMBestAcc", pct(llms[best]["exactitude"]["globale"]))
    macro("nLLMWorstName", sysname(worst))
    macro("nLLMWorstAcc", pct(llms[worst]["exactitude"]["globale"]))
    p = s["rules-parser"]["par_strate"]
    macro("nParserInGrammar", pct(p.get("in_grammar", {}).get("exactitude")))
    macro("nParserHorsGram", pct(p.get("hors_grammaire", {}).get("exactitude")))
    # compromis : modele non-best a moins de 5 pts du best et plus rapide, sinon best
    sweet = best
    for k, v in llms.items():
        if k == best:
            continue
        if (llms[best]["exactitude"]["globale"] - v["exactitude"]["globale"] <= 0.05
                and v["latence"].get("moyenne_s", 1e9)
                < llms[best]["latence"].get("moyenne_s", 1e9)):
            if (sweet == best
                    or v["exactitude"]["globale"] > llms[sweet]["exactitude"]["globale"]):
                sweet = k
    macro("nLLMSweetName", sysname(sweet))
    macro("nLLMSweetAcc", pct(llms[sweet]["exactitude"]["globale"]))
    macro("nLLMSweetLat", secs(llms[sweet]["latence"].get("moyenne_s")))
    sc_parser = s["rules-parser"].get("scenarios", {}).get("taux_contraintes")
    macro("nScenParser", pct(sc_parser))
    sc_best = max((v.get("scenarios", {}).get("taux_contraintes", 0.0)
                   for v in llms.values()), default=None)
    macro("nScenBest", pct(sc_best))

    lines = [
        "\\begin{table}[t]\\centering\\small",
        "\\caption{Interprétation : exactitude TrafScript exacte (IC Wilson 95\\,\\%), "
        "par strate, rejet des négatifs de sécurité, JSON strict, latence et débit "
        f"({d['n_cas']} clairances ; chaîne de production complète).}}",
        "\\label{tab:llm}",
        "\\begin{tabular}{lrrrrrrr}",
        "\\toprule",
        "Système & Globale & IC 95\\,\\% & Std. & Hors gr. & Nég. rejetés & JSON & Lat. moy. \\\\",
        "\\midrule",
    ]
    for sy, v in s.items():
        e = v["exactitude"]
        st = v["par_strate"]
        lat = v["latence"].get("moyenne_s")
        lines.append(" & ".join([
            sysname(sy),
            fr(100 * e["globale"], 1),
            f"\\ic{{{fr(100 * e['ic95'][0], 0)}}}{{{fr(100 * e['ic95'][1], 0)}}}",
            fr(100 * st.get("in_grammar", {}).get("exactitude", float('nan')), 0),
            fr(100 * st.get("hors_grammaire", {}).get("exactitude", float('nan')), 0),
            fr(100 * (e.get("negatifs_rejetes") or 0), 0),
            fr(100 * v.get("json_strict", 0), 0),
            (fr(lat, 2) + "\\,s") if lat is not None else "--",
        ]) + " \\\\")
        if sy == "rules-parser":
            lines.append("\\midrule")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    write(path, "\n".join(lines) + "\n")

    mc = d.get("mcnemar", {})
    lines = [
        "\\begin{table}[t]\\centering\\small",
        "\\caption{Tests exacts de McNemar entre systèmes appariés sur les "
        f"{d['n_cas']} clairances ($n_{{01}}$ : A correct / B faux).}}",
        "\\label{tab:mcnemar}",
        "\\begin{tabular}{lrrr}",
        "\\toprule",
        "Paire (A vs B) & $n_{01}$ & $n_{10}$ & $p$ \\\\",
        "\\midrule",
    ]
    for pair, r in mc.items():
        a, b = pair.split(" vs ")
        pv = r["p_value"]
        pstr = "$<10^{-4}$" if pv < 1e-4 else fr(pv, 4)
        lines.append(f"{sysname(a)} vs {sysname(b)} & {r['n01']} & {r['n10']} & {pstr} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    write(mpath, "\n".join(lines) + "\n")


# =============================================================================
#  tts_bench
# =============================================================================
def gen_tts():
    d = load("tts_bench.json")
    path = os.path.join(TABLES, "tab_tts.tex")
    if not d or not any("erreur" not in v for v in d.get("engines", {}).values()):
        macro("nTTSKokoroRTF", "??")
        macro("nTTSKokoroWERVHF", "??")
        placeholder(path, "TTS", "tab:tts")
        return
    engines = {k: v for k, v in d["engines"].items() if "erreur" not in v}
    koks = [v for k, v in engines.items() if k.startswith("kokoro")]
    if koks:
        macro("nTTSKokoroRTF", fr(sum(v["rtf_moyen"] for v in koks) / len(koks), 3))
        macro("nTTSKokoroWERVHF",
              pct(sum(v["wer_aller_retour_vhf"] for v in koks) / len(koks)))
    else:
        macro("nTTSKokoroRTF", "??")
        macro("nTTSKokoroWERVHF", "??")
    lines = [
        "\\begin{table}[t]\\centering\\small",
        f"\\caption{{TTS : RTF et intelligibilité aller-retour (juge {d.get('juge', '?')}) "
        f"sur {d['n_phrases']} collationnements OACI.}}",
        "\\label{tab:tts}",
        "\\begin{tabular}{lrrr}",
        "\\toprule",
        "Moteur / voix & RTF & WER propre & WER après VHF \\\\",
        "\\midrule",
    ]
    for k, v in engines.items():
        lines.append(" & ".join([
            k.replace("_", "\\_"),
            fr(v["rtf_moyen"], 3),
            pct(v["wer_aller_retour_propre"]),
            pct(v["wer_aller_retour_vhf"]),
        ]) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    write(path, "\n".join(lines) + "\n")


# =============================================================================
#  e2e_bench
# =============================================================================
def gen_e2e():
    d = load("e2e_bench.json")
    path = os.path.join(TABLES, "tab_e2e.tex")
    if not d:
        for m in ("nEEn", "nEEVoix", "nEETexte", "nEELatMoy", "nEELatPceQuinze"):
            macro(m, "??")
        placeholder(path, "E2E", "tab:e2e")
        return
    macro("nEEn", str(d["config"]["n"]))
    macro("nEEVoix", pct(d["voix"]["reussite"], 0))
    macro("nEETexte", pct(d["texte_temoin"]["reussite"], 0))
    macro("nEELatMoy", secs(d["latences"]["totale"].get("moyenne_s")))
    macro("nEELatPceQuinze", secs(d["latences"]["totale"].get("p95_s")))
    at = d["attribution_echecs"]
    lines = [
        "\\begin{table}[t]\\centering\\small",
        "\\caption{Boucle vocale complète : configuration, réussite, attribution "
        "des échecs et latences par étage.}",
        "\\label{tab:e2e}",
        "\\begin{tabular}{lr}",
        "\\toprule",
        f"Clairances parlées (canal SNR {fr(d['config']['snr_db'], 0)}\\,dB) & "
        f"{d['config']['n']} \\\\",
        f"Réussite voix (IC Wilson) & {pct(d['voix']['reussite'], 0)} "
        f"\\ic{{{fr(100 * d['voix']['ic95'][0], 0)}}}{{{fr(100 * d['voix']['ic95'][1], 0)}}} \\\\",
        f"Réussite témoin texte & {pct(d['texte_temoin']['reussite'], 0)} \\\\",
        f"Échecs attribués STT / LLM / fournisseur & "
        f"{at['stt']} / {at['llm']} / {at['provider']} \\\\",
        "\\midrule",
    ]
    for stage, lbl in (("stt", "Latence STT"), ("llm", "Latence LLM"),
                       ("tts", "Latence TTS"), ("totale", "Latence totale")):
        ls = d["latences"][stage]
        if ls.get("n"):
            lines.append(f"{lbl} (moy. / p95) & {fr(ls['moyenne_s'], 2)} / "
                         f"{fr(ls['p95_s'], 2)}\\,s \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    write(path, "\n".join(lines) + "\n")


def main():
    gen_sim()
    gen_stt()
    gen_llm()
    gen_tts()
    gen_e2e()
    lines = ["% GENERE par gen_tables.py - ne pas editer a la main"]
    for name, val in sorted(MACROS.items()):
        lines.append(f"\\newcommand{{\\{name}}}{{{val}}}")
    write(os.path.join(HERE, "numbers.tex"), "\n".join(lines) + "\n")
    missing = [k for k, v in MACROS.items() if v == "??"]
    if missing:
        print(f"  [!] macros incompletes ({len(missing)}) : {missing}")


if __name__ == "__main__":
    main()
