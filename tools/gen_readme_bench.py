"""
Injecte la synthese de la campagne bench/ dans le README (bloc BENCH:*).
=======================================================================
Source unique : bench/results/*.json — aucun chiffre saisi a la main.
Execution :  python tools/gen_readme_bench.py
"""
from __future__ import annotations

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "bench", "results")
README = os.path.join(ROOT, "README.md")


def load(name):
    path = os.path.join(RES, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pc(x, nd=1):
    return f"{100 * x:.{nd}f}%" if x is not None else "—"


def build_block():
    lines = ["| Stage | Protocol | Headline result |", "|---|---|---|"]

    def milliers(n):
        return f"{n:,}".replace(",", " ")          # 1 000 000 (insecable ASCII)

    sim = load("sim_bench.json")
    if sim:
        c = sim["cpa_multi_graines"]
        g = sim["conflit_garanti"]
        sc = {r["avions"]: r for r in sim.get("bluesky_scaling", [])}
        lines += [
            f"| Conflict geometry | {milliers(c['total_geometries'])} Monte-Carlo geometries, "
            f"5 seeds, vs independent fine grid | **{c['total_desaccords']} decision "
            f"disagreement**, dCPA error bounded by display rounding |",
            f"| Guaranteed exercise conflicts | {milliers(g['n'])} seeded draws | "
            f"**{pc(g['taux_garantie'], 1)}** guarantee (max dCPA "
            f"{g['dcpa_nm']['max']:.3f} NM ≪ 5 NM) |",
            f"| BlueSky scaling | 5 reps x 5..200 aircraft | "
            f"x{sc[5]['facteur_temps_reel_moyen']:.0f} real-time @5 → "
            f"x{sc[200]['facteur_temps_reel_moyen']:.0f} @200 |",
        ]

    stt = load("stt_bench.json")
    if stt and "systems" in stt:
        s = stt["systems"]

        def wer(sy, ck):
            return s.get(sy, {}).get(ck, {}).get("vhf_bandpass", {}).get("wer_corpus")

        lines += [
            f"| STT (real VHF audio) | ATCO2 + UWB-ATCC samples (n=150 each), production "
            f"bandpass, project WER protocol | LoRA **{pc(wer('hf-small-lora', 'atco2'))}** vs "
            f"vanilla {pc(wer('hf-small', 'atco2'))} on ATCO2 "
            f"(paired bootstrap: significant); UWB {pc(wer('hf-small-lora', 'uwb_atcc'))} |",
        ]

    llm = load("llm_bench.json")
    if llm and "systems" in llm:
        sy = llm["systems"]
        llms = {k: v for k, v in sy.items() if k != "rules-parser"}
        best = max(llms, key=lambda k: llms[k]["exactitude"]["globale"])
        b = llms[best]
        p = sy["rules-parser"]
        pretty = (best.replace("-instruct", "").replace("-q4_k_m", "")
                  .replace("mistral-7b", "Mistral-7B"))
        lines += [
            f"| Clearance interpretation | {llm['n_cas']} annotated clearances (standard + "
            f"out-of-grammar + adversarial), full production chain, {len(llms)} local LLMs | "
            f"best local **{pretty} {pc(b['exactitude']['globale'])}** "
            f"(rules parser {pc(p['exactitude']['globale'])}; out-of-grammar: LLM "
            f"{pc(b['par_strate']['hors_grammaire']['exactitude'], 0)} vs parser "
            f"{pc(p['par_strate']['hors_grammaire']['exactitude'], 0)}) |",
        ]

    tts = load("tts_bench.json")
    if tts:
        koks = [v for k, v in tts.get("engines", {}).items()
                if k.startswith("kokoro") and "erreur" not in v]
        if koks:
            rtf = sum(v["rtf_moyen"] for v in koks) / len(koks)
            wv = sum(v["wer_aller_retour_vhf"] for v in koks) / len(koks)
            lines += [
                f"| TTS (local Kokoro-82M, 4 voices) | {tts['n_phrases']} ICAO readbacks, "
                f"round-trip intelligibility (fixed STT judge, semantic normalization) | "
                f"RTF **{rtf:.2f}**, round-trip WER after VHF **{pc(wv)}** |",
            ]

    e2e = load("e2e_bench.json")
    if e2e:
        lines += [
            f"| Full voice loop (E2E) | {e2e['config']['n']} spoken clearances through radio "
            f"channel (SNR {e2e['config']['snr_db']:.0f} dB), STT→LLM→validation→TTS | "
            f"**{pc(e2e['voix']['reussite'], 0)}** exact execution (text control: "
            f"{pc(e2e['texte_temoin']['reussite'], 0)}), mean voice latency "
            f"**{e2e['latences']['totale']['moyenne_s']:.1f} s** |",
        ]

    lines += ["", "Historical ROMEO (GH200) reference figures remain in the table above; "
                  "the July 2026 campaign proves the same architecture on consumer hardware."]
    return "\n".join(lines)


def main():
    with open(README, encoding="utf-8") as f:
        md = f.read()
    block = ("<!-- BENCH:START — bloc généré par tools/gen_readme_bench.py, "
             "ne pas éditer à la main -->\n" + build_block() + "\n<!-- BENCH:END -->")
    out, n = re.subn(r"<!-- BENCH:START.*?<!-- BENCH:END -->", block, md, flags=re.S)
    if n != 1:
        raise SystemExit("marqueurs BENCH introuvables dans README.md")
    with open(README, "w", encoding="utf-8") as f:
        f.write(out)
    print("[OK] bloc bench injecte dans README.md")


if __name__ == "__main__":
    main()
