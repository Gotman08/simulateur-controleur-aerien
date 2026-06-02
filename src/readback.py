"""
Generation du collationnement pilote (readback) - phraseologie OACI
===================================================================
A partir des ordres JSON (du pipeline), produit le texte de READBACK que le
pilote prononce : repetition de l'instruction + indicatif en telephonie.
Ex. {AFR1234, ALT, 10000} (avion a FL130) -> "descend flight level one zero zero, air france one two three four".
Donnees standard (chiffres parles, alphabet OACI, indicatifs telephoniques).
"""
import re

WORD = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
        "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "niner"}
LETTER = {"A": "alfa", "B": "bravo", "C": "charlie", "D": "delta", "E": "echo",
          "F": "foxtrot", "G": "golf", "H": "hotel", "I": "india", "J": "juliet",
          "K": "kilo", "L": "lima", "M": "mike", "N": "november", "O": "oscar",
          "P": "papa", "Q": "quebec", "R": "romeo", "S": "sierra", "T": "tango",
          "U": "uniform", "V": "victor", "W": "whiskey", "X": "xray", "Y": "yankee", "Z": "zulu"}
CODE2TEL = {"AFR": "air france", "BAW": "speedbird", "DLH": "lufthansa", "RYR": "ryanair",
            "EZY": "easyjet", "KLM": "klm", "AAL": "american", "UAL": "united", "DAL": "delta"}


def num_words(s):
    return " ".join(WORD.get(c, c) for c in str(s))


def spell(s):
    return " ".join(LETTER.get(c.upper(), c) for c in str(s) if c.isalnum())


def callsign_telephony(cs):
    m = re.match(r"^([A-Z]{2,3})(\d+)$", cs or "")
    if m and m.group(1) in CODE2TEL:
        return f"{CODE2TEL[m.group(1)]} {num_words(m.group(2))}"
    out = []
    for ch in (cs or ""):
        if ch.isdigit():
            out.append(WORD[ch])
        elif ch.isalpha():
            out.append(LETTER.get(ch.upper(), ch))
    return " ".join(out)


def readback_for_order(o, cur_alt_ft=None):
    a = str(o.get("action", "")).upper()
    if a == "ALT":
        v = int(o.get("value", 0))
        verb = "descend" if (cur_alt_ft is not None and v < cur_alt_ft) else "climb"
        return f"{verb} flight level {num_words(str(v // 100).zfill(3))}"
    if a == "HDG":
        return f"heading {num_words(str(int(o.get('value', 0))).zfill(3))}"
    if a == "SPD":
        return f"speed {num_words(int(o.get('value', 0)))} knots"
    if a == "ADDWPT":
        return f"proceed direct {spell(o.get('wpt', ''))}"
    return ""


def readback_text(orders, cur_alt=None):
    cur_alt = cur_alt or {}
    if not orders:
        return ""
    cs = orders[0].get("callsign", "")
    phr = [p for p in (readback_for_order(o, cur_alt.get(cs)) for o in orders) if p]
    if not phr:
        return ""
    return ", ".join(phr) + ", " + callsign_telephony(cs)


if __name__ == "__main__":
    print(readback_text([{"callsign": "AFR1234", "action": "ALT", "value": 10000}], {"AFR1234": 13000}))
    print(readback_text([{"callsign": "BAW57", "action": "HDG", "value": 180}]))
    print(readback_text([{"callsign": "RYR9", "action": "ALT", "value": 24000}], {"RYR9": 9000}))
