"""
Preuve - Semaine 2 : connecteur RAG (JSON) -> BlueSky (TrafScript)
==================================================================
Le système RAG produit un JSON propre ; cet interpréteur le traduit en
commandes natives BlueSky (API TrafScript, mode headless), cf. rapport S2 :
  HDG    -> changement de cap
  ALT    -> changement d'altitude
  SPD    -> changement de vitesse
  ADDWPT -> ajout d'un point de route

Exécution :  python 03_bluesky_connector.py
Sorties   :  bluesky_demo_output.txt
"""
import json

# --- validation simple des bornes physiques / réglementaires --------------
LIMITS = {
    "HDG": (0, 360, "deg"),
    "ALT": (0, 45000, "ft"),
    "SPD": (0, 350, "kt"),
}


class CommandError(ValueError):
    pass


def json_to_trafscript(order: dict) -> str:
    """Traduit un ordre {callsign, action, value, [wpt]} en ligne TrafScript."""
    cs = order.get("callsign")
    action = (order.get("action") or "").upper()
    if not cs:
        raise CommandError("callsign manquant")

    if action in LIMITS:
        lo, hi, unit = LIMITS[action]
        val = order.get("value")
        if val is None:
            raise CommandError(f"{action}: valeur manquante")
        if not (lo <= val <= hi):
            raise CommandError(f"{action}={val}{unit} hors limites [{lo},{hi}]")
        return f"{action} {cs} {val}"

    if action == "ADDWPT":
        wpt = order.get("wpt")
        if not wpt:
            raise CommandError("ADDWPT: waypoint manquant")
        alt = order.get("value")
        return f"ADDWPT {cs} {wpt}" + (f" {alt}" if alt is not None else "")

    raise CommandError(f"action inconnue : {action!r}")


def translate_batch(orders):
    lines, errors = [], []
    for o in orders:
        try:
            lines.append(json_to_trafscript(o))
        except CommandError as e:
            errors.append((o, str(e)))
    return lines, errors


DEMO = [
    {"callsign": "AFR1234", "action": "HDG", "value": 270},
    {"callsign": "AFR1234", "action": "ALT", "value": 35000},
    {"callsign": "BAW57",   "action": "SPD", "value": 280},
    {"callsign": "DLH88",   "action": "ADDWPT", "wpt": "BALMO", "value": 24000},
    {"callsign": "RYR9",    "action": "ALT", "value": 99000},     # erreur : hors limites
    {"callsign": "EZY12",   "action": "TURN", "value": 10},        # erreur : action inconnue
]


def main():
    print("=== Entrée (JSON produit par le RAG) ===")
    print(json.dumps(DEMO, indent=2, ensure_ascii=False))
    lines, errors = translate_batch(DEMO)

    out = ["# Commandes BlueSky (TrafScript) générées"]
    out += lines
    out.append("")
    out.append("# Ordres rejetés par la validation de sécurité")
    for o, e in errors:
        out.append(f"#  REJET {o.get('callsign')} : {e}")
    text = "\n".join(out)

    print("\n=== Sortie BlueSky ===")
    print(text)
    with open("bluesky_demo_output.txt", "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print("\n[OK] bluesky_demo_output.txt")
    print(f"[OK] {len(lines)} commandes valides, {len(errors)} rejets")


if __name__ == "__main__":
    main()
