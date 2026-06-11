"""Tests de readback (generation du collationnement pilote, phraseologie OACI)."""
from readback import (num_words, spell, callsign_telephony,
                      readback_for_order, readback_text)


# --- num_words / spell -------------------------------------------------------
def test_num_words_chaine():
    assert num_words("100") == "one zero zero"


def test_num_words_int():
    # 9 est rendu 'niner' (convention OACI dans la table WORD)
    assert num_words(270) == "two seven zero"
    assert num_words(9) == "niner"


def test_spell_waypoint():
    assert spell("BALMO") == "bravo alfa lima mike oscar"


# --- callsign_telephony ------------------------------------------------------
def test_callsign_telephony_code_connu():
    assert callsign_telephony("AFR1234") == "air france one two three four"


def test_callsign_telephony_baw():
    assert callsign_telephony("BAW57") == "speedbird five seven"


def test_callsign_telephony_code_inconnu_epele_caractere():
    # code non mappe -> epellation caractere par caractere
    assert callsign_telephony("XXX12") == "xray xray xray one two"


# --- readback_for_order : ALT climb vs descend -------------------------------
def test_alt_descend_si_altitude_courante_superieure():
    # avion a 13000 ft, ordre FL100 (10000 ft) -> descend
    assert readback_for_order({"action": "ALT", "value": 10000}, 13000) == \
        "descend flight level one zero zero"


def test_alt_climb_si_altitude_courante_inferieure():
    assert readback_for_order({"action": "ALT", "value": 10000}, 5000) == \
        "climb flight level one zero zero"


def test_alt_climb_par_defaut_sans_altitude_courante():
    # sans altitude courante connue, le verbe par defaut est 'climb'
    assert readback_for_order({"action": "ALT", "value": 10000}) == \
        "climb flight level one zero zero"


# --- readback_for_order : HDG / SPD / ADDWPT ---------------------------------
def test_hdg_zero_padde_sur_trois_chiffres():
    # cap 90 -> '090' epele
    assert readback_for_order({"action": "HDG", "value": 90}) == \
        "heading zero niner zero"


def test_hdg_trois_chiffres():
    assert readback_for_order({"action": "HDG", "value": 270}) == \
        "heading two seven zero"


def test_spd_avec_knots():
    assert readback_for_order({"action": "SPD", "value": 250}) == \
        "speed two five zero knots"


def test_addwpt_epelle_le_fix():
    assert readback_for_order({"action": "ADDWPT", "wpt": "BALMO"}) == \
        "proceed direct bravo alfa lima mike oscar"


def test_action_inconnue_renvoie_vide():
    assert readback_for_order({"action": "ZZZ"}) == ""


# --- readback_text : assemblage complet --------------------------------------
def test_readback_text_simple_avec_telephonie():
    txt = readback_text([{"callsign": "AFR1234", "action": "ALT", "value": 10000}],
                        {"AFR1234": 13000})
    assert txt == "descend flight level one zero zero, air france one two three four"


def test_readback_text_ordres_multiples():
    txt = readback_text([
        {"callsign": "AFR1234", "action": "HDG", "value": 270},
        {"callsign": "AFR1234", "action": "SPD", "value": 250},
    ])
    # chaque ordre, separe par ', ', suivi de l'indicatif en telephonie
    assert txt == "heading two seven zero, speed two five zero knots, air france one two three four"


def test_readback_text_liste_vide():
    assert readback_text([]) == ""


def test_readback_text_que_des_ordres_non_reconnus():
    # aucun ordre exploitable -> chaine vide (pas d'indicatif seul)
    assert readback_text([{"callsign": "AFR1234", "action": "ZZZ"}]) == ""
