"""
Benchmark LLM - extraction d'intention ATC multi-modeles
========================================================
Pour CHAQUE modele GGUF (llama.cpp derriere la facade OpenAI-compatible
locale), execute les 116 clairances du corpus (bench_corpus) a travers LA
CHAINE DE PRODUCTION :

    atc_llm.build_messages (prompt systeme + KB OACI inlinee + indices NER)
    -> POST /v1/chat/completions   (ai_client.LlmClient, temperature 0.0)
    -> atc_llm.parse_orders + postprocess_orders (bornes + graphe secteur)
    -> TrafScript compare a la verite terrain (insensible a l'ordre)

puis les 20 descriptions du generateur de situations (validation/04) avec le
MEME verificateur de contraintes que la validation historique.

Le parseur a regles (atc_ai) est evalue sur le meme corpus comme systeme de
reference. Metriques : exactitude (globale / positifs / negatifs / par
categorie / par strate in-grammar vs hors-grammaire) avec IC de Wilson,
validite JSON stricte, latence (bootstrap), debit tokens/s (journal serveur),
tests de McNemar apparies entre systemes.

Execution :  bench\\bench-env\\Scripts\\python.exe bench\\llm_bench.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import requests

import bench_corpus
from bench_stats import bootstrap_ci_mean, latency_summary, mcnemar_exact, wilson_ci

RESULTS_DIR = os.path.join(HERE, "results")
DEFAULT_PORT = 8901


# --- serveur local ------------------------------------------------------------
class LocalLlmServer:
    """Lance local_server.py --role llm pour un GGUF donne, attend la sante."""

    def __init__(self, gguf, name, port=DEFAULT_PORT, usage_log=""):
        self.gguf, self.name, self.port, self.usage_log = gguf, name, port, usage_log
        self.proc = None
        self.start_s = None

    def __enter__(self):
        cmd = [sys.executable, os.path.join(HERE, "local_server.py"),
               "--role", "llm", "--llm-gguf", self.gguf, "--llm-name", self.name,
               "--port", str(self.port), "--warm"]
        if "mistral" in self.name.lower():
            cmd.append("--merge-system")     # template v0.3 sans role system
        if self.usage_log:
            cmd += ["--usage-log", self.usage_log]
        t0 = time.perf_counter()
        self._errlog = open(os.path.join(RESULTS_DIR, f"server_{self.name}.log"), "w")
        self.proc = subprocess.Popen(cmd, stdout=self._errlog, stderr=self._errlog)
        deadline = time.time() + 600
        url = f"http://127.0.0.1:{self.port}/v1/models"
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"serveur mort (code {self.proc.returncode}) pour {self.name}")
            try:
                if requests.get(url, timeout=2).ok:
                    self.start_s = time.perf_counter() - t0
                    return self
            except requests.RequestException:
                pass
            time.sleep(1.0)
        raise TimeoutError(f"serveur {self.name} indisponible apres 600 s")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if getattr(self, "_errlog", None):
            self._errlog.close()


# --- chaine de production (identique a AIClient.interpret, + acces au brut) ----
def interpret_verbose(llm_client, text):
    """MEMES etapes que ai_client.AIClient.interpret, en exposant la reponse
    brute du LLM (pour mesurer la validite JSON stricte)."""
    import atc_llm
    import kb_oaci
    ner = atc_llm.ner_extract(text)
    docs = kb_oaci.build_documents()
    messages = atc_llm.build_messages(text, [(d, 1.0) for d in docs], ner)
    raw = llm_client.chat(messages)
    orders = atc_llm.parse_orders(raw)
    valid, rejected = atc_llm.postprocess_orders(orders)
    return {"raw": raw, "orders": orders,
            "trafscript": [v["trafscript"] for v in valid],
            "rejected": [r["erreur"] for r in rejected]}


def json_strict_ok(raw):
    """La reponse brute est-elle DIRECTEMENT un tableau JSON (apres retrait
    d'eventuelles clotures de code) ? Plus exigeant que parse_orders."""
    t = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    try:
        return isinstance(json.loads(t), list)
    except Exception:
        return False


# --- evaluation clairances ------------------------------------------------------
def eval_clairances_llm(cases, port, model_name):
    from ai_client import LlmClient, ProviderConfig, ProviderError
    os.environ["ATC_LLM_URL"] = f"http://127.0.0.1:{port}"
    os.environ["ATC_LLM_KEY"] = ""
    os.environ["ATC_LLM_MODEL"] = model_name
    client = LlmClient(ProviderConfig.from_env("llm"))
    # echauffement (compilation du template, caches) - non compte
    try:
        client.chat([{"role": "user", "content": "ready?"}], max_tokens=8)
    except ProviderError:
        pass
    rows = []
    for i, case in enumerate(cases):
        expected = sorted(bench_corpus.expected_for_llm(case))
        t0 = time.perf_counter()
        err = ""
        try:
            out = interpret_verbose(client, case["phrase"])
        except ProviderError as e:
            out = {"raw": "", "orders": [], "trafscript": [], "rejected": []}
            err = str(e)
        dt = time.perf_counter() - t0
        got = sorted(out["trafscript"])
        # une erreur fournisseur n'est JAMAIS un succes (meme si un negatif
        # attend une sortie vide : ici le systeme n'a pas repondu du tout)
        correct = False if err else ((got == []) if case["negatif"] else (got == expected))
        rows.append({"categorie": case["categorie"], "phrase": case["phrase"],
                     "negatif": case["negatif"], "in_grammar": case["in_grammar"],
                     "attendu": expected, "obtenu": got,
                     "correct": bool(correct),
                     "json_strict": json_strict_ok(out["raw"]),
                     "n_orders_bruts": len(out["orders"]),
                     "n_rejets": len(out["rejected"]),
                     "latence_s": dt, "erreur": err,
                     "brut": out["raw"][:400]})
        print(f"    [{i + 1:3d}/{len(cases)}] {'OK ' if correct else 'KO '} "
              f"({dt:5.1f}s) {case['phrase'][:60]!r}", flush=True)
    return rows


def eval_clairances_parser(cases):
    """Systeme de reference : parseur a regles (hors runtime depuis 2026-07)."""
    from atc_ai import local_interpret
    rows = []
    for case in cases:
        t0 = time.perf_counter()
        r = local_interpret(case["phrase"])
        dt = time.perf_counter() - t0
        got_full = sorted(r["trafscript"])
        # contrat LLM (sans VS) pour comparaison appariee avec les modeles
        got_llm = sorted(t for t in r["trafscript"] if not t.startswith("VS "))
        expected = sorted(bench_corpus.expected_for_llm(case))
        correct = (got_llm == []) if case["negatif"] else (got_llm == expected)
        expected_own = sorted(case["attendu"])
        correct_own = (got_full == []) if case["negatif"] else (got_full == expected_own)
        rows.append({"categorie": case["categorie"], "phrase": case["phrase"],
                     "negatif": case["negatif"], "in_grammar": case["in_grammar"],
                     "attendu": expected, "obtenu": got_llm,
                     "correct": bool(correct), "correct_contrat_propre": bool(correct_own),
                     "json_strict": True, "n_orders_bruts": len(r["orders"]),
                     "n_rejets": len(r["rejected"]), "latence_s": dt, "erreur": ""})
    return rows


# --- evaluation generateur de situations ----------------------------------------
def _load_gen_eval():
    path = os.path.join(ROOT, "validation", "04_generateur_eval.py")
    spec = importlib.util.spec_from_file_location("generateur_eval", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def eval_scenarios_llm(port, model_name):
    import atc_ai
    import atc_llm
    from ai_client import LlmClient, ProviderConfig, ProviderError
    gen = _load_gen_eval()
    os.environ["ATC_LLM_URL"] = f"http://127.0.0.1:{port}"
    os.environ["ATC_LLM_MODEL"] = model_name
    client = LlmClient(ProviderConfig.from_env("llm"))
    stats = defaultdict(lambda: {"n": 0, "ok": 0})
    fails, latences = [], []
    n_desc_ok = 0
    for desc, groups in gen.TESTS:
        t0 = time.perf_counter()
        try:
            raw = client.chat(atc_llm.build_scenario_messages(desc),
                              max_tokens=768, timeout=180)
            items = atc_llm.clean_scenario_items(atc_llm.parse_orders(raw))
            acs = atc_ai._items_to_aircraft(items)
        except ProviderError as e:
            acs = []
            fails.append({"description": desc, "contrainte": "erreur", "detail": str(e)})
        latences.append(time.perf_counter() - t0)
        n_attendu = sum(g["count"] for g in groups)
        stats["nombre"]["n"] += 1
        before = len(fails)
        if len(acs) != n_attendu:
            fails.append({"description": desc, "contrainte": "nombre",
                          "detail": f"{len(acs)} avions, attendu {n_attendu}"})
        else:
            stats["nombre"]["ok"] += 1
            i = 0
            for g in groups:
                gen.check_group(g, acs[i:i + g["count"]], stats, fails, desc)
                i += g["count"]
        n_desc_ok += int(len(acs) == n_attendu and len(fails) == before)
    n_checks = sum(s["n"] for s in stats.values())
    n_ok = sum(s["ok"] for s in stats.values())
    return {"n_descriptions": len(gen.TESTS), "descriptions_conformes": n_desc_ok,
            "n_contraintes": n_checks, "n_contraintes_ok": n_ok,
            "taux_contraintes": (n_ok / n_checks) if n_checks else float("nan"),
            "ic95_taux": list(wilson_ci(n_ok, n_checks)),
            "par_contrainte": {k: dict(v) for k, v in stats.items()},
            "latence": latency_summary(latences),
            "echecs": fails[:20]}


def eval_scenarios_parser():
    gen = _load_gen_eval()
    stats = defaultdict(lambda: {"n": 0, "ok": 0})
    fails = []
    n_desc_ok = 0
    for desc, groups in gen.TESTS:
        acs = gen.local_scenario(desc)
        n_attendu = sum(g["count"] for g in groups)
        stats["nombre"]["n"] += 1
        before = len(fails)
        if len(acs) != n_attendu:
            fails.append({"description": desc, "contrainte": "nombre",
                          "detail": f"{len(acs)} avions, attendu {n_attendu}"})
        else:
            stats["nombre"]["ok"] += 1
            i = 0
            for g in groups:
                gen.check_group(g, acs[i:i + g["count"]], stats, fails, desc)
                i += g["count"]
        n_desc_ok += int(len(acs) == n_attendu and len(fails) == before)
    n_checks = sum(s["n"] for s in stats.values())
    n_ok = sum(s["ok"] for s in stats.values())
    return {"n_descriptions": len(gen.TESTS), "descriptions_conformes": n_desc_ok,
            "n_contraintes": n_checks, "n_contraintes_ok": n_ok,
            "taux_contraintes": (n_ok / n_checks) if n_checks else float("nan"),
            "ic95_taux": list(wilson_ci(n_ok, n_checks)),
            "par_contrainte": {k: dict(v) for k, v in stats.items()},
            "echecs": fails[:20]}


# --- agregation -------------------------------------------------------------------
def summarize(rows):
    pos = [r for r in rows if not r["negatif"]]
    neg = [r for r in rows if r["negatif"]]
    par_cat = defaultdict(lambda: {"n": 0, "ok": 0})
    par_strate = defaultdict(lambda: {"n": 0, "ok": 0})
    for r in rows:
        par_cat[r["categorie"]]["n"] += 1
        par_cat[r["categorie"]]["ok"] += int(r["correct"])
        strate = "in_grammar" if r["in_grammar"] else "hors_grammaire"
        par_strate[strate]["n"] += 1
        par_strate[strate]["ok"] += int(r["correct"])
    k = sum(r["correct"] for r in rows)
    kp = sum(r["correct"] for r in pos)
    kn = sum(r["correct"] for r in neg)
    lat = [r["latence_s"] for r in rows if not r["erreur"]]
    return {
        "n": len(rows),
        "exactitude": {"globale": k / len(rows), "ic95": list(wilson_ci(k, len(rows))),
                       "positifs": kp / len(pos) if pos else None,
                       "ic95_positifs": list(wilson_ci(kp, len(pos))),
                       "negatifs_rejetes": kn / len(neg) if neg else None,
                       "ic95_negatifs": list(wilson_ci(kn, len(neg)))},
        "json_strict": sum(r["json_strict"] for r in rows) / len(rows),
        "n_erreurs_fournisseur": sum(1 for r in rows if r["erreur"]),
        "par_categorie": {c: {**v, "exactitude": v["ok"] / v["n"]}
                          for c, v in sorted(par_cat.items())},
        "par_strate": {s: {**v, "exactitude": v["ok"] / v["n"],
                           "ic95": list(wilson_ci(v["ok"], v["n"]))}
                       for s, v in par_strate.items()},
        "latence": latency_summary(lat),
        "echecs": [{k2: r[k2] for k2 in ("categorie", "phrase", "attendu", "obtenu", "erreur")}
                   for r in rows if not r["correct"]][:40],
    }


def tokens_stats(usage_log, model_name):
    if not os.path.exists(usage_log):
        return {}
    gen_tps, prompt_tokens, completion_tokens = [], [], []
    with open(usage_log, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("model") != model_name or not e.get("completion_tokens"):
                continue
            prompt_tokens.append(e.get("prompt_tokens") or 0)
            completion_tokens.append(e["completion_tokens"])
            if e.get("duration_s"):
                gen_tps.append(e["completion_tokens"] / e["duration_s"])
    if not gen_tps:
        return {}
    lo, hi = bootstrap_ci_mean(gen_tps)
    return {"n_requetes": len(gen_tps),
            "prompt_tokens_moyen": sum(prompt_tokens) / len(prompt_tokens),
            "completion_tokens_moyen": sum(completion_tokens) / len(completion_tokens),
            "tokens_generes_par_s_moyen": sum(gen_tps) / len(gen_tps),
            "ic95_tokens_par_s": [lo, hi],
            "note": "debit = completion_tokens / duree totale requete (prefill inclus)"}


def machine_info():
    info = {"python": sys.version.split()[0]}
    try:
        try:
            import torch
            _lib = os.path.join(os.path.dirname(torch.__file__), "lib")
            if os.name == "nt" and os.path.isdir(_lib):
                os.add_dll_directory(_lib)
        except ImportError:
            pass
        import llama_cpp
        info["llama_cpp"] = llama_cpp.__version__
        info["gpu_offload"] = bool(llama_cpp.llama_supports_gpu_offload())
    except Exception as e:
        info["llama_cpp_erreur"] = str(e)
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                              "--format=csv,noheader"], capture_output=True, text=True,
                             timeout=10)
        info["gpu"] = out.stdout.strip()
    except Exception:
        pass
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="", help="name=path.gguf,name2=path2.gguf")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--out", default=os.path.join(RESULTS_DIR, "llm_bench.json"))
    ap.add_argument("--skip-scenarios", action="store_true")
    args = ap.parse_args()

    models = {}
    if args.models:
        for part in args.models.split(","):
            name, _, path = part.partition("=")
            models[name.strip()] = path.strip()
    else:
        for f in sorted(os.listdir(os.path.join(HERE, "models"))):
            if f.endswith(".gguf"):
                name = os.path.splitext(f)[0].lower()
                models[name] = os.path.join(HERE, "models", f)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    usage_log = os.path.join(RESULTS_DIR, "llm_usage.jsonl")
    cases = bench_corpus.all_cases()
    print(f"[llm_bench] {len(cases)} clairances, {len(models)} modeles : {list(models)}")

    results = {"machine": machine_info(), "port": args.port,
               "n_cas": len(cases), "systems": {}, "rows": {}}

    print("[llm_bench] reference : parseur a regles")
    parser_rows = eval_clairances_parser(cases)
    results["rows"]["rules-parser"] = parser_rows
    results["systems"]["rules-parser"] = summarize(parser_rows)
    if not args.skip_scenarios:
        results["systems"]["rules-parser"]["scenarios"] = eval_scenarios_parser()

    for name, gguf in models.items():
        print(f"[llm_bench] modele : {name} ({os.path.getsize(gguf) / 1e9:.2f} Go)")
        with LocalLlmServer(gguf, name, args.port, usage_log) as srv:
            rows = eval_clairances_llm(cases, args.port, name)
            summary = summarize(rows)
            summary["chargement_serveur_s"] = round(srv.start_s, 1)
            summary["taille_gguf_go"] = round(os.path.getsize(gguf) / 1e9, 2)
            if not args.skip_scenarios:
                print(f"    scenarios ({name})...")
                summary["scenarios"] = eval_scenarios_llm(args.port, name)
            summary["tokens"] = tokens_stats(usage_log, name)
            results["rows"][name] = rows
            results["systems"][name] = summary
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1, ensure_ascii=False)
        print(f"    -> exactitude {summary['exactitude']['globale']:.1%} "
              f"(sauvegarde intermediaire)")

    # McNemar apparie entre tous les systemes (issue binaire 'correct' par cas)
    names = list(results["rows"])
    mcn = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ra = [r["correct"] for r in results["rows"][a]]
            rb = [r["correct"] for r in results["rows"][b]]
            mcn[f"{a} vs {b}"] = mcnemar_exact(ra, rb)
    results["mcnemar"] = mcn

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    print(f"[OK] llm_bench -> {args.out}")
    for name, s in results["systems"].items():
        print(f"  {name:40s} exactitude={s['exactitude']['globale']:.1%} "
              f"IC95={s['exactitude']['ic95']}")


if __name__ == "__main__":
    main()
