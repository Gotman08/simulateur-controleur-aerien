"""
Corpus de clairances avec verite terrain - banc de benchmark LLM
================================================================
Deux strates :

  BASE  (68 phrases)  : le jeu de la validation historique (validation/
        03_parseur_eval.py), phraseologie DANS la grammaire du parseur a
        regles. Importe dynamiquement (source unique de verite).

  EXTRA (~55 phrases) : cas HORS grammaire ou adversariaux, concus pour
        mesurer la valeur ajoutee d'un LLM par rapport au parseur a regles :
          - paraphrase   : meme intention, formulation non couverte ;
          - bruit_stt    : hesitations/repetitions typiques d'une sortie STT ;
          - francais_ext : francais parle (nombres en toutes lettres) ;
          - chiffres_ext : nombres composes ("two hundred fifty") ;
          - indicatif_ext: immatriculations epelees, compagnies hors prompt ;
          - multi_ext    : clairances triples, connecteurs ("then", "and") ;
          - mixte        : ordre valide + ordre invalide dans LA MEME phrase
                           (l'invalide DOIT etre filtre, le valide conserve) ;
          - negatif_ext  : rien ne doit etre emis (hors bornes, hors schema,
                           information pure, instruction relative).

La verite terrain est exprimee en TrafScript (format de sortie du systeme
APRES validation deterministe). Le contrat LLM ne couvre pas l'action VS :
`expected_for_llm()` retire les lignes VS de la verite terrain du parseur.

Chaque cas : {categorie, phrase, attendu, negatif, in_grammar}.
"""
from __future__ import annotations

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def _load_base_cases():
    """Importe CASES depuis validation/03_parseur_eval.py (source unique)."""
    path = os.path.join(ROOT, "validation", "03_parseur_eval.py")
    spec = importlib.util.spec_from_file_location("parseur_eval", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.CASES)


# (categorie, phrase, trafscript attendu APRES validation, negatif?)
EXTRA_CASES = [
    # --- PARAPHRASES hors grammaire (intention claire, formulation libre) ----
    ("paraphrase", "air france one two three four descend and maintain flight level one hundred",
     ["ALT AFR1234 10000"], False),
    ("paraphrase", "BAW57 make your heading zero nine zero", ["HDG BAW57 90"], False),
    ("paraphrase", "EZY21 pick up speed to three hundred knots", ["SPD EZY21 300"], False),
    ("paraphrase", "DLH88 when ready descend flight level one two zero", ["ALT DLH88 12000"], False),
    ("paraphrase", "ryanair niner route direct to delta", ["ADDWPT RYR9 DELTA"], False),
    ("paraphrase", "speedbird five seven climb now to flight level three five zero",
     ["ALT BAW57 35000"], False),
    ("paraphrase", "KLM one two three turn right heading one five five", ["HDG KLM123 155"], False),
    ("paraphrase", "AFR1234 slow down to two three zero knots", ["SPD AFR1234 230"], False),
    ("paraphrase", "BAW57 stop climb at flight level two eight zero", ["ALT BAW57 28000"], False),
    ("paraphrase", "united four five one climb and maintain flight level three three zero",
     ["ALT UAL451 33000"], False),
    ("paraphrase", "american six three fly heading one two zero", ["HDG AAL63 120"], False),
    # --- BRUIT STT (hesitations, repetitions, politesse) ---------------------
    ("bruit_stt", "uh air france one two three four er climb flight level three two zero please",
     ["ALT AFR1234 32000"], False),
    ("bruit_stt", "speedbird five seven speedbird five seven turn left heading two one zero",
     ["HDG BAW57 210"], False),
    ("bruit_stt", "easyjet two one good evening climb flight level one eight zero",
     ["ALT EZY21 18000"], False),
    ("bruit_stt", "AFR1234 roger climb flight level two four zero", ["ALT AFR1234 24000"], False),
    # --- FRANCAIS etendu (nombres en toutes lettres) --------------------------
    ("francais_ext", "AFR1234 tournez a gauche cap deux sept zero", ["HDG AFR1234 270"], False),
    ("francais_ext", "BAW57 reduisez vitesse deux trois zero noeuds", ["SPD BAW57 230"], False),
    ("francais_ext", "DLH88 directe BALMO", ["ADDWPT DLH88 BALMO"], False),
    ("francais_ext", "EZY21 montez niveau de vol trois un zero", ["ALT EZY21 31000"], False),
    ("francais_ext", "air france un deux trois quatre montez niveau un zero zero",
     ["ALT AFR1234 10000"], False),
    # --- CHIFFRES composes -----------------------------------------------------
    ("chiffres_ext", "AFR1234 climb flight level two hundred", ["ALT AFR1234 20000"], False),
    ("chiffres_ext", "BAW57 reduce speed two hundred fifty knots", ["SPD BAW57 250"], False),
    ("chiffres_ext", "EZY21 fly heading zero four five", ["HDG EZY21 45"], False),
    ("chiffres_ext", "DLH88 descend flight level one hundred", ["ALT DLH88 10000"], False),
    # --- INDICATIFS etendus (immatriculations epelees) --------------------------
    ("indicatif_ext", "foxtrot golf alfa bravo charlie climb flight level one five zero",
     ["ALT FGABC 15000"], False),
    ("indicatif_ext", "november one two three alfa bravo descend flight level niner zero",
     ["ALT N123AB 9000"], False),
    # --- MULTI etendu ------------------------------------------------------------
    ("multi_ext", "AFR1234 climb flight level three one zero speed two eight zero knots direct CROSS",
     ["ALT AFR1234 31000", "SPD AFR1234 280", "ADDWPT AFR1234 CROSS"], False),
    ("multi_ext", "speedbird five seven descend flight level one four zero and reduce speed to two five zero knots",
     ["ALT BAW57 14000", "SPD BAW57 250"], False),
    ("multi_ext", "KLM123 turn right heading two two zero then direct NORTH",
     ["HDG KLM123 220", "ADDWPT KLM123 NORTH"], False),
    ("multi_ext", "easyjet two one descend flight level niner zero speed two one zero",
     ["ALT EZY21 9000", "SPD EZY21 210"], False),
    # --- MIXTE : valide + invalide dans la meme phrase ----------------------------
    # (le systeme DOIT conserver l'ordre valide et filtrer l'invalide)
    ("mixte", "AFR1234 climb flight level three two zero and increase speed four zero zero knots",
     ["ALT AFR1234 32000"], False),
    ("mixte", "BAW57 fly heading zero niner zero contact tower one one eight decimal one",
     ["HDG BAW57 90"], False),
    ("mixte", "DLH88 descend flight level five one zero reduce speed two five zero",
     ["SPD DLH88 250"], False),
    ("mixte", "EZY21 direct NOWHERE then speed two four zero", ["SPD EZY21 240"], False),
    # --- NEGATIFS etendus : RIEN ne doit etre emis ---------------------------------
    ("negatif_ext", "AFR1234 turn left twenty degrees", [], True),            # cap RELATIF
    ("negatif_ext", "BAW57 contact marseille one three two decimal five five", [], True),
    ("negatif_ext", "AFR1234 squawk seven thousand", [], True),               # hors schema
    ("negatif_ext", "QNH one zero one three", [], True),                      # information
    ("negatif_ext", "AFR1234 hold position", [], True),                       # hors schema
    ("negatif_ext", "EZY21 climb flight level six zero zero", [], True),      # FL600 hors bornes
    ("negatif_ext", "DLH88 increase speed four five zero knots", [], True),   # 450 kt hors bornes
    ("negatif_ext", "AFR1234 fly heading three seven zero", [], True),        # 370 deg hors bornes
    ("negatif_ext", "BAW57 direct KOLOS", [], True),                          # fix inconnu
    ("negatif_ext", "radar contact", [], True),
    ("negatif_ext", "AFR1234 report your heading", [], True),                 # demande d'info
    ("negatif_ext", "expect higher in one zero miles", [], True),
    ("negatif_ext", "AFR1234 cleared ILS approach runway two six", [], True), # hors schema
    ("negatif_ext", "AFR1234 monter niveau cinq cents", [], True),            # FL500 hors bornes
]


def all_cases():
    """[{categorie, phrase, attendu, negatif, in_grammar}] - BASE puis EXTRA."""
    cases = []
    for cat, phrase, attendu, negatif in _load_base_cases():
        cases.append({"categorie": cat, "phrase": phrase, "attendu": list(attendu),
                      "negatif": negatif, "in_grammar": True})
    for cat, phrase, attendu, negatif in EXTRA_CASES:
        cases.append({"categorie": cat, "phrase": phrase, "attendu": list(attendu),
                      "negatif": negatif, "in_grammar": False})
    return cases


def expected_for_llm(case):
    """Verite terrain pour le contrat LLM : lignes VS retirees (hors contrat)."""
    return [t for t in case["attendu"] if not t.startswith("VS ")]


if __name__ == "__main__":
    cases = all_cases()
    n_base = sum(1 for c in cases if c["in_grammar"])
    n_extra = len(cases) - n_base
    n_neg = sum(1 for c in cases if c["negatif"])
    print(f"{len(cases)} cas ({n_base} base + {n_extra} extra), dont {n_neg} negatifs")
    from collections import Counter
    print(Counter(c["categorie"] for c in cases))
