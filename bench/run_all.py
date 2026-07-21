"""
Orchestrateur du banc de benchmark — execution complete
=======================================================
Enchaine les benchmarks dans l'ordre (le GPU est serialise) :

  1. sim_bench   (venv APPLICATION, BlueSky requis)   — CPA, conflits, charge
  2. llm_bench   (venv bench, GPU)                    — 4 modeles + parseur
  3. stt_bench   (venv bench, GPU)                    — 5 systemes x 2 corpus x 2 cond.
  4. tts_bench   (venv bench, GPU juge)               — kokoro + SAPI
  5. e2e_bench   (venv bench, GPU)                    — boucle vocale complete
  6. figures     (venv bench)                         — toutes les figures

Usage :  bench\\bench-env\\Scripts\\python.exe bench\\run_all.py [--skip sim,llm,...]

Les resultats intermediaires sont sauvegardes au fil de l'eau dans
bench/results/*.json ; chaque script est relancable individuellement.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP_PY = os.path.join(ROOT, "src", "bluesky-env", "Scripts", "python.exe")
BENCH_PY = sys.executable

STEPS = [
    ("sim", [APP_PY, os.path.join(HERE, "sim_bench.py")]),
    ("llm", [BENCH_PY, os.path.join(HERE, "llm_bench.py")]),
    ("stt", [BENCH_PY, os.path.join(HERE, "stt_bench.py")]),
    ("tts", [BENCH_PY, os.path.join(HERE, "tts_bench.py"), "--save-audio"]),
    ("e2e", [BENCH_PY, os.path.join(HERE, "e2e_bench.py"), "--save-audio",
             "--llm-gguf", os.path.join(HERE, "models",
                                        "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf")]),
    ("figures", [BENCH_PY, os.path.join(HERE, "figures.py")]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", default="", help="etapes a sauter (csv)")
    ap.add_argument("--only", default="", help="n'executer que ces etapes (csv)")
    args = ap.parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    for name, cmd in STEPS:
        if name in skip or (only and name not in only):
            print(f"[run_all] {name} : saute")
            continue
        print(f"[run_all] === {name} ===", flush=True)
        t0 = time.time()
        r = subprocess.run(cmd, cwd=ROOT)
        print(f"[run_all] {name} : code {r.returncode} en {time.time() - t0:.0f} s",
              flush=True)
        if r.returncode != 0:
            print(f"[run_all] ARRET sur echec de {name}")
            sys.exit(r.returncode)
    print("[run_all] campagne complete terminee.")


if __name__ == "__main__":
    main()
