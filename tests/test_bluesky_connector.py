"""Tests de 03_bluesky_connector (JSON d'ordre -> ligne TrafScript + validation).

Module a prefixe numerique -> charge via la fixture `bsky_conn` (importlib).
"""
import pytest


# --- json_to_trafscript : traductions correctes ------------------------------
def test_hdg_correct(bsky_conn):
    assert bsky_conn.json_to_trafscript(
        {"callsign": "AFR1234", "action": "HDG", "value": 270}) == "HDG AFR1234 270"


def test_alt_correct(bsky_conn):
    assert bsky_conn.json_to_trafscript(
        {"callsign": "AFR1234", "action": "ALT", "value": 35000}) == "ALT AFR1234 35000"


def test_spd_correct(bsky_conn):
    assert bsky_conn.json_to_trafscript(
        {"callsign": "BAW57", "action": "SPD", "value": 280}) == "SPD BAW57 280"


def test_addwpt_sans_altitude(bsky_conn):
    assert bsky_conn.json_to_trafscript(
        {"callsign": "DLH88", "action": "ADDWPT", "wpt": "BALMO"}) == "ADDWPT DLH88 BALMO"


def test_addwpt_avec_altitude(bsky_conn):
    assert bsky_conn.json_to_trafscript(
        {"callsign": "DLH88", "action": "ADDWPT", "wpt": "BALMO", "value": 24000}) == \
        "ADDWPT DLH88 BALMO 24000"


def test_action_insensible_a_la_casse(bsky_conn):
    assert bsky_conn.json_to_trafscript(
        {"callsign": "AFR1234", "action": "hdg", "value": 100}) == "HDG AFR1234 100"


# --- bornes inclusives -------------------------------------------------------
def test_hdg_borne_haute_inclusive(bsky_conn):
    # 360 est dans [0, 360] -> accepte
    assert bsky_conn.json_to_trafscript(
        {"callsign": "AFR1234", "action": "HDG", "value": 360}) == "HDG AFR1234 360"


def test_hdg_borne_basse_inclusive(bsky_conn):
    assert bsky_conn.json_to_trafscript(
        {"callsign": "AFR1234", "action": "HDG", "value": 0}) == "HDG AFR1234 0"


# --- violations de bornes -> CommandError ------------------------------------
def test_alt_hors_limites(bsky_conn):
    with pytest.raises(bsky_conn.CommandError):
        bsky_conn.json_to_trafscript({"callsign": "RYR9", "action": "ALT", "value": 99000})


def test_spd_hors_limites(bsky_conn):
    with pytest.raises(bsky_conn.CommandError):
        bsky_conn.json_to_trafscript({"callsign": "RYR9", "action": "SPD", "value": 500})


def test_hdg_hors_limites(bsky_conn):
    with pytest.raises(bsky_conn.CommandError):
        bsky_conn.json_to_trafscript({"callsign": "RYR9", "action": "HDG", "value": 400})


# --- erreurs structurelles ---------------------------------------------------
def test_callsign_manquant(bsky_conn):
    with pytest.raises(bsky_conn.CommandError):
        bsky_conn.json_to_trafscript({"action": "HDG", "value": 270})


def test_action_inconnue(bsky_conn):
    with pytest.raises(bsky_conn.CommandError):
        bsky_conn.json_to_trafscript({"callsign": "EZY12", "action": "TURN", "value": 10})


def test_valeur_manquante(bsky_conn):
    with pytest.raises(bsky_conn.CommandError):
        bsky_conn.json_to_trafscript({"callsign": "AFR1234", "action": "HDG"})


def test_addwpt_waypoint_manquant(bsky_conn):
    with pytest.raises(bsky_conn.CommandError):
        bsky_conn.json_to_trafscript({"callsign": "AFR1234", "action": "ADDWPT"})


# --- coercition / validation de type de la valeur ---------------------------
def test_valeur_flottante_arrondie_en_entier(bsky_conn):
    # une valeur flottante ne doit jamais produire une ligne TrafScript decimale
    out = bsky_conn.json_to_trafscript({"callsign": "AFR1", "action": "HDG", "value": 180.0})
    assert out == "HDG AFR1 180" and "." not in out
    out2 = bsky_conn.json_to_trafscript({"callsign": "AFR1", "action": "ALT", "value": 10000.4})
    assert out2 == "ALT AFR1 10000" and "." not in out2


def test_valeur_booleenne_rejetee(bsky_conn):
    # True == 1 en Python : ne doit PAS franchir la borne
    with pytest.raises(bsky_conn.CommandError):
        bsky_conn.json_to_trafscript({"callsign": "AFR1", "action": "HDG", "value": True})


def test_valeur_chaine_rejetee_proprement(bsky_conn):
    # une string ne doit pas lever un TypeError brut mais un CommandError propre
    with pytest.raises(bsky_conn.CommandError):
        bsky_conn.json_to_trafscript({"callsign": "AFR1", "action": "ALT", "value": "35000"})


def test_valeur_non_finie_rejetee(bsky_conn):
    for v in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(bsky_conn.CommandError):
            bsky_conn.json_to_trafscript({"callsign": "AFR1", "action": "ALT", "value": v})


def test_addwpt_altitude_flottante_arrondie(bsky_conn):
    out = bsky_conn.json_to_trafscript(
        {"callsign": "DLH88", "action": "ADDWPT", "wpt": "BALMO", "value": 24000.0})
    assert out == "ADDWPT DLH88 BALMO 24000" and "." not in out


# --- limites declarees -------------------------------------------------------
def test_limits_constantes(bsky_conn):
    assert bsky_conn.LIMITS["ALT"][:2] == (0, 45000)
    assert bsky_conn.LIMITS["SPD"][:2] == (0, 350)
    assert bsky_conn.LIMITS["HDG"][:2] == (0, 360)


# --- translate_batch : separation lignes / erreurs ---------------------------
def test_translate_batch_separe_valides_et_rejets(bsky_conn):
    lines, errors = bsky_conn.translate_batch(bsky_conn.DEMO)
    # DEMO contient 4 ordres valides et 2 invalides (ALT hors limites + action inconnue)
    assert len(lines) == 4
    assert len(errors) == 2
    # chaque erreur = (ordre, message)
    rejected_callsigns = {o.get("callsign") for o, _ in errors}
    assert rejected_callsigns == {"RYR9", "EZY12"}


def test_translate_batch_tout_valide(bsky_conn):
    orders = [
        {"callsign": "AFR1", "action": "HDG", "value": 90},
        {"callsign": "AFR1", "action": "ALT", "value": 10000},
    ]
    lines, errors = bsky_conn.translate_batch(orders)
    assert lines == ["HDG AFR1 90", "ALT AFR1 10000"]
    assert errors == []
