"""
Banc VoiceChat-11B - scoring local de la campagne ROMEO
======================================================
Note les sorties du modele bout-en-bout parole-a-parole
`nvidia/NVIDIA-NemotronLabs-VoiceChat-11B` (inference realisee sur ROMEO,
GH200 ; voir `bench/voicechat/`) avec le code de PRODUCTION du depot, donc
exactement les memes regles que la chaine en cascade :

  1. exactitude des ordres : appels d'outil du modele -> `atc_llm.postprocess_orders`
     (normalisation d'indicatif, graphe secteur, bornes de securite S2) ->
     TrafScript compare a la verite terrain de `bench_corpus` ;
  2. collationnement : WER entre le texte prononce par le modele et le
     collationnement canonique du depot (`readback.readback_text`), apres
     normalisation radio symetrique (`bench_textnorm.norm_radio`) ;
  3. intelligibilite aller-retour : audio agent 22,05 kHz -> juge STT FIXE
     (faster-whisper small, protocole de `tts_bench`) -> WER contre le texte
     que le modele a lui-meme genere ;
  4. statistiques : IC de Wilson pour les taux, McNemar exact APPARIE contre
     la cascade Whisper-LoRA -> Mistral-7B -> XTTS mesuree sur le meme
     cluster (`e2e_bench_romeo.json`) et contre la campagne locuteur humain
     (`human_e2e.json`), avec correction de Holm.

Usage :
  bench\\bench-env\\Scripts\\python.exe bench\\voicechat_bench.py \\
      --infer bench\\results\\voicechat_raw\\results.json \\
      --audio-dir bench\\results\\voicechat_raw\\wav
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

# Les DLL CUDA/cuDNN de ctranslate2 (juge faster-whisper) ne sont PAS trouvees
# sous Windows sans ajouter le repertoire lib de torch au chemin de recherche -
# meme contournement que `bench/stt_bench.py` et `bench/local_server.py`.
try:
    import torch
    _torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
    if os.name == "nt" and os.path.isdir(_torch_lib):
        os.add_dll_directory(_torch_lib)
except ImportError:
    torch = None

import bench_corpus
from bench_stats import (bootstrap_ci_mean, holm_correction, latency_summary,
                         mcnemar_exact, wilson_ci)
from bench_textnorm import norm_radio

RESULTS_DIR = os.path.join(HERE, "results")
CASCADE_ROMEO = os.path.join(RESULTS_DIR, "e2e_bench_romeo.json")
CASCADE_LOCAL = os.path.join(RESULTS_DIR, "e2e_bench.json")
HUMAIN = os.path.join(RESULTS_DIR, "human_e2e.json")


# --------------------------------------------------------------------------
# verite terrain -> ordres -> collationnement canonique
# --------------------------------------------------------------------------
def trafscript_to_order(line):
    """'HDG AFR1234 270' -> {'callsign':'AFR1234','action':'HDG','value':270}."""
    parts = str(line).split()
    if len(parts) < 3:
        return None
    action, callsign, val = parts[0], parts[1], parts[2]
    o = {"callsign": callsign, "action": action}
    if action == "ADDWPT":
        o["wpt"] = val
        o["value"] = 0
    else:
        try:
            o["value"] = int(float(val))
        except ValueError:
            return None
    return o


def readback_reference(attendu):
    import readback
    orders = [o for o in (trafscript_to_order(l) for l in attendu) if o]
    return readback.readback_text(orders)


# --------------------------------------------------------------------------
# Collationnement CORRECT : critere explicite et symetrique.
# Le parseur a regles du depot (`atc_ai.local_interpret`) attend de la
# phraseologie CONTROLEUR (indicatif en tete) et se trompe sur un
# collationnement pilote (indicatif en fin) - il n'est donc pas utilisable ici.
# On verifie plutot, apres la normalisation radio symetrique du banc
# (`bench_textnorm.norm_radio`, qui ramene « two hundred and seventy » et
# « two seven zero » a « 270 »), que le collationnement contient bien
# l'ACTION attendue, la VALEUR attendue et l'INDICATIF attendu.
# --------------------------------------------------------------------------
_MOTS_ACTION = {
    "HDG": ("heading",),
    "ALT": ("flight level", "altitude", "feet", "climb", "descend"),
    "SPD": ("speed", "knots"),
    "ADDWPT": ("direct", "proceed"),
}


def _valeurs_acceptees(order):
    a, v = order["action"], order.get("value")
    if a == "ADDWPT":
        return {str(order.get("wpt", "")).lower()}
    v = int(v)
    vals = {str(v)}
    if a == "HDG":
        vals.add(f"{v:03d}")                       # « zero niner zero » -> 090
    if a == "ALT" and v % 100 == 0:
        vals.add(str(v // 100))                    # niveau de vol
        vals.add(f"{v // 100:03d}")
    return vals


def collationnement_correct(texte, attendu):
    """(ok, detail) - l'enonce du modele reprend-il action + valeur + indicatif ?"""
    import readback
    h = " " + norm_radio(texte or "") + " "
    details = []
    for ligne in attendu:
        o = trafscript_to_order(ligne)
        if not o:
            continue
        cs = norm_radio(readback.callsign_telephony(o["callsign"]))
        ok_cs = bool(cs) and cs in h
        ok_act = any(m in h for m in _MOTS_ACTION.get(o["action"], ()))
        ok_val = any(f" {v} " in h for v in _valeurs_acceptees(o))
        details.append({"trafscript": ligne, "indicatif": ok_cs,
                        "action": ok_act, "valeur": ok_val})
    ok = bool(details) and all(d["indicatif"] and d["action"] and d["valeur"]
                               for d in details)
    return ok, details


# --------------------------------------------------------------------------
# appels d'outil du modele -> ordres du contrat de production
# --------------------------------------------------------------------------
_TOOLCALL_RE = re.compile(r"<TOOLCALL>\s*(\[.*?\]|\{.*?\})\s*</TOOLCALL>", re.S)


def calls_from_text(text):
    """Repli : certains tours placent l'appel dans le canal texte."""
    out = []
    for m in _TOOLCALL_RE.finditer(text or ""):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        for c in (data if isinstance(data, list) else [data]):
            if isinstance(c, dict):
                out.append({"name": c.get("name", ""),
                            "arguments": c.get("arguments", {})})
    return out


def orders_from_calls(calls):
    """Appels set_flight_order -> ordres {callsign, action, value, wpt}."""
    orders = []
    for c in calls or []:
        args = c.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        if not isinstance(args, dict):
            continue
        action = str(args.get("action", "")).upper().strip()
        o = {"callsign": str(args.get("callsign", "")).strip(),
             "action": action}
        wpt = args.get("waypoint") or args.get("wpt")
        if wpt:
            o["wpt"] = str(wpt).strip()
        v = args.get("value")
        if v is not None and str(v) != "":
            try:
                o["value"] = int(float(v))
            except (TypeError, ValueError):
                o["value"] = v
        orders.append(o)
    return orders


def score_orders(orders):
    """MEME validation que la production (bornes S2 + graphe secteur)."""
    import atc_llm
    valid, rejected = atc_llm.postprocess_orders(orders)
    return sorted(v["trafscript"] for v in valid), [r["erreur"] for r in rejected]


def diagnostic(attendu, obtenu, appels, rejetes):
    """Attribution de l'echec, dans l'esprit de `e2e_bench.etage_echec` :
    on isole ce qui, dans l'appel d'outil, devie de la verite terrain."""
    if obtenu == attendu:
        return None
    if not appels:
        return "aucun_appel_outil"
    if not obtenu and rejetes:
        return "ordre_rejete_validation"
    ref = [trafscript_to_order(l) for l in attendu]
    got = [trafscript_to_order(l) for l in obtenu]
    ref = [o for o in ref if o]
    got = [o for o in got if o]
    if not got:
        return "aucun_ordre_valide"
    if len(got) != len(ref):
        return "nombre_d_ordres"
    if any(a["callsign"] != b["callsign"] for a, b in zip(ref, got)):
        return "indicatif"
    if any(a["action"] != b["action"] for a, b in zip(ref, got)):
        return "action"
    if any(a.get("value") != b.get("value") or a.get("wpt") != b.get("wpt")
           for a, b in zip(ref, got)):
        return "valeur"
    return "autre"


# --------------------------------------------------------------------------
# juge STT fixe (protocole tts_bench) pour l'intelligibilite aller-retour
# --------------------------------------------------------------------------
class Judge:
    def __init__(self):
        from faster_whisper import WhisperModel
        try:
            self.m = WhisperModel("small", device="cuda", compute_type="float16")
            self.device = "cuda"
        except Exception:
            self.m = WhisperModel("small", device="cpu", compute_type="int8")
            self.device = "cpu"

    def transcribe(self, wav_path):
        import soundfile as sf
        from math import gcd
        from scipy.signal import resample_poly
        data, sr = sf.read(wav_path, dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != 16000:
            g = gcd(int(sr), 16000)
            data = resample_poly(data, 16000 // g, int(sr) // g).astype(np.float32)
        segs, _ = self.m.transcribe(data, language="en", beam_size=5)
        return " ".join(s.text for s in segs).strip()

    @staticmethod
    def _fusionne_chiffres(t):
        """« 1-2-3-4 » -> « 1234 ».

        Whisper restitue les suites de chiffres epelees avec des tirets ;
        `norm_radio` les garde separees et le WER explose alors que l'audio
        est parfaitement intelligible (0,71 au lieu de 0,05 sur le
        sous-echantillon). On fusionne donc AVANT normalisation - c'est une
        correction de FORMAT du juge, pas une indulgence sur le contenu."""
        return re.sub(r"(?<=\d)[-‑–](?=\d)", "", t or "")

    def wer(self, wav_path, ref_text):
        import jiwer
        hyp = self.transcribe(wav_path)
        r = norm_radio(self._fusionne_chiffres(ref_text))
        h = norm_radio(self._fusionne_chiffres(hyp))
        return (jiwer.wer([r], [h]) if r else float("nan")), hyp


# --------------------------------------------------------------------------
def summarize(rows):
    k = sum(1 for r in rows if r["correct"])
    kc = sum(1 for r in rows if r["collationnement_ok"])
    n = len(rows)
    # attribution des echecs de collationnement : quel constituant manque ?
    manque = {"indicatif": 0, "action": 0, "valeur": 0}
    for r in rows:
        if r["collationnement_ok"]:
            continue
        for d in r.get("collationnement_detail", []):
            for cle in manque:
                if not d.get(cle):
                    manque[cle] += 1
    muets = sum(1 for r in rows if not (r.get("texte_agent") or "").strip())
    wers_rb = [r["wer_collationnement"] for r in rows
               if r.get("wer_collationnement") is not None
               and not np.isnan(r["wer_collationnement"])]
    wers_rt = [r["wer_aller_retour"] for r in rows
               if r.get("wer_aller_retour") is not None
               and not np.isnan(r["wer_aller_retour"])]
    out = {
        "n": n,
        # --- metrique principale : le modele a-t-il compris la clairance ? ---
        "collationnement_k": kc,
        "collationnement_correct": kc / n if n else float("nan"),
        "ic95_collationnement": list(wilson_ci(kc, n)) if n else None,
        "collationnement_manques": manque,
        "reponses_muettes": muets,
        # --- route « appel d'outil » (ordre directement executable) ---------
        "k": k,
        "exactitude_ordres": k / n if n else float("nan"),
        "ic95": list(wilson_ci(k, n)) if n else None,
        "sans_appel_outil": sum(1 for r in rows if not r["appels"]),
        "ordres_rejetes": sum(1 for r in rows if r["rejetes"]),
        "attribution_echecs": {
            d: sum(1 for r in rows if r.get("diagnostic") == d)
            for d in sorted({r["diagnostic"] for r in rows if r.get("diagnostic")})},
        "latence_s2s": latency_summary([r["s2s_latence_s"] for r in rows
                                        if r.get("s2s_latence_s")]),
        "latence_fc": latency_summary([r["fc_latence_s"] for r in rows
                                       if r.get("fc_latence_s")]),
    }
    if wers_rb:
        lo, hi = bootstrap_ci_mean(wers_rb)
        out["wer_collationnement"] = float(np.mean(wers_rb))
        out["ic95_wer_collationnement"] = [lo, hi]
    if wers_rt:
        lo, hi = bootstrap_ci_mean(wers_rt)
        out["wer_aller_retour"] = float(np.mean(wers_rt))
        out["ic95_wer_aller_retour"] = [lo, hi]
    rtf = [r["s2s_rtf"] for r in rows if r.get("s2s_rtf")]
    if rtf:
        out["rtf_s2s_median"] = float(np.median(rtf))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--infer", default=os.path.join(RESULTS_DIR, "voicechat_raw",
                                                    "results.json"))
    ap.add_argument("--audio-dir", default=os.path.join(RESULTS_DIR, "voicechat_raw",
                                                        "wav"))
    ap.add_argument("--out", default=os.path.join(RESULTS_DIR, "voicechat_romeo.json"))
    ap.add_argument("--no-judge", action="store_true",
                    help="sauter l'intelligibilite aller-retour (pas de GPU/STT)")
    args = ap.parse_args()

    with open(args.infer, encoding="utf-8") as f:
        raw = json.load(f)
    cases = bench_corpus.all_cases()
    cases = [c for c in cases if c["in_grammar"] and not c["negatif"]
             and c["categorie"] not in ("francais",)][:25]
    attendus = [sorted(bench_corpus.expected_for_llm(c)) for c in cases]
    ref_rb = [readback_reference(a) for a in attendus]

    judge = None
    if not args.no_judge:
        print("[vc] chargement du juge STT (faster-whisper small)...")
        judge = Judge()
        print(f"[vc] juge sur {judge.device}")

    par_condition = {}
    for row in raw["rows"]:
        cond = row.get("condition", "?")
        i = int(row["id"].split("_c")[-1])
        appels = row.get("fc_appels") or []
        if not appels:
            appels = calls_from_text(row.get("fc_texte", "")) or \
                     calls_from_text(row.get("s2s_texte", ""))
        orders = orders_from_calls(appels)
        got, rejetes = score_orders(orders)
        texte = (row.get("s2s_texte") or row.get("fc_texte") or "").strip()

        import jiwer
        r_n, h_n = norm_radio(ref_rb[i]), norm_radio(texte)
        wer_rb = jiwer.wer([r_n], [h_n]) if r_n else float("nan")

        wer_rt, hyp = float("nan"), ""
        wav = row.get("s2s_audio") or row.get("fc_audio")
        if judge is not None and wav:
            local = os.path.join(args.audio_dir, os.path.basename(wav))
            if os.path.exists(local) and texte:
                try:
                    wer_rt, hyp = judge.wer(local, texte)
                except Exception as e:
                    print(f"  [!] juge en echec sur {local} : {e}")

        rb_ok, rb_detail = collationnement_correct(texte, attendus[i])
        rec = {
            "id": row["id"], "cas": i, "phrase": row.get("phrase", cases[i]["phrase"]),
            "attendu": attendus[i], "obtenu": got, "correct": got == attendus[i],
            "collationnement_ok": rb_ok, "collationnement_detail": rb_detail,
            "appels": appels, "ordres": orders, "rejetes": rejetes,
            "diagnostic": diagnostic(attendus[i], got, appels, rejetes),
            "texte_agent": texte, "collationnement_reference": ref_rb[i],
            "wer_collationnement": float(wer_rb),
            "wer_aller_retour": float(wer_rt), "juge_transcription": hyp,
            "s2s_latence_s": row.get("s2s_latence_s"),
            "fc_latence_s": row.get("fc_latence_s"),
            "s2s_rtf": row.get("s2s_rtf"),
            "duree_entree_s": row.get("duree_entree_s"),
            "erreur": row.get("erreur"),
        }
        par_condition.setdefault(cond, []).append(rec)

    for rows in par_condition.values():
        rows.sort(key=lambda r: r["cas"])

    resume = {c: summarize(rows) for c, rows in par_condition.items()}

    # ---------------- comparaisons appariees ------------------------------
    comparaisons = {}
    pvals, keys = [], []

    def compare(nom, cond, ref_path, extract):
        if cond not in par_condition or not os.path.exists(ref_path):
            return
        with open(ref_path, encoding="utf-8") as f:
            ref = json.load(f)
        ref_ok = extract(ref)
        # cote VoiceChat, la sortie comparable est la COMPREHENSION de la
        # clairance (collationnement) : le modele n'a emis aucun ordre
        # structure. Ce n'est donc pas la meme sortie que la cascade (qui
        # produit un ordre executable) - la comparaison porte sur l'etage de
        # comprehension, ce que le rapport doit dire explicitement.
        vc_ok = [r["collationnement_ok"] for r in par_condition[cond]]
        n = min(len(ref_ok), len(vc_ok))
        if n < 5:
            return
        res = mcnemar_exact(vc_ok[:n], ref_ok[:n])
        res.update({"n": n,
                    "voicechat_k": sum(vc_ok[:n]),
                    "reference_k": sum(ref_ok[:n])})
        comparaisons[nom] = res
        pvals.append(res["p_value"])
        keys.append(nom)

    compare("sapi_radio_vs_cascade_romeo", "sapi_radio", CASCADE_ROMEO,
            lambda d: [bool(r.get("correct")) for r in d["rows"]])
    compare("sapi_radio_vs_cascade_locale", "sapi_radio", CASCADE_LOCAL,
            lambda d: [bool(r.get("correct")) for r in d["rows"]])
    compare("humain_micro_vs_cascade", "humain_micro", HUMAIN,
            lambda d: [bool(r.get("correct"))
                       for r in d["par_locuteur"]["nicolas"]["micro"]["rows"]])
    compare("humain_radio_vs_cascade", "humain_radio", HUMAIN,
            lambda d: [bool(r.get("correct"))
                       for r in d["par_locuteur"]["nicolas"]["radio"]["rows"]])

    if pvals:
        for k_, p in zip(keys, holm_correction(pvals)):
            comparaisons[k_]["p_holm"] = p

    out = {
        "modele": raw.get("modele"),
        "protocole": {
            "conditions": sorted(par_condition),
            "n_cas": len(cases),
            "corpus": "bench_corpus, cas EN in-grammar positifs (identiques a e2e_bench)",
            "validation": "atc_llm.postprocess_orders (bornes S2 + graphe secteur)",
            "juge_intelligibilite": "faster-whisper small, WER norm_radio "
                                    "(protocole tts_bench)",
            "materiel": raw.get("gpu"), "torch": raw.get("torch"),
            "chargement_modele_s": raw.get("chargement_modele_s"),
            "invite_systeme_atc": raw.get("message_systeme_atc"),
            "outils": raw.get("outils"),
        },
        "resume": resume,
        "comparaisons_appariees": comparaisons,
        "rows": {c: rows for c, rows in par_condition.items()},
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)

    print(f"\n[OK] voicechat_bench -> {args.out}\n")
    for cond, s in resume.items():
        print(f"  {cond:<14} collationnement {s['collationnement_k']:2d}/{s['n']:2d} = "
              f"{s['collationnement_correct']:.0%}"
              f"  [{s['ic95_collationnement'][0]:.2f};{s['ic95_collationnement'][1]:.2f}]"
              f"  muets={s['reponses_muettes']:2d}"
              f"  appels_outil={s['n'] - s['sans_appel_outil']:2d}"
              f"  WER_collat={s.get('wer_collationnement', float('nan')):.2f}"
              f"  lat_med={s['latence_s2s'].get('mediane_s', float('nan')):.1f}s")
        print(f"                 manques : {s['collationnement_manques']}")
    for nom, c in comparaisons.items():
        print(f"  [McNemar] {nom}: VoiceChat {c['voicechat_k']}/{c['n']} vs "
              f"reference {c['reference_k']}/{c['n']} ; n01={c['n01']} n10={c['n10']} "
              f"p={c['p_value']:.3f} p_Holm={c.get('p_holm', float('nan')):.3f}")


if __name__ == "__main__":
    main()
