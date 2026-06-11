"""Tests du repli local de atc_ai : local_interpret, local_scenario et helpers.

On ne teste QUE le repli local (parseurs regex purs), pas l'aiguillage ROMEO.
"""
import math

import pytest

import atc_ai


# =============================================================================
#  Helpers langage : _normalize_numbers / _to_int
# =============================================================================
def test_normalize_numbers_mots_vers_chiffres():
    assert atc_ai._normalize_numbers("descend flight level one zero zero") == \
        "descend flight level 1 0 0"


def test_to_int_chiffres_epeles():
    assert atc_ai._to_int("2 7 0") == 270


def test_to_int_un_zero_zero():
    # '1 0 0' = concatenation -> 100 (et NON 1)
    assert atc_ai._to_int("1 0 0") == 100


def test_to_int_thousand():
    assert atc_ai._to_int("5 thousand") == 5000


def test_to_int_hundred():
    assert atc_ai._to_int("1 hundred") == 100


def test_to_int_compact():
    assert atc_ai._to_int("250") == 250


# =============================================================================
#  local_interpret : caps, niveaux, vitesses, direct
# =============================================================================
def test_interpret_cap_turn_right():
    r = atc_ai.local_interpret("speedbird five seven turn right heading two seven zero")
    assert r["orders"] == [{"action": "HDG", "value": 270, "callsign": "BAW57"}]
    assert r["trafscript"] == ["HDG BAW57 270"]
    assert r["rejected"] == []


def test_interpret_niveau_epele_vers_alt():
    # 'descend flight level one zero zero' -> ALT 10000 (FL100 * 100)
    r = atc_ai.local_interpret("csa one delta zulu descend flight level one zero zero")
    assert r["orders"] == [{"action": "ALT", "value": 10000, "callsign": "CSA1DZ"}]
    assert r["trafscript"] == ["ALT CSA1DZ 10000"]


def test_interpret_air_france_descend():
    r = atc_ai.local_interpret("air france one two three four descend flight level one zero zero")
    assert r["trafscript"] == ["ALT AFR1234 10000"]


def test_interpret_vitesse():
    r = atc_ai.local_interpret("speedbird five seven reduce speed two five zero")
    assert r["orders"] == [{"action": "SPD", "value": 250, "callsign": "BAW57"}]
    assert r["trafscript"] == ["SPD BAW57 250"]


def test_interpret_direct_fix_valide_du_secteur():
    # BALMO est un fix du secteur (secteur_graphe.json)
    r = atc_ai.local_interpret("ryanair niner proceed direct balmo")
    assert r["orders"] == [{"action": "ADDWPT", "wpt": "BALMO", "callsign": "RYR9"}]
    assert r["rejected"] == []


def test_interpret_direct_fix_delta():
    r = atc_ai.local_interpret("ryanair niner proceed direct delta")
    assert r["orders"] == [{"action": "ADDWPT", "wpt": "DELTA", "callsign": "RYR9"}]


# =============================================================================
#  local_interpret : multi-ordres
# =============================================================================
def test_interpret_multi_ordres():
    r = atc_ai.local_interpret(
        "csa one delta zulu climb flight level two four zero reduce speed two five zero "
        "turn left heading 090")
    actions = [(o["action"], o["value"]) for o in r["orders"]]
    # l'ordre interne est : ALT, puis HDG, puis SPD (cf. _parse_alt+_parse_hdg+_parse_spd)
    assert ("ALT", 24000) in actions
    assert ("HDG", 90) in actions
    assert ("SPD", 250) in actions
    assert set(r["trafscript"]) == {"ALT CSA1DZ 24000", "HDG CSA1DZ 90", "SPD CSA1DZ 250"}


# =============================================================================
#  local_interpret : expedite / rate -> VS
# =============================================================================
def test_interpret_expedite_descend_vers_vs_negatif():
    # 'expedite' fixe le taux a 3000 fpm ; le verbe 'descend' rend le signe negatif
    r = atc_ai.local_interpret("ryanair niner descend flight level one zero zero expedite")
    assert "VS RYR9 -3000" in r["trafscript"]


def test_interpret_rate_climb_vers_vs_positif():
    r = atc_ai.local_interpret("ryanair niner climb flight level three zero zero rate two thousand")
    assert "VS RYR9 2000" in r["trafscript"]


# =============================================================================
#  local_interpret : rejets
# =============================================================================
def test_interpret_sans_indicatif_rejete():
    # un ordre sans indicatif identifiable est rejete et vide les ordres
    r = atc_ai.local_interpret("turn right heading two seven zero")
    assert r["orders"] == []
    assert "indicatif non reconnu" in r["rejected"]


def test_interpret_waypoint_inconnu_rejete():
    r = atc_ai.local_interpret("ryanair niner proceed direct zzz")
    assert r["orders"] == []
    assert any("inconnu" in x for x in r["rejected"])


def test_interpret_hors_bornes_hdg():
    # Un ordre hors bornes (cap 400) est entierement REJETE : il n'apparait ni
    # dans `trafscript` ni dans `orders` (sinon le pilote collationnerait un
    # ordre jamais execute). Seul le motif du rejet est conserve.
    r = atc_ai.local_interpret("ryanair niner turn right heading 400")
    assert r["orders"] == []
    assert r["trafscript"] == []
    assert any("hors limites" in x for x in r["rejected"])


# =============================================================================
#  local_scenario : nombre d'avions, FL, espacement, clauses multiples
# =============================================================================
def test_scenario_nombre_d_avions():
    ac = atc_ai.local_scenario("three A320 from the north at FL300 heading 180, 8 miles apart")
    assert len(ac) == 3


def test_scenario_fl_applique():
    ac = atc_ai.local_scenario("three A320 from the north at FL300 heading 180, 8 miles apart")
    # FL300 -> 30000 ft pour tous
    assert {a["alt_ft"] for a in ac} == {30000.0}


def test_scenario_cap_applique():
    ac = atc_ai.local_scenario("three A320 from the north at FL300 heading 180, 8 miles apart")
    assert {a["hdg"] for a in ac} == {180.0}


def test_scenario_type_applique():
    ac = atc_ai.local_scenario("three A320 from the north at FL300 heading 180, 8 miles apart")
    assert {a["type"] for a in ac} == {"A320"}


def test_scenario_espacement():
    # avions du nord (bearing 0), espaces de 8 NM : la distance au centre augmente
    # de 8 NM par avion -> ecart de latitude constant. On verifie l'espacement reel.
    ac = atc_ai.local_scenario("three A320 from the north at FL300 heading 180, 8 miles apart")
    lats = sorted(a["lat"] for a in ac)
    ecarts = [round(lats[i + 1] - lats[i], 4) for i in range(len(lats) - 1)]
    # 8 NM = 8/60 degre de latitude ~ 0.1333
    assert ecarts[0] == pytest.approx(8.0 / 60.0, abs=1e-3)
    assert ecarts[0] == pytest.approx(ecarts[1], abs=1e-6)


def test_scenario_clauses_multiples_and():
    ac = atc_ai.local_scenario(
        "two B738 from the south at flight level 240 and one A319 from the west at fl120")
    assert len(ac) == 3
    types = [a["type"] for a in ac]
    assert types == ["B738", "B738", "A319"]
    # FL distincts par clause
    assert [a["alt_ft"] for a in ac] == [24000.0, 24000.0, 12000.0]


def test_scenario_clauses_multiples_francais_et():
    ac = atc_ai.local_scenario("deux A320 du nord et un A330 du sud")
    assert len(ac) == 3


def test_scenario_vide_genere_defaut():
    # description vide -> un A320 par defaut
    ac = atc_ai.local_scenario("")
    assert len(ac) == 1
    assert ac[0]["type"] == "A320"


def test_scenario_type_generique_aliase():
    # un type generique (A330, B777...) est aliase vers une variante connue de la
    # base de performances BlueSky (_TYPE_ALIAS), pas remplace par A320.
    ac = atc_ai.local_scenario("one a330 from the west")
    assert ac[0]["type"] == "A332"
    ac = atc_ai.local_scenario("one b744 from the east at FL340")
    assert ac[0]["type"] == "B744"


# =============================================================================
#  _items_to_aircraft : lat/lon directs vs bearing/dist
# =============================================================================
def test_items_to_aircraft_lat_lon_directs():
    items = [{"callsign": "afr1", "type": "A320", "lat": 49.0, "lon": 4.0,
              "hdg": 90, "alt_ft": 30000, "spd_kt": 280}]
    out = atc_ai._items_to_aircraft(items)
    assert len(out) == 1
    a = out[0]
    assert a["callsign"] == "AFR1"
    assert a["lat"] == 49.0 and a["lon"] == 4.0
    assert a["hdg"] == 90.0 and a["alt_ft"] == 30000.0 and a["spd_kt"] == 280.0


def test_items_to_aircraft_bearing_dist():
    # bearing 90 (est), dist 30 NM : lat reste au centre, lon decale vers l'est
    items = [{"callsign": "baw2", "bearing_deg": 90, "dist_nm": 30}]
    out = atc_ai._items_to_aircraft(items)
    assert len(out) == 1
    a = out[0]
    # reconstruit la position attendue avec la meme conversion from_nm
    exp_lat, exp_lon = atc_ai.from_nm(30 * math.sin(math.radians(90)),
                                      30 * math.cos(math.radians(90)))
    assert a["lat"] == pytest.approx(exp_lat)
    assert a["lon"] == pytest.approx(exp_lon)


def test_items_to_aircraft_type_non_sur_devient_a320():
    items = [{"callsign": "x", "type": "F16", "lat": 49, "lon": 4}]
    out = atc_ai._items_to_aircraft(items)
    assert out[0]["type"] == "A320"


def test_items_to_aircraft_valeurs_par_defaut():
    # sans hdg/alt/spd -> defauts (0, 20000, 250)
    items = [{"callsign": "y", "lat": 49, "lon": 4}]
    out = atc_ai._items_to_aircraft(items)
    a = out[0]
    assert a["hdg"] == 0.0
    assert a["alt_ft"] == 20000.0
    assert a["spd_kt"] == 250.0


def test_items_to_aircraft_liste_vide():
    assert atc_ai._items_to_aircraft([]) == []
    assert atc_ai._items_to_aircraft(None) == []
