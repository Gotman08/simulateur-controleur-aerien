"""
Preuve - Semaine 5 (U7) : usage du graphe secteur (validation + routage)
========================================================================
1) Routage : plus court chemin sur le graphe (distances NM, separation 5 NM).
2) Validation : un ADDWPT vers un fix CONNU est accepte ; vers un point inconnu
   du secteur, il est REJETE (anti-hallucination de routage).

A lancer sur un noeud armgpu (la partie interpret() charge le LLM).
"""
import os

os.environ.setdefault("HF_HOME", f"/gpfs/scratch/{os.environ.get('USER','nimarano')}/atc-whisper-s4/hf_cache")

import graph_secteur
import atc_llm


def main():
    g = graph_secteur.SectorGraph()
    print("=== GRAPHE SECTEUR (S2) ===")
    print("Fixes :", g.fixes())
    print("Topo  :", g.topology_text())
    for a, b in [("ENTRY_W", "EXIT_E"), ("ENTRY_S", "NORTH")]:
        p, d = g.shortest_path(a, b)
        chemin = " -> ".join(p) if p else "(aucun)"
        print(f"  plus court chemin {a} -> {b} : {chemin} = {d:.1f} NM")

    print("\n=== VALIDATION ADDWPT VIA LE GRAPHE ===")
    r = atc_llm.Retriever()
    cases = [
        "delta four zero two proceed direct to BALMO",          # fix connu -> OK
        "delta four zero two proceed direct to tango bravo",    # inconnu -> rejet
    ]
    for s in cases:
        res = atc_llm.interpret(s, r)
        print(f"\nATC   : {s}")
        print(f"  valides: {[v['order'] for v in res['valid']]}")
        print(f"  rejets : {[rj['erreur'] for rj in res['rejected']]}")
    print("\n[U7] graphe secteur integre (routage + validation des fixes).")


if __name__ == "__main__":
    main()
