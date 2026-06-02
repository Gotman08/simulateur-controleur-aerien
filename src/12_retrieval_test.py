"""
Preuve - Semaine 5 (U2) : test de qualite du retrieval
======================================================
Pour des requetes ATC types, verifie que la bonne fiche de regle remonte en tete
(cap -> HDG, niveau/altitude -> ALT, vitesse -> SPD, point -> ADDWPT, informatif).

A lancer sur un noeud armgpu. (embedder seul, pas de LLM)
"""
import os

os.environ.setdefault("HF_HOME", "/gpfs/projet/r250127/hf_cache")

from atc_llm import Retriever

QUERIES = [
    ("turn right heading two seven zero", "HDG"),
    ("climb flight level three five zero", "ALT"),
    ("descend to flight level one hundred", "ALT"),
    ("reduce speed two two zero", "SPD"),
    ("proceed direct to BALMO", "ADDWPT"),
    ("contact approach one one niner decimal seven", None),
    ("qnh one zero one four", None),
]


def main():
    r = Retriever()
    print(f"[*] KB : {len(r.docs)} fiches | modele {r.model.__class__.__name__}")
    hits = 0
    for q, expected in QUERIES:
        top = r.retrieve(q, k=3)
        top_action = top[0][0]["action"]
        ok = (top_action == expected)
        hits += ok
        print(f"\nQ: {q}")
        print(f"   attendu={expected}  obtenu={top_action}  {'OK' if ok else '!!'}")
        for d, s in top:
            print(f"     {s:.3f} [{d['action']}] {d['title']}")
    print(f"\n[U2] {hits}/{len(QUERIES)} requetes avec la bonne fiche en tete.")


if __name__ == "__main__":
    main()
