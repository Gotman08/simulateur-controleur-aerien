"""
Helpers RAG + LLM - Semaine 5
=============================
- Retriever : recherche cosinus (numpy) sur l'index KB (bge-small).
- LLM Mistral : prompt strict -> tableau JSON d'ordres {callsign, action, value, [wpt]}.
- Reutilise la validation S2 (03_bluesky_connector.json_to_trafscript) et le NER S2 (04).

Utilise par 12 (retrieval), 13 (interpret), 14 (eval), 15 (pipeline).
"""
import os
import re
import json
import importlib.util

import numpy as np

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
# datasets / whisper / embedder -> cache SCRATCH ; le gros LLM Mistral -> cache PROJET
# (chacun dans sa partition de 20 Go ; on evite de tout entasser au meme endroit).
os.environ.setdefault("HF_HOME", os.path.join(WORK, "hf_cache"))
PROJET_CACHE = os.environ.get("ATC_LLM_CACHE", "/gpfs/projet/r250127/hf_cache/hub")
_HERE = os.path.dirname(os.path.abspath(__file__))
EMB_ID = os.environ.get("ATC_EMB", "BAAI/bge-small-en-v1.5")
LLM_ID = os.environ.get("ATC_LLM", "mistralai/Mistral-7B-Instruct-v0.3")
KB_DIR = os.path.join(WORK, "kb")


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


_bsky = _load_module("03_bluesky_connector.py", "bsky_conn")   # validation + TrafScript (S2)
_ner = _load_module("04_ner_extraction.py", "ner_extr")        # NER (S2)

try:
    import graph_secteur
    _GRAPH = graph_secteur.SectorGraph()       # graphe secteur (S2) : validation fix + contexte
except Exception:
    _GRAPH = None

import atc_callsign                            # normalisation des indicatifs (robustesse)


def ner_extract(text):
    if _ner and hasattr(_ner, "extract"):
        try:
            return _ner.extract(text)
        except Exception:
            pass
    return {"text": text, "callsign": None, "entities": []}


_validateur_alerte = False


def validate_order(order):
    """(ok, trafscript|erreur) via la validation de securite S2 (bornes, actions)."""
    global _validateur_alerte
    if _bsky and hasattr(_bsky, "json_to_trafscript"):
        try:
            return True, _bsky.json_to_trafscript(order)
        except Exception as e:
            return False, str(e)
    if not _validateur_alerte:
        # sans le validateur, 100 % des ordres sont rejetes : l'app "tourne"
        # mais n'execute plus rien - on le dit UNE fois, fort.
        import logging
        logging.getLogger("atc_llm").error(
            "03_bluesky_connector introuvable : TOUT ordre sera rejete "
            "(« validateur S2 indisponible ») - verifier l'installation")
        _validateur_alerte = True
    return False, "validateur S2 indisponible"


# --- Retrieval -----------------------------------------------------------
class Retriever:
    def __init__(self, kb_dir=KB_DIR, emb_id=EMB_ID):
        with open(os.path.join(kb_dir, "docs.json"), encoding="utf-8") as f:
            meta = json.load(f)
        self.docs = meta["docs"]
        self.qinstr = meta.get("query_instruction", "")
        self.emb = np.load(os.path.join(kb_dir, "embeddings.npy")).astype("float32")
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(emb_id)

    def retrieve(self, query, k=4):
        q = self.model.encode([f"{self.qinstr} {query}".strip()],
                              normalize_embeddings=True, convert_to_numpy=True)[0]
        sims = self.emb @ q                       # embeddings normalises -> cosinus
        idx = np.argsort(-sims)[:k]
        return [(self.docs[i], float(sims[i])) for i in idx]


# --- LLM (Mistral) -------------------------------------------------------
_LLM = {}


def load_llm(llm_id=LLM_ID):
    if "m" not in _LLM:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        _LLM["t"] = AutoTokenizer.from_pretrained(llm_id, cache_dir=PROJET_CACHE)
        _LLM["m"] = AutoModelForCausalLM.from_pretrained(
            llm_id, torch_dtype=torch.bfloat16, device_map="cuda", cache_dir=PROJET_CACHE)
    return _LLM["t"], _LLM["m"]


SYSTEM = (
    "You are an air traffic control (ATC) command interpreter. "
    "Convert the controller transcription into a JSON ARRAY of orders. "
    "Each order is an object: {\"callsign\": string, \"action\": one of "
    "\"HDG\"|\"ALT\"|\"SPD\"|\"ADDWPT\", \"value\": number, and \"wpt\": string only for ADDWPT}. "
    "Conversion rules: spelled-out numbers -> integer; 'flight level' N or FLxxx -> action ALT with "
    "value = N*100 (feet); heading is in degrees (HDG); speed in knots (SPD). "
    "Use ONLY those four actions. Omit purely informational items (QNH, altimeter, 'contact <freq>', "
    "read-backs). Omit any order whose value is out of range (HDG 0-360, ALT 0-45000, SPD 0-350). "
    "Ground every order in the provided rules. Output ONLY the JSON array, no prose, no code fences. "
    "If nothing is actionable, output []. "
    "For callsigns, use the ICAO airline code + flight number (air france=AFR, speedbird=BAW, "
    "lufthansa=DLH, ryanair=RYR, easyjet=EZY, klm=KLM); otherwise spell the registration with the "
    "phonetic alphabet as letters (alfa=A, bravo=B, ... zulu=Z)."
)


def build_messages(transcription, retrieved, ner):
    rules = "\n".join(f"- {d['title']}: {d['text']}" for d, _ in retrieved)
    cs = ner.get("callsign")
    orders = [e for e in ner.get("entities", []) if e.get("type") == "ORDER"]
    hint = f"callsign={cs}; intentions_detectees={[o.get('name') for o in orders]}"
    sector = (f"Sector graph: {_GRAPH.topology_text()}\n\n" if _GRAPH is not None else "")
    user = (f"Applicable ICAO phraseology rules:\n{rules}\n\n"
            f"{sector}"
            f"NER hints: {hint}\n\n"
            f"Controller transcription: \"{transcription}\"\n\n"
            "Return ONLY the JSON array of orders.")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def generate_from_messages(messages, max_new_tokens=256):
    """Generation brute a partir de messages chat arbitraires (role system/user).
    Utilise par la facade OpenAI-compatible (server.py /v1/chat/completions)."""
    tok, model = load_llm()
    enc = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt",
                                  return_dict=True).to(model.device)
    out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False)
    return tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)


def generate_text(transcription, retrieved, ner, max_new_tokens=256):
    return generate_from_messages(build_messages(transcription, retrieved, ner),
                                  max_new_tokens=max_new_tokens)


def _fix_leading_zeros(blob):
    """Nombres JSON a zero de tete ('"value": 090') -> valides ('90').
    Les LLM produisent volontiers des caps a trois chiffres (heading 090) ;
    json.loads rejette ces litteraux. On ne touche qu'aux nombres NUS apres
    ':' / '[' / ',' - jamais au contenu des chaines ("ENTRY_090" intact)."""
    return re.sub(r"([:\[,]\s*)0+(\d)", r"\g<1>\g<2>", blob)


def parse_orders(text):
    """Extrait un tableau JSON d'ordres, tolerant (code fences, prose autour,
    objets isoles, zeros de tete)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    m = re.search(r"\[.*\]", t, re.S)
    blob = m.group(0) if m else t
    try:
        data = json.loads(blob)
    except Exception:
        try:
            data = json.loads(_fix_leading_zeros(blob))
        except Exception:
            data = []
            for o in re.findall(r"\{[^{}]*\}", t, re.S):
                try:
                    data.append(json.loads(_fix_leading_zeros(o)))
                except Exception:
                    pass
    if isinstance(data, dict):
        data = [data]
    return data if isinstance(data, list) else []


def postprocess_orders(orders):
    """Post-traitement PUR de la sortie LLM : normalisation des indicatifs,
    validation ADDWPT contre le graphe secteur, validation de securite (03).
    -> (valid=[{order, trafscript}], rejected=[{order, erreur}]).
    Sans GPU : reutilisable par le client API (ai_client) comme par interpret()."""
    valid, rejected = [], []
    for o in orders:
        if not isinstance(o, dict):
            rejected.append({"order": o, "erreur": "format invalide"})
            continue
        o = dict(o)                        # copie : pas d'effet de bord sur l'appelant
        if o.get("callsign"):
            o["callsign"] = atc_callsign.normalize_callsign(str(o["callsign"]))   # indicatif canonique
        # validation graphe : un ADDWPT doit cibler un fix CONNU du secteur
        if str(o.get("action", "")).upper() == "ADDWPT" and _GRAPH is not None:
            wpt = str(o.get("wpt", "")).strip()
            if not _GRAPH.is_fix(wpt):
                cand = wpt.upper().replace("_", "").replace(" ", "")
                match = next((f for f in _GRAPH.fixes() if f.replace("_", "") == cand), None)
                if match:
                    o["wpt"] = match               # normalisation vers le fix connu
                else:
                    rejected.append({"order": o, "erreur": f"waypoint '{wpt}' inconnu du secteur"})
                    continue
        ok, res = validate_order(o)
        if ok:
            # aligner la valeur de l'ordre sur l'ENTIER coerce du TrafScript
            # (source unique) : le JSON LLM peut porter 32000.0 la ou la ligne
            # dit 32000 - les consommateurs aval (readback, garde-fous)
            # comparent alors des types coherents.
            if str(o.get("action", "")).upper() in ("HDG", "ALT", "SPD"):
                o["value"] = int(res.split()[2])
            valid.append({"order": o, "trafscript": res})
        else:
            rejected.append({"order": o, "erreur": res})
    return valid, rejected


def interpret(text, retriever, k=4, max_new_tokens=256):
    """transcription -> {orders, valid(+trafscript), rejected(+erreur), cited, raw}.
    NER (04) + retrieval + LLM + validation de securite (03). Reutilise par 14/15."""
    ner = ner_extract(text)
    retrieved = retriever.retrieve(text, k=k)
    raw = generate_text(text, retrieved, ner, max_new_tokens=max_new_tokens)
    orders = parse_orders(raw)
    valid, rejected = postprocess_orders(orders)
    return {"text": text, "orders": orders, "valid": valid, "rejected": rejected,
            "cited": [d["id"] for d, _ in retrieved], "raw": raw}


# --- Generation de situation (instructeur -> avions a creer) --------------
SCENARIO_SYSTEM = (
    "You are an air traffic control training scenario generator. "
    "From the instructor's free-text description, output a JSON ARRAY of aircraft to spawn "
    "in the sector. Each aircraft is an object: "
    "{\"callsign\": ICAO airline code + flight number (e.g. AFR1234), "
    "\"type\": ICAO aircraft type designator (A320, A319, A321, B737, B738, E190, A333...), "
    "\"bearing_deg\": integer 0-359, bearing of the aircraft POSITION from the sector center "
    "(0=North, 90=East, 180=South, 270=West), "
    "\"dist_nm\": integer 20-60, distance from the sector center, "
    "\"hdg\": integer 0-359, the aircraft heading in degrees, "
    "\"alt_ft\": integer altitude in feet (flight level x 100, e.g. FL300 -> 30000), "
    "\"spd_kt\": integer ground speed in knots}. "
    "If a count is given ('three aircraft'), output exactly that many, separated along the radial. "
    "If a direction is given ('from the north'), set bearing_deg to it and head them toward the "
    "center unless a heading is stated. Use realistic distinct callsigns. "
    "Output ONLY the JSON array, no prose, no code fences."
)


def build_scenario_messages(description):
    sector = (f"Sector context: {_GRAPH.topology_text()}\n\n" if _GRAPH is not None else "")
    user = (f"{sector}Instructor description: \"{description}\"\n\n"
            "Return ONLY the JSON array of aircraft.")
    return [{"role": "system", "content": SCENARIO_SYSTEM}, {"role": "user", "content": user}]


def _num_or(v, default):
    """float(v) tolerant : None / chaine invalide -> valeur par defaut.
    Un LLM qui renvoie un champ null ne doit pas faire disparaitre l'avion
    entier - seul le champ fautif retombe sur son defaut."""
    try:
        f = float(v)
        return f if f == f else default        # NaN -> defaut
    except (TypeError, ValueError):
        return default


def clean_scenario_items(items):
    """Nettoyage PUR de la sortie LLM scenario : normalisation des indicatifs
    + bornes (bearing/dist/alt/spd). Sans GPU : reutilisable par ai_client."""
    clean = []
    for it in items:
        if not isinstance(it, dict):
            continue
        cs = atc_callsign.normalize_callsign(str(it.get("callsign") or ""))
        if not cs:
            continue
        clean.append({
            "callsign": cs,
            "type": str(it.get("type") or "A320").upper(),
            "bearing_deg": int(_num_or(it.get("bearing_deg"), 270)) % 360,
            "dist_nm": max(10.0, min(65.0, _num_or(it.get("dist_nm"), 40))),
            "hdg": int(_num_or(it.get("hdg"), 0)) % 360,
            "alt_ft": max(1000.0, min(45000.0, _num_or(it.get("alt_ft"), 24000))),
            "spd_kt": max(120.0, min(350.0, _num_or(it.get("spd_kt"), 280))),
        })
    return clean


def scenario_from_description(description, max_new_tokens=512):
    """Description en langage naturel -> liste d'avions {callsign,type,bearing_deg,
    dist_nm,hdg,alt_ft,spd_kt} (bornes appliquees). Conversion en lat/lon cote local."""
    raw = generate_from_messages(build_scenario_messages(description),
                                 max_new_tokens=max_new_tokens)
    return clean_scenario_items(parse_orders(raw))
