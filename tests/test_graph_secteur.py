"""Tests de graph_secteur.SectorGraph (graphe du secteur, Dijkstra)."""
import math

import pytest

import graph_secteur


@pytest.fixture(scope="module")
def g():
    return graph_secteur.SectorGraph()


def test_fixes_contient_les_noeuds_attendus(g):
    fixes = g.fixes()
    for name in ("ENTRY_W", "BALMO", "CROSS", "DELTA", "EXIT_E", "ENTRY_S", "NORTH"):
        assert name in fixes
    assert len(fixes) == 7


def test_is_fix(g):
    assert g.is_fix("BALMO") is True
    assert g.is_fix("CROSS") is True
    assert g.is_fix("INCONNU") is False


def test_separation_chargee(g):
    assert g.sep_nm == 5.0


def test_shortest_path_chemin_connu(g):
    # ENTRY_W -> BALMO -> CROSS -> DELTA -> EXIT_E
    path, dist = g.shortest_path("ENTRY_W", "EXIT_E")
    assert path == ["ENTRY_W", "BALMO", "CROSS", "DELTA", "EXIT_E"]
    # 25 + 25.5 + 25.5 + 25 = 101 NM
    assert dist == pytest.approx(101.0)


def test_shortest_path_distance_positive(g):
    _, dist = g.shortest_path("ENTRY_W", "NORTH")
    assert dist > 0


def test_shortest_path_segments_bidirectionnels(g):
    # les segments sont ajoutes dans les deux sens : trajet retour identique
    path_aller, d_aller = g.shortest_path("ENTRY_W", "EXIT_E")
    path_retour, d_retour = g.shortest_path("EXIT_E", "ENTRY_W")
    assert d_retour == pytest.approx(d_aller)
    assert path_retour == list(reversed(path_aller))


def test_shortest_path_meme_noeud(g):
    path, dist = g.shortest_path("CROSS", "CROSS")
    assert path == ["CROSS"]
    assert dist == 0.0


def test_shortest_path_source_inconnue(g):
    path, dist = g.shortest_path("INCONNU", "EXIT_E")
    assert path is None
    assert dist == math.inf


def test_shortest_path_destination_inconnue(g):
    path, dist = g.shortest_path("ENTRY_W", "INCONNU")
    assert path is None
    assert dist == math.inf


def test_neighbors(g):
    # CROSS est connecte a BALMO, DELTA, ENTRY_S, NORTH
    voisins = {nid for nid, _ in g.neighbors("CROSS")}
    assert voisins == {"BALMO", "DELTA", "ENTRY_S", "NORTH"}
