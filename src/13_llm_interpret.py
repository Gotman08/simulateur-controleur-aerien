"""
Preuve - Semaine 5 (U3) : interpretation LLM ancree -> JSON strict (porte)
==========================================================================
Demonstration de interpret() (atc_llm) : NER + retrieval + LLM Mistral + validation S2.
Critere (gate) : 100% des sorties sont du JSON parseable et conforme au schema ;
les items informatifs (contact/qnh) ne produisent aucun ordre.

A lancer sur un noeud armgpu (GPU). Reutilise par 14/15.
"""
import os
import json

os.environ.setdefault("HF_HOME", "/gpfs/projet/r250127/hf_cache")

import atc_llm

SAMPLES = [
    "air france one two three four turn right heading two seven zero",
    "speedbird five seven climb flight level three five zero",
    "lufthansa eight eight descend flight level two four zero reduce speed two two zero",
    "ryanair niner contact approach one one niner decimal seven",      # informatif -> []
    "delta four zero two proceed direct to BALMO",
]


def main():
    r = atc_llm.Retriever()
    print(f"[*] KB {len(r.docs)} fiches | LLM {atc_llm.LLM_ID}")
    n_parse = n_orders = n_valid = 0
    for s in SAMPLES:
        res = atc_llm.interpret(s, r)
        n_parse += isinstance(res["orders"], list)
        n_orders += len(res["orders"])
        n_valid += len(res["valid"])
        print(f"\nATC   : {s}")
        print(f"  JSON  : {json.dumps(res['orders'], ensure_ascii=False)}")
        for v in res["valid"]:
            print(f"  OK    -> {v['trafscript']}")
        for rj in res["rejected"]:
            print(f"  REJET -> {rj['order']} : {rj['erreur']}")
    print(f"\n[U3] {n_parse}/{len(SAMPLES)} JSON parseables ; "
          f"{n_valid}/{n_orders} ordres valides (TrafScript).")


if __name__ == "__main__":
    main()
