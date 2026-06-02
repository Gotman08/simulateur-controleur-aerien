"""
Base de connaissances phraseologie ATC - Semaine 5
==================================================
Fiches de regles FACTUELLES et CONCISES (redigees pour ce projet ; aucun extrait
verbatim d'un document protege) qui ancrent l'interpretation LLM -> JSON BlueSky.

Chaque fiche relie une intention de phraseologie standard au schema d'ordre du
connecteur S2 : {callsign, action, value, [wpt]}, action in {HDG, ALT, SPD, ADDWPT}.

Reutilise, quand disponibles, les regles deja codees du projet :
  - LIMITS (bornes) depuis 03_bluesky_connector.py
  - ORDERS (motifs d'intentions) depuis 04_ner_extraction.py
  - waypoints depuis secteur_graphe.json
Sinon, repli sur des valeurs par defaut equivalentes.
"""
import os
import json
import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module(filename, modname):
    path = os.path.join(_HERE, filename)
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# --- regles du projet (reutilisation S2) ---------------------------------
_bsky = _load_module("03_bluesky_connector.py", "bsky_conn")
LIMITS = getattr(_bsky, "LIMITS", {"HDG": (0, 360, "deg"),
                                   "ALT": (0, 45000, "ft"),
                                   "SPD": (0, 350, "kt")})

_ner = _load_module("04_ner_extraction.py", "ner_extr")
ORDER_NAMES = list(getattr(_ner, "ORDERS", {}).keys()) or \
    ["turn", "heading", "climb", "descend", "speed", "contact"]


def _load_waypoints():
    path = os.path.join(_HERE, "secteur_graphe.json")
    if not os.path.exists(path):
        return ["BALMO", "CROSS", "DELTA", "NORTH", "ENTRY_W", "ENTRY_S", "EXIT_E"]
    try:
        with open(path, encoding="utf-8") as f:
            g = json.load(f)
        for key in ("nodes", "noeuds", "fixes"):
            if key in g:
                items = g[key]
                if isinstance(items, dict):
                    return list(items.keys())
                return [n.get("id") or n.get("name") for n in items if isinstance(n, dict)] or \
                       [str(n) for n in items]
        return list(g.keys())
    except Exception:
        return ["BALMO", "CROSS", "DELTA", "NORTH", "ENTRY_W", "ENTRY_S", "EXIT_E"]


WAYPOINTS = _load_waypoints()
_hdg = LIMITS.get("HDG", (0, 360, "deg"))
_alt = LIMITS.get("ALT", (0, 45000, "ft"))
_spd = LIMITS.get("SPD", (0, 350, "kt"))


# --- fiches de regles (contenu original, factuel) ------------------------
CARDS = [
    {"id": "act-heading", "action": "HDG",
     "title": "Instruction de cap (heading)",
     "text": (f"Un changement de cap fait voler l'avion vers un cap magnetique en degres "
              f"({_hdg[0]}-{_hdg[1]}). Declenche par 'turn left/right heading' ou 'fly heading' "
              f"suivi de trois chiffres. JSON: action HDG, value = cap en degres."),
     "example": "turn right heading two seven zero -> {action: HDG, value: 270}"},

    {"id": "act-altitude", "action": "ALT",
     "title": "Montee / descente (altitude ou niveau de vol)",
     "text": (f"'climb to' ou 'descend to' fixe une altitude cible. Un niveau de vol "
              f"'flight level FLxxx' se convertit en pieds en multipliant par 100 "
              f"(FL350 = 35000 ft). Une altitude est deja en pieds. Bornes {_alt[0]}-{_alt[1]} ft. "
              f"JSON: action ALT, value = altitude en pieds."),
     "example": "descend flight level one hundred -> {action: ALT, value: 10000}"},

    {"id": "act-speed", "action": "SPD",
     "title": "Instruction de vitesse",
     "text": (f"'reduce/increase speed' ou 'speed' fixe une vitesse en noeuds "
              f"({_spd[0]}-{_spd[1]} kt). JSON: action SPD, value = vitesse en noeuds."),
     "example": "reduce speed two two zero -> {action: SPD, value: 220}"},

    {"id": "act-addwpt", "action": "ADDWPT",
     "title": "Routage direct / via un point",
     "text": ("'proceed direct to' ou 'route via' ajoute un point de cheminement (waypoint/fix) "
              "a la route. JSON: action ADDWPT, wpt = nom du point, value = altitude optionnelle. "
              f"Points connus du secteur : {', '.join(map(str, WAYPOINTS))}."),
     "example": "proceed direct to BALMO -> {action: ADDWPT, wpt: BALMO}"},

    {"id": "ctx-numbers", "action": None,
     "title": "Prononciation des nombres",
     "text": ("Les nombres sont epeles chiffre par chiffre (zero, one, two, ... niner=9). "
              "Les caps sur trois chiffres, les frequences avec 'decimal'. Convertir les "
              "chiffres epeles en valeur numerique pour le JSON."),
     "example": "one one niner decimal seven -> 119.7"},

    {"id": "ctx-callsign", "action": None,
     "title": "Indicatif (callsign)",
     "text": ("L'indicatif identifie l'avion (compagnie + numero, ex. AFR1234, ou epele en "
              "alphabet OACI). Toujours reporter l'indicatif dans le champ callsign du JSON."),
     "example": "air france one two three four -> callsign AFR1234"},

    {"id": "ctx-qnh", "action": None,
     "title": "QNH / calage altimetrique (informatif)",
     "text": ("Le QNH est un calage altimetrique (information meteo), PAS une commande de "
              "trajectoire : il ne produit aucun ordre BlueSky (HDG/ALT/SPD/ADDWPT)."),
     "example": "qnh one zero one four -> aucun ordre"},

    {"id": "ctx-contact", "action": None,
     "title": "Transfert de frequence (informatif)",
     "text": ("'contact <station> <frequence>' est un transfert radio : hors du jeu d'actions "
              "supporte (HDG/ALT/SPD/ADDWPT) -> ne produit aucun ordre exploitable."),
     "example": "contact approach one one niner decimal seven -> aucun ordre"},

    {"id": "rule-schema", "action": None,
     "title": "Schema et validation de securite",
     "text": (f"Actions supportees : HDG ({_hdg[0]}-{_hdg[1]} deg), ALT ({_alt[0]}-{_alt[1]} ft), "
              f"SPD ({_spd[0]}-{_spd[1]} kt), ADDWPT (wpt). Toute valeur hors bornes ou action "
              f"inconnue doit etre REJETEE (ne pas produire d'ordre). En cas de doute, ne rien produire."),
     "example": "climb flight level nine nine zero -> REJET (99000 ft hors bornes)"},
]


def build_documents():
    """Renvoie la liste des documents a indexer : {id, action, text, example}."""
    docs = []
    for c in CARDS:
        txt = f"{c['title']}. {c['text']} Exemple : {c['example']}"
        docs.append({"id": c["id"], "action": c["action"], "text": txt,
                     "title": c["title"], "example": c["example"]})
    return docs


if __name__ == "__main__":
    docs = build_documents()
    print(f"[kb] {len(docs)} fiches | LIMITS={LIMITS} | waypoints={WAYPOINTS}")
    for d in docs[:3]:
        print(f"  - [{d['action']}] {d['title']}")
