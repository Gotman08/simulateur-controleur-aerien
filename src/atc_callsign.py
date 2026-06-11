"""
Normalisation des indicatifs ATC - robustesse (S5+)
===================================================
Convertit une chaine d'indicatif (telle que transcrite / produite par le LLM)
en indicatif canonique : alphabet phonetique OACI -> lettres, mots-nombres ->
chiffres, telephonie compagnie -> code OACI a 3 lettres.

Donnees standard factuelles (alphabet OACI, indicatifs telephoniques).
"""
import re

PHON = {"alfa": "A", "alpha": "A", "bravo": "B", "charlie": "C", "delta": "D", "echo": "E",
        "foxtrot": "F", "golf": "G", "hotel": "H", "india": "I", "juliet": "J", "juliett": "J",
        "kilo": "K", "lima": "L", "mike": "M", "november": "N", "oscar": "O", "papa": "P",
        "quebec": "Q", "romeo": "R", "sierra": "S", "tango": "T", "uniform": "U", "victor": "V",
        "whiskey": "W", "whisky": "W", "xray": "X", "yankee": "Y", "zulu": "Z"}
DIGI = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "niner": "9"}
# telephonie -> code OACI (cas non ambigus). 'oscar kilo' = prefixe immat. tcheque OK-.
# 'delta' n'est mappe qu'en TETE d'indicatif (Delta Air Lines) ; ailleurs il reste
# la lettre phonetique D (ex. 'csa one delta zulu' -> CSA1DZ), cf. _map_tokens.
AIRLINE = {"air france": "AFR", "speedbird": "BAW", "lufthansa": "DLH", "ryanair": "RYR",
           "easyjet": "EZY", "easy": "EZY", "klm": "KLM", "csa": "CSA", "delta": "DAL",
           "oscar kilo": "OK"}


def _map_tokens(toks):
    out = []
    for t in toks:
        if t in PHON:
            out.append(PHON[t])
        elif t in DIGI:
            out.append(DIGI[t])
        elif re.fullmatch(r"[a-z0-9]+", t):
            out.append(t.upper())
    return "".join(out)


def normalize_callsign(s):
    if not s:
        return ""
    low = s.strip().lower()
    toks = [t for t in re.split(r"[\s_\-]+", low) if t]
    if not toks:
        return s.upper()
    # 1) telephonie compagnie en tete (forme espacee)
    for name in sorted(AIRLINE, key=lambda k: -len(k.split())):
        nw = name.split()
        if toks[:len(nw)] == nw:
            return AIRLINE[name] + _map_tokens(toks[len(nw):])
    # 2) telephonie collee (ex. 'speedbird57', 'lufthansa88')
    if len(toks) == 1:
        for name in sorted(AIRLINE, key=len, reverse=True):
            nm = name.replace(" ", "")
            if low.startswith(nm) and low != nm:
                return AIRLINE[name] + _map_tokens(re.findall(r"[a-z]+|[0-9]+", low[len(nm):]))
    # 3) sequence phonetique / immatriculation
    return _map_tokens(toks) or s.upper()


if __name__ == "__main__":
    tests = [
        "air france one two three four", "speedbird57", "speedbird five seven",
        "lufthansa eight eight", "oscar kilo foxtrot alfa oscar", "csa one delta zulu",
        "AFR1234", "ryanair niner", "oscar_kilo_echo_lima_alfa", "delta402",
    ]
    for t in tests:
        print(f"  {t!r:42s} -> {normalize_callsign(t)}")
