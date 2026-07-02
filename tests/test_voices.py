"""
Tests de l'attribution deterministe des voix (src/voices.py) - module pur.
=========================================================================
"""
import voices


# ------------------------------------------------------------- parse_pool
def test_parse_pool_nominal():
    assert voices.parse_pool("pilot_1,pilot_2,pilot_3") == ["pilot_1", "pilot_2", "pilot_3"]


def test_parse_pool_espaces_et_vides():
    assert voices.parse_pool(" a , b ,, c ,") == ["a", "b", "c"]


def test_parse_pool_vide_ou_none():
    assert voices.parse_pool("") == []
    assert voices.parse_pool(None) == []


# ----------------------------------------------------- voice_for_callsign
POOL = ["pilot_1", "pilot_2", "pilot_3"]


def test_deterministe():
    assert voices.voice_for_callsign("AFR1234", POOL) == voices.voice_for_callsign("AFR1234", POOL)


def test_insensible_casse_et_espaces():
    ref = voices.voice_for_callsign("AFR1234", POOL)
    assert voices.voice_for_callsign("afr1234", POOL) == ref
    assert voices.voice_for_callsign(" AFR1234 ", POOL) == ref


def test_pool_vide_renvoie_none():
    assert voices.voice_for_callsign("AFR1234", []) is None


def test_pool_unitaire():
    assert voices.voice_for_callsign("BAW42", ["solo"]) == "solo"
    assert voices.voice_for_callsign("DLH9", ["solo"]) == "solo"


def test_callsign_vide_ou_none():
    # Pas d'exception : une voix stable est renvoyee meme sans indicatif.
    assert voices.voice_for_callsign("", POOL) in POOL
    assert voices.voice_for_callsign(None, POOL) in POOL


def test_distribution_non_degeneree():
    """Sur ~20 indicatifs realistes, au moins 2 voix distinctes du pool de 3
    doivent etre utilisees (le hachage ne doit pas etre constant)."""
    calls = [f"AFR{n}" for n in range(100, 110)] + [f"BAW{n}" for n in range(200, 210)]
    used = {voices.voice_for_callsign(cs, POOL) for cs in calls}
    assert len(used) >= 2
    assert used <= set(POOL)
