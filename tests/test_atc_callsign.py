"""Tests de atc_callsign.normalize_callsign (normalisation d'indicatifs ATC)."""
import atc_callsign
from atc_callsign import normalize_callsign


def test_telephonie_compagnie_espacee():
    # 'air france' (2 mots) + chiffres parles -> code OACI + chiffres
    assert normalize_callsign("air france one two three four") == "AFR1234"


def test_telephonie_speedbird_collee_avec_chiffres():
    # forme collee : 'speedbird57' -> BAW57
    assert normalize_callsign("speedbird57") == "BAW57"


def test_telephonie_speedbird_chiffres_parles():
    # 'speedbird five seven' -> BAW57
    assert normalize_callsign("speedbird five seven") == "BAW57"


def test_telephonie_lufthansa():
    assert normalize_callsign("lufthansa eight eight") == "DLH88"


def test_telephonie_ryanair_niner():
    # 'niner' est un synonyme OACI de 9
    assert normalize_callsign("ryanair niner") == "RYR9"


def test_sequence_phonetique_pure():
    # 'oscar kilo' est dans AIRLINE (prefixe immat. tcheque OK-) : 'oscar kilo'
    # est consomme en tete -> 'OK' + le reste epele 'foxtrot alfa oscar' = FAO
    assert normalize_callsign("oscar kilo foxtrot alfa oscar") == "OKFAO"


def test_phonetique_avec_separateurs_underscore():
    # 'oscar_kilo_echo_lima_alfa' : separateurs -> tokens ; 'oscar kilo' = OK,
    # puis echo lima alfa = ELA
    assert normalize_callsign("oscar_kilo_echo_lima_alfa") == "OKELA"


def test_deja_canonique_inchange():
    assert normalize_callsign("AFR1234") == "AFR1234"


def test_csa_avec_lettres_et_chiffres():
    # 'csa one delta zulu' -> CSA + 1 + D + Z
    assert normalize_callsign("csa one delta zulu") == "CSA1DZ"


def test_vide_renvoie_chaine_vide():
    assert normalize_callsign("") == ""


def test_none_renvoie_chaine_vide():
    assert normalize_callsign(None) == ""


def test_delta_compagnie_en_tete():
    # 'delta' en TETE d'indicatif = la compagnie Delta Air Lines (DAL), coherent
    # avec la table CODE2TEL de readback.py (DAL -> 'delta').
    assert normalize_callsign("delta402") == "DAL402"
    assert normalize_callsign("delta four zero two") == "DAL402"


def test_delta_reste_phonetique_hors_tete():
    # ... mais ailleurs 'delta' reste la lettre phonetique D.
    assert normalize_callsign("csa one delta zulu") == "CSA1DZ"


def test_table_phonetique_complete():
    # quelques entrees de la table OACI standard
    assert atc_callsign.PHON["alfa"] == "A"
    assert atc_callsign.PHON["alpha"] == "A"   # variante acceptee
    assert atc_callsign.DIGI["niner"] == "9"
    assert atc_callsign.DIGI["oh"] == "0"
