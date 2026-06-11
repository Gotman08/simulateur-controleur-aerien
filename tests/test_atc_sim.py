"""Tests des fonctions geometriques PURES de atc_sim.

IMPORTANT : l'import de atc_sim tire bluesky_runtime mais PAS bluesky tant que
bsk.bs() n'est pas appele. Aucun test ici n'instancie la boucle de simulation
ni n'appelle de fonction BlueSky : on ne touche qu'aux helpers geometriques
(to_nm / from_nm / _point_in_poly) et a la methode STATIQUE SimManager._analyze,
qui opere sur des dictionnaires d'avions construits a la main.
"""

import pytest

import atc_sim
from atc_sim import to_nm, from_nm, _point_in_poly, SimManager


# =============================================================================
#  to_nm / from_nm : aller-retour ~ identite
# =============================================================================
def test_to_nm_centre_est_origine():
    assert to_nm(atc_sim.CLAT, atc_sim.CLON) == (0.0, 0.0)


def test_from_nm_60nm_nord_est_un_degre_de_latitude():
    lat, lon = from_nm(0, 60)
    assert lat == pytest.approx(atc_sim.CLAT + 1.0)
    assert lon == pytest.approx(atc_sim.CLON)


@pytest.mark.parametrize("lat,lon", [
    (49.5, 4.5), (48.0, 3.0), (50.25, 4.05), (49.25, 4.05),
])
def test_roundtrip_to_nm_from_nm(lat, lon):
    x, y = to_nm(lat, lon)
    lat2, lon2 = from_nm(x, y)
    assert lat2 == pytest.approx(lat)
    assert lon2 == pytest.approx(lon)


# =============================================================================
#  _point_in_poly : ray casting
# =============================================================================
def test_point_in_poly_interieur():
    carre = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert _point_in_poly(5, 5, carre) is True


def test_point_in_poly_exterieur_droite():
    carre = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert _point_in_poly(15, 5, carre) is False


def test_point_in_poly_exterieur_gauche():
    carre = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert _point_in_poly(-1, 5, carre) is False


# =============================================================================
#  _vel_nm_s : vecteur vitesse (convention x=est, y=nord)
# =============================================================================
def test_vel_cap_est():
    # cap 090 -> plein est : vx>0, vy~0. gs 3600 kt -> 1 NM/s
    vx, vy = SimManager._vel_nm_s({"gs": 3600, "hdg": 90})
    assert vx == pytest.approx(1.0)
    assert vy == pytest.approx(0.0, abs=1e-9)


def test_vel_cap_nord():
    vx, vy = SimManager._vel_nm_s({"gs": 3600, "hdg": 0})
    assert vx == pytest.approx(0.0, abs=1e-9)
    assert vy == pytest.approx(1.0)


# =============================================================================
#  SimManager._analyze : detection / prediction de conflits
# =============================================================================
def _ac(id_, x, y, alt, hdg, gs):
    return {"id": id_, "x": x, "y": y, "alt_ft": alt, "hdg": hdg, "gs": gs}


def test_analyze_perte_de_separation_meme_fl():
    # (a) deux avions a 3 NM, meme FL -> perte de separation immediate (< 5 NM)
    acs = [_ac("A", 0.0, 0.0, 30000, 90, 400),
           _ac("B", 3.0, 0.0, 30000, 90, 400)]
    current, predicted = SimManager._analyze(acs)
    assert current == [["A", "B"]]
    # deja en LOS -> pas de prediction supplementaire pour cette paire
    assert predicted == []


def test_analyze_conflit_face_a_face_cpa():
    # (b) face-a-face : A en x=0 cap 090 (est), B en x=20 cap 270 (ouest),
    # 300 kt chacun, meme FL. Vitesse de rapprochement = 600 kt = 600/3600 NM/s.
    # CPA : t = 20 / (600/3600) = 120 s, distance d = 0 NM.
    acs = [_ac("A", 0.0, 0.0, 30000, 90, 300),
           _ac("B", 20.0, 0.0, 30000, 270, 300)]
    current, predicted = SimManager._analyze(acs)
    assert current == []
    assert len(predicted) == 1
    p = predicted[0]
    assert sorted(p["pair"]) == ["A", "B"]
    # coherence mathematique du CPA (calcul a la main ci-dessus)
    assert p["t"] == 120
    assert p["d"] == pytest.approx(0.0, abs=0.05)


def test_analyze_separes_verticalement_rien():
    # (c) 2000 ft d'ecart vertical (>= SEP_FT=1000) -> aucun conflit meme proches
    acs = [_ac("A", 0.0, 0.0, 30000, 90, 300),
           _ac("B", 3.0, 0.0, 32000, 270, 300)]
    current, predicted = SimManager._analyze(acs)
    assert current == []
    assert predicted == []


def test_analyze_routes_divergentes_rien():
    # (d) A cap 270 (ouest) en x=0, B cap 090 (est) en x=20 : ils s'eloignent
    acs = [_ac("A", 0.0, 0.0, 30000, 270, 300),
           _ac("B", 20.0, 0.0, 30000, 90, 300)]
    current, predicted = SimManager._analyze(acs)
    assert current == []
    assert predicted == []


def test_analyze_cpa_decale_distance_non_nulle():
    # Verification CPA avec offset lateral : A en (0,0) cap est, B en (20, 2)
    # cap ouest, meme FL, 300 kt. Au CPA les x se croisent (t=120 s) mais
    # l'ecart lateral en y reste 2 NM (B ne bouge pas en y). d_cpa = 2 NM < 5 NM.
    acs = [_ac("A", 0.0, 0.0, 30000, 90, 300),
           _ac("B", 20.0, 2.0, 30000, 270, 300)]
    current, predicted = SimManager._analyze(acs)
    assert current == []
    assert len(predicted) == 1
    p = predicted[0]
    assert p["t"] == 120
    assert p["d"] == pytest.approx(2.0, abs=0.05)


def test_analyze_constantes_de_separation():
    assert atc_sim.SEP_NM == 5.0
    assert atc_sim.SEP_FT == 1000.0
    assert atc_sim.LOOKAHEAD_S == 120.0


def test_import_atc_sim_ne_charge_pas_bluesky():
    # Garantit que tester atc_sim ne tire pas la dependance lourde bluesky.
    import sys
    assert "bluesky" not in sys.modules
