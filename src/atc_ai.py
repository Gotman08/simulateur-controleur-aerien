"""
Client IA hybride - Application d'entrainement ATC
==================================================
Aiguille les requetes IA vers le serveur ROMEO (Whisper / Mistral+RAG / XTTS)
quand le tunnel est ouvert, sinon bascule en REPLI LOCAL 100 % hors-ligne :

  - interpret(texte)  -> ordres ATC {callsign, action, value/wpt} + TrafScript
        ROMEO : POST /interpret (Mistral+RAG)   |  local : parseur regex de phraseologie
  - scenario(texte)   -> liste d'avions a creer {callsign,type,lat,lon,hdg,alt_ft,spd_kt}
        ROMEO : POST /scenario (Mistral)        |  local : generateur de situation
  - asr(wav) / tts(texte) : proxy ROMEO (en repli, c'est le navigateur qui fait STT/TTS)

Le repli reutilise les briques LEGERES du projet (sans charger les modeles lourds) :
  03_bluesky_connector.json_to_trafscript (validation/bornes S2), 04_ner_extraction,
  graph_secteur (fix du secteur), atc_callsign (indicatifs), atc_sim (geometrie).
"""
import os
import re
import math
import importlib.util

import requests

import atc_callsign
from atc_sim import from_nm

_HERE = os.path.dirname(os.path.abspath(__file__))
ROMEO = os.environ.get("ATC_SERVER", "http://localhost:8765")
ROMEO_TTS = os.environ.get("ATC_TTS_SERVER", "http://localhost:8766")


def _load_module(filename, modname):
    """Charge un module a prefixe numerique par chemin (cf. atc_llm._load_module)."""
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


_bsky = _load_module("03_bluesky_connector.py", "bsky_conn")     # validation -> TrafScript
try:
    import graph_secteur
    _GRAPH = graph_secteur.SectorGraph()
except Exception:
    _GRAPH = None


# =============================================================================
#  Outils langage : nombres parles -> chiffres
# =============================================================================
_NUM = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "niner": "9",
        # nombres parles en francais (le repli local est aussi utilise en francais)
        "un": "1", "une": "1", "deux": "2", "trois": "3", "quatre": "4",
        "cinq": "5", "sept": "7", "huit": "8", "neuf": "9"}
_MULT = {"hundred": 100, "thousand": 1000}
_COUNT_WORDS = {"a": 1, "an": 1, "single": 1, "pair": 2, "couple": 2}
# Captures BORNEES : un cap/niveau ne doit pas absorber le nombre du champ suivant
# (ex. 'heading 1 8 0 8 miles' -> cap=180, pas 1808). Les nombres ATC sont epeles
# chiffre par chiffre (cap=3, FL=2-3, vitesse=2-3) ou en entier compact.
_N_LEVEL = r"(\d\s+\d\s+\d|\d\s+(?:hundred|thousand)|\d\s+\d|\d{2,5}|\d)"   # FL / altitude
_N_DEG = r"(\d\s+\d\s+\d|\d\s+\d|\d{2,3}|\d{1,2})"                          # cap / vitesse
_N_SMALL = r"(\d\s+\d|\d{1,2})"                                            # nombre / espacement
NUMSEQ = r"(\d+(?:\s+\d+)*(?:\s+(?:hundred|thousand))?)"
_ACTION_KW = re.compile(
    r"\b(turn|fly|heading|hdg|climb|climbing|descend|descending|descent|maintain|"
    r"reduce|increase|speed|direct|proceed|contact|cleared|continue|expedite|"
    # verbes/mots-cles francais (l'eleve peut parler/taper en francais)
    r"monte[zr]|descende[zr]|descendre|maintene[zr]|maintenir|cap|tourne[zr]|vire[zr]|"
    r"vitesse|r[ée]duise[zr]|augmente[zr])\b", re.I)


def _normalize_numbers(text):
    """Remplace les mots-nombres par leur chiffre, en gardant les espaces
    ('descend flight level one zero zero' -> 'descend flight level 1 0 0')."""
    parts = re.split(r"(\s+)", str(text or "").lower())
    return "".join(_NUM.get(p, p) for p in parts)


def _to_int(s):
    """'2 7 0'->270, '1 0 0'->100, '5 thousand'->5000, '1 hundred'->100, '250'->250."""
    s = (s or "").strip()
    m = re.match(r"^(\d+(?:\s+\d+)*)\s+(hundred|thousand)$", s)
    if m:
        base = int(re.sub(r"\s+", "", m.group(1)))
        return base * _MULT[m.group(2)]
    compact = re.sub(r"\s+", "", s)
    return int(compact) if compact.isdigit() else int(re.sub(r"\D", "", s) or 0)


# =============================================================================
#  REPLI LOCAL : interpretation d'une clairance
# =============================================================================
def _parse_alt(instr):
    orders = []
    pat = (r"\b(climb|climbing|descend|descending|descent|maintain|"
           r"monte[zr]|descende[zr]|descendre|maintene[zr]|maintenir)\b"
           r"(?:\s+(?:to|au|a|à|vers))?\s*"
           r"(flight\s+level|fl|altitude|level|niveau(?:\s+de\s+vol)?)?\s*"
           + _N_LEVEL + r"\s*(feet|ft|pieds)?")
    for m in re.finditer(pat, instr, re.I):
        verb, lvl, num, ft = (g.lower() if g else g for g in m.groups())
        v = _to_int(num)
        if v <= 0:
            continue
        if verb in ("maintain", "maintenir", "maintenez", "maintener") and not lvl and not ft:
            continue                                   # 'maintain N' seul -> ambigu (vitesse)
        is_fl = (lvl is not None and lvl != "altitude") or (not ft and not lvl and v <= 450)
        orders.append({"action": "ALT", "value": int(v * 100 if is_fl else v)})
    return orders


def _parse_hdg(instr):
    orders, seen = [], set()
    for pat in (r"\b(?:turn\s+(?:left|right)\s+)?(?:fly\s+)?(?:heading|hdg)\s+" + _N_DEG,
                r"\bturn\s+(?:left|right)\s+" + _N_DEG,
                # francais : 'cap 180', 'tournez a droite cap 270', 'virez a gauche 090'
                r"\b(?:tourne[zr]|vire[zr])?\s*(?:[aà]\s+)?(?:droite|gauche)?\s*\bcap\s+" + _N_DEG,
                r"\b(?:tourne[zr]|vire[zr])\s+(?:[aà]\s+)?(?:droite|gauche)\s+" + _N_DEG):
        for m in re.finditer(pat, instr, re.I):
            v = int(_to_int(m.group(1)))
            if v not in seen:
                seen.add(v)
                orders.append({"action": "HDG", "value": v})
    return orders


def _parse_spd(instr):
    orders, seen = [], set()
    for pat in (r"\b(?:reduce\s+speed|increase\s+speed|reduce|increase|speed|"
                r"vitesse|r[ée]duise[zr](?:\s+vitesse)?|augmente[zr](?:\s+vitesse)?)\s+(?:to\s+|[aà]\s+)?"
                + _N_DEG + r"(?:\s*(?:knots|kts|kt|n[oœ]euds))?",
                _N_DEG + r"\s*(?:knots|kts|kt|n[oœ]euds)\b"):
        for m in re.finditer(pat, instr, re.I):
            v = int(_to_int(m.group(1)))
            if 0 < v and v not in seen:
                seen.add(v)
                orders.append({"action": "SPD", "value": v})
    return orders


def _parse_direct(instr):
    orders = []
    for m in re.finditer(r"\b(?:proceed\s+)?direct(?:\s+to)?\s+([a-z][a-z0-9_]+)", instr, re.I):
        orders.append({"action": "ADDWPT", "wpt": m.group(1).upper()})
    return orders


def _extract_callsign(text_norm):
    m = _ACTION_KW.search(text_norm)
    phrase = text_norm[:m.start()] if m else ""
    instr = text_norm[m.start():] if m else ""
    return (atc_callsign.normalize_callsign(phrase.strip()) or None), instr


def local_interpret(text):
    """Parseur de phraseologie hors-ligne. Meme format de sortie que /interpret."""
    raw = re.sub(r"[,;]", " ", str(text or ""))
    norm = _normalize_numbers(raw)
    cs, instr = _extract_callsign(norm)
    orders, trafscript, rejected = [], [], []
    parsed = _parse_alt(instr) + _parse_hdg(instr) + _parse_spd(instr) + _parse_direct(instr)
    if parsed and not cs:
        rejected.append("indicatif non reconnu")
        parsed = []
    for o in parsed:
        o["callsign"] = cs
        if o["action"] == "ADDWPT" and _GRAPH is not None:
            w = o.get("wpt", "")
            if not _GRAPH.is_fix(w):
                cand = w.replace("_", "")
                match = next((f for f in _GRAPH.fixes() if f.replace("_", "") == cand), None)
                if match:
                    o["wpt"] = match
                else:
                    rejected.append(f"waypoint '{w}' inconnu du secteur")
                    continue
        # un ordre invalide (bornes, action inconnue) est REJETE et ne doit ni
        # etre execute ni etre collationne par le pilote -> orders reste coherent
        # avec trafscript.
        try:
            line = _bsky.json_to_trafscript(o)
        except Exception as e:
            rejected.append(str(e))
            continue
        orders.append(o)
        trafscript.append(line)
    # Taux de montee/descente (VS, fpm) : 'expedite' ou 'rate N' / 'N feet per minute'.
    # Le signe vient du verbe (descend -> negatif).
    if cs:
        rate = None
        if re.search(r"\bexpedite\b", instr, re.I):
            rate = 3000
        else:
            mr = (re.search(r"(?:rate|taux)\s+" + _N_LEVEL, instr, re.I)
                  or re.search(_N_LEVEL + r"\s*(?:feet\s*per\s*minute|fpm|ft\s*/?\s*min)", instr, re.I))
            if mr:
                rate = _to_int(mr.group(1))
        if rate and rate > 0:
            sign = -1 if re.search(r"descend|descending|descent|descendre", instr, re.I) else 1
            trafscript.append(f"VS {cs} {sign * rate}")
    return {"text": text, "orders": orders, "trafscript": trafscript,
            "rejected": rejected, "cited": []}


# =============================================================================
#  REPLI LOCAL : generation de situation (langage naturel -> avions)
# =============================================================================
_DIR = {"north east": 45, "northeast": 45, "north west": 315, "northwest": 315,
        "south east": 135, "southeast": 135, "south west": 225, "southwest": 225,
        "north": 0, "east": 90, "south": 180, "west": 270,
        "nord est": 45, "nord ouest": 315, "sud est": 135, "sud ouest": 225,
        "nord": 0, "est": 90, "sud": 180, "ouest": 270}
_TYPE_PAT = re.compile(
    r"\b(a31[89]|a320|a321|a32[01]neo|a33[023]|a34[3]|a35[09]|a38[08]|"
    r"b73[2-9]|b74[4789]|b75[27]|b76[37]|b77[7w]|b78[789]|e1[79][05]|crj[79])\b", re.I)
_SAFE_TYPES = {"A318", "A319", "A320", "A321", "A332", "A333", "A343", "A359", "A388",
               "B737", "B738", "B739", "B744", "B748", "B752", "B763", "B77W", "B788",
               "B789", "E170", "E190", "E195", "CRJ9"}
#: variantes generiques -> type connu de la base de performances BlueSky
_TYPE_ALIAS = {"A330": "A332", "A350": "A359", "A380": "A388",
               "B747": "B744", "B777": "B77W", "B787": "B788"}
_AIRLINES = ["AFR", "BAW", "DLH", "RYR", "EZY", "KLM", "BEL", "TAP", "SAS", "IBE", "AEE", "VLG"]
_DEF_BASE_NM = 38.0       # distance initiale au centre secteur
_DEF_SPACING = 8.0


def _gen_callsign(i):
    return f"{_AIRLINES[i % len(_AIRLINES)]}{100 + i}"


def _detect_type(cn):
    m = _TYPE_PAT.search(cn)
    if not m:
        return "A320"
    t = m.group(1).upper().replace("NEO", "N")
    t = _TYPE_ALIAS.get(t, t)
    return t if t in _SAFE_TYPES else "A320"


def _consume(cn, pat):
    """Cherche pat (groupe 1 = NUMSEQ), retourne (valeur|None, cn sans le motif)."""
    m = re.search(pat, cn, re.I)
    if not m:
        return None, cn
    val = _to_int(m.group(1))
    return val, (cn[:m.start()] + " " + cn[m.end():])


def _parse_clause(clause, start_idx):
    cn = _normalize_numbers(clause)
    # FL/altitude (prefixe), puis le cap (capture bornee a 3 chiffres : il ne deborde
    # pas sur le nombre suivant), puis vitesse et espacement (ancres par leur unite).
    alt_ft, cn = _consume(cn, r"(?:flight\s+level|fl|niveau)\s*" + _N_LEVEL)
    if alt_ft is not None:
        alt_ft *= 100
    if alt_ft is None:
        feet, cn = _consume(cn, _N_LEVEL + r"\s*(?:feet|ft)\b")
        alt_ft = feet
    hdg, cn = _consume(cn, r"(?:heading|hdg|cap)\s+" + _N_DEG)
    spd, cn = _consume(cn, _N_DEG + r"\s*(?:knots|kts|kt|noeuds)\b")
    if spd is None:
        spd, cn = _consume(cn, r"(?:speed|vitesse)\s+" + _N_DEG)
    spacing, cn = _consume(cn, _N_SMALL + r"\s*(?:nm|nautical\s+miles?|miles?|mile|milles?)"
                                       r"(?:\s*(?:apart|in\s+trail|spacing|separation|d'\s*ecart))?")
    bearing = next((b for k, b in sorted(_DIR.items(), key=lambda kv: -len(kv[0])) if k in cn), None)
    actype = _detect_type(clause)

    mc = re.search(r"\b(\d{1,2})\b", cn)
    count = int(mc.group(1)) if mc else None
    if count is None:
        count = next((v for w, v in _COUNT_WORDS.items() if re.search(rf"\b{w}\b", cn)), 1)
    count = max(1, min(12, count))

    alt_ft = alt_ft if alt_ft else 28000
    spd = spd if spd else 250
    spacing = spacing if spacing else _DEF_SPACING
    b = bearing if bearing is not None else 270
    inbound = (b + 180) % 360
    out = []
    for i in range(count):
        dist = _DEF_BASE_NM + i * spacing
        dx = dist * math.sin(math.radians(b))
        dy = dist * math.cos(math.radians(b))
        lat, lon = from_nm(dx, dy)
        out.append({"callsign": _gen_callsign(start_idx + i), "type": actype,
                    "lat": lat, "lon": lon,
                    "hdg": float(hdg if hdg is not None else inbound),
                    "alt_ft": float(alt_ft), "spd_kt": float(spd)})
    return out


def local_scenario(description):
    """Genere des avions a partir d'une description en langage naturel."""
    text = re.sub(r"[,;.]", " ", str(description or "")).lower()
    clauses = [c for c in re.split(r"\b(?:and|then|plus|et|puis)\b", text) if c.strip()]
    base = sum(ord(c) for c in text) % 700        # indicatifs varies selon la description
    aircraft, idx = [], base
    for clause in (clauses or [text]):
        for ac in _parse_clause(clause, idx):
            aircraft.append(ac)
            idx += 1
    if not aircraft:
        aircraft = _parse_clause("one a320 from the west at fl240", base)
    return aircraft


def _items_to_aircraft(items):
    """Normalise la sortie ROMEO /scenario (bearing/dist ou lat/lon) -> avions."""
    out = []
    for it in items or []:
        try:
            if it.get("lat") is not None and it.get("lon") is not None:
                lat, lon = float(it["lat"]), float(it["lon"])
            else:
                b = float(it.get("bearing_deg", 270))
                d = float(it.get("dist_nm", _DEF_BASE_NM))
                lat, lon = from_nm(d * math.sin(math.radians(b)), d * math.cos(math.radians(b)))
            cs = str(it.get("callsign", "")).upper().strip() or _gen_callsign(len(out))
            t = str(it.get("type", "A320")).upper().strip()
            out.append({"callsign": cs, "type": t if t in _SAFE_TYPES else "A320",
                        "lat": lat, "lon": lon, "hdg": float(it.get("hdg") or 0),
                        "alt_ft": float(it.get("alt_ft") or 20000),
                        "spd_kt": float(it.get("spd_kt") or 250)})
        except Exception:
            continue
    return out


# =============================================================================
#  Client : aiguillage ROMEO / local
# =============================================================================
class AIClient:
    def __init__(self):
        self._caps = {"romeo": False, "asr": False, "llm": False, "tts": False}
        self.refresh_health()

    def refresh_health(self):
        caps = {"romeo": False, "asr": False, "llm": False, "tts": False}
        try:
            j = requests.get(ROMEO + "/health", timeout=3).json()
            caps["romeo"] = True
            caps["asr"] = j.get("role") in ("all", "asrllm")
            caps["llm"] = j.get("role") in ("all", "asrllm")
        except Exception:
            pass
        try:
            caps["tts"] = requests.get(ROMEO_TTS + "/health", timeout=3).ok
        except Exception:
            pass
        self._caps = caps
        return caps

    def caps(self):
        return dict(self._caps)

    def mode(self):
        return "romeo" if self._caps.get("llm") else "local"

    def interpret(self, text):
        if self._caps.get("llm"):
            try:
                r = requests.post(ROMEO + "/interpret", json={"text": text}, timeout=60)
                r.raise_for_status()
                j = r.json()
                j.setdefault("orders", [])
                j.setdefault("trafscript", [])
                j.setdefault("rejected", [])
                j.setdefault("cited", [])
                return j
            except Exception:
                pass
        return local_interpret(text)

    def scenario(self, description):
        if self._caps.get("llm"):
            try:
                r = requests.post(ROMEO + "/scenario", json={"description": description}, timeout=90)
                r.raise_for_status()
                ac = _items_to_aircraft(r.json().get("aircraft", []))
                if ac:
                    return ac
            except Exception:
                pass
        return local_scenario(description)

    def asr(self, wav_bytes):
        r = requests.post(ROMEO + "/asr",
                          files={"file": ("utt.wav", wav_bytes, "audio/wav")}, timeout=60)
        r.raise_for_status()
        return r.json().get("text", "")

    def tts(self, text, voice=None):
        payload = {"text": text, "vhf": True}
        if voice:
            payload["voice"] = voice
        r = requests.post(ROMEO_TTS + "/tts", json=payload, timeout=120)
        r.raise_for_status()
        return r.content


if __name__ == "__main__":
    print("=== interpret (repli local) ===")
    for t in ["air france one two three four descend flight level one zero zero",
              "speedbird five seven turn right heading two seven zero",
              "csa one delta zulu climb flight level two four zero reduce speed two five zero",
              "ryanair niner proceed direct delta"]:
        r = local_interpret(t)
        print(f"  {t!r}\n     -> {r['trafscript']}  rejets={r['rejected']}")
    print("\n=== scenario (repli local) ===")
    for d in ["three A320 from the north at FL300 heading 180, 8 miles apart",
              "two B738 from the south at flight level 240 and one A319 from the west at fl120",
              "trois A320 venant du nord au niveau 300 cap 180 espaces de 8 milles"]:
        ac = local_scenario(d)
        print(f"  {d!r}")
        for a in ac:
            print(f"     {a['callsign']} {a['type']} hdg={a['hdg']:.0f} FL{int(a['alt_ft']/100):03d} "
                  f"@({a['lat']:.3f},{a['lon']:.3f})")
