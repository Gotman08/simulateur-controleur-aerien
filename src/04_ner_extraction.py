"""
Preuve - Semaine 2 : extraction d'information (NER) sur la phraséologie ATC
==========================================================================
Structure stricte ciblée (cf. rapport S2, corpus ATCO2) :
    (Indicatif de l'avion, Ordre donné, Valeur)

Démonstrateur à base de règles (regex) sur des transcriptions d'exemple.
Il sert de "vérité de structure" pour pré-étiqueter le corpus avant le
fine-tuning faiblement supervisé de l'encodeur.

Exécution :  python 04_ner_extraction.py
Sorties   :  ner_demo_output.json
"""
import json
import re

# alphabet OACI -> on reconnaît les indicatifs épelés ou compagnie+chiffres
CALLSIGN = re.compile(
    r"\b([A-Z][A-Z0-9]{2,3}\s?\d{1,4}[A-Z]?)\b"          # ex : AFR1234, BAW57
    r"|\b(speedbird|air\s?france|lufthansa|easy)\s?(\d{1,4})\b", re.I)

ORDERS = {
    "turn":     r"\bturn\s+(left|right)\b",
    "heading":  r"\b(?:heading|hdg|fly heading)\s+(\d{1,3})\b",
    "climb":    r"\bclimb(?:\s+to)?\s+(?:FL\s?)?(\d{2,3})\b",
    "descend":  r"\bdescend(?:\s+to)?\s+(?:FL\s?)?(\d{2,3})\b",
    "speed":    r"\b(?:reduce|increase)?\s*speed\s+(\d{2,3})\b",
    "contact":  r"\bcontact\s+([a-z]+)\s+(\d{3}\.\d{1,3})\b",
}

SAMPLES = [
    "AFR1234 turn right heading 270",
    "BAW57 climb to FL350",
    "DLH88 descend FL240 reduce speed 220",
    "RYR9 contact approach 119.700",
    "speedbird 57 fly heading 090",
]


def extract(utterance: str):
    ents = []
    m = CALLSIGN.search(utterance)
    callsign = None
    if m:
        callsign = next(g for g in m.groups() if g) if not m.group(1) else m.group(1)
        callsign = re.sub(r"\s+", "", callsign).upper()
        ents.append({"type": "CALLSIGN", "value": callsign})
    for label, pat in ORDERS.items():
        mm = re.search(pat, utterance, re.I)
        if mm:
            ents.append({"type": "ORDER", "name": label,
                         "value": " ".join(g for g in mm.groups() if g)})
    return {"text": utterance, "callsign": callsign, "entities": ents}


def main():
    results = [extract(s) for s in SAMPLES]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    with open("ner_demo_output.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    n_orders = sum(len([e for e in r["entities"] if e["type"] == "ORDER"]) for r in results)
    print(f"\n[OK] ner_demo_output.json")
    print(f"[OK] {len(results)} énoncés, "
          f"{sum(r['callsign'] is not None for r in results)} indicatifs, "
          f"{n_orders} ordres extraits")


if __name__ == "__main__":
    main()
