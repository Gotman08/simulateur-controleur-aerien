"""
Tests du moteur d'exercice (src/atc_exercise.py) - modules purs, sans BlueSky.
=============================================================================
Couvre le bareme de notation (_score_unlocked), les paliers grade() et la
construction geometrique du conflit garanti (make_conflict_pair). Ces fonctions
sont pures/deterministes (seed) : aucune dependance GPU/cluster/reseau.

Le bareme est documente dans docs/VALIDATION.md (par. 6) et dans le docstring du
module : S_conf recompense les conflits predits RESOLUS AVANT la perte de
separation -> un conflit qui devient une LoS n'est PAS compte resolu (voulu).
"""
import math
import random

import pytest

import atc_exercise as EX
from atc_sim import to_nm


# --------------------------------------------------------------- grade()
def test_grade_paliers():
    assert EX.grade(100) == "A"
    assert EX.grade(90) == "A"
    assert EX.grade(89.9) == "B"
    assert EX.grade(75) == "B"
    assert EX.grade(74.9) == "C"
    assert EX.grade(60) == "C"
    assert EX.grade(59.9) == "D"
    assert EX.grade(40) == "D"
    assert EX.grade(39.9) == "E"
    assert EX.grade(0) == "E"


# ------------------------------------------------- make_conflict_pair()
def _pos_at(ac, t_s):
    """Position (x, y) en NM de l'avion apres t_s secondes le long de son cap."""
    x, y = to_nm(ac["lat"], ac["lon"])
    d = ac["spd_kt"] * t_s / 3600.0
    r = math.radians(ac["hdg"])
    return x + d * math.sin(r), y + d * math.cos(r)


@pytest.mark.parametrize("seed", range(25))
def test_make_conflict_pair_converge(seed):
    """Les 2 avions arrivent quasi au meme point a t_c (conflit garanti) et
    partagent la meme altitude (perte de separation verticale acquise)."""
    rng = random.Random(seed)
    ac, t_c = EX.make_conflict_pair(rng, ["AAA111", "BBB222"], 30000)
    assert len(ac) == 2
    assert ac[0]["alt_ft"] == ac[1]["alt_ft"] == 30000.0
    assert 240.0 <= t_c <= 420.0
    (x1, y1), (x2, y2) = _pos_at(ac[0], t_c), _pos_at(ac[1], t_c)
    # < 0.5 NM : l'ecart residuel vient de l'arrondi de spd_kt (cf. audit : ~0.1 NM).
    assert math.hypot(x1 - x2, y1 - y2) < 0.5


# ------------------------------------------------------ _score_unlocked()
def _engine():
    """Moteur avec dependances factices : _score_unlocked n'utilise que les
    metriques internes (ni sim, ni ai, ni emit)."""
    return EX.ExerciseEngine(sim=None, ai=None, emit=lambda ev: None)


def test_score_vide_est_parfait():
    s = _engine()._score_unlocked(0.0)
    assert s["total"] == 100.0 and s["grade"] == "A"
    assert (s["separation"], s["conflits"], s["zones"], s["radio"]) == (50.0, 20.0, 15.0, 15.0)


def test_score_une_los_de_20s():
    e = _engine()
    e._los = {"A/B": {"pair": ["A", "B"], "t_start": 10.0, "t_end": 30.0,
                      "min_nm": 3.0, "open": False}}
    s = e._score_unlocked(30.0)
    # S_sep = 50 - 25*1 - 0.5*20 = 15 ; total = 15 + 20 + 15 + 15 = 65 (C)
    assert s["separation"] == 15.0
    assert s["total"] == 65.0 and s["grade"] == "C"


def test_conflit_predit_puis_resolu_avant_los():
    """Predit, jamais en LoS, plus predit -> resolu -> S_conf plein."""
    e = _engine()
    e._predicted = {"A/B": {"pair": ["A", "B"], "t_first": 5.0, "d_min": 4.0}}
    e._predicted_now = set()
    s = e._score_unlocked(60.0)
    assert s["conflits_predits"] == 1 and s["conflits_resolus"] == 1
    assert s["conflits"] == 20.0


def test_conflit_predit_devenu_los_non_compte_resolu():
    """Comportement DOCUMENTE (pas un bug) : un conflit predit qui devient une
    LoS n'est pas 'resolu avant la perte de separation' -> S_conf = 0."""
    e = _engine()
    e._predicted = {"A/B": {"pair": ["A", "B"], "t_first": 5.0, "d_min": 2.0}}
    e._los = {"A/B": {"pair": ["A", "B"], "t_start": 10.0, "t_end": 25.0,
                      "min_nm": 2.0, "open": False}}
    e._predicted_now = set()
    s = e._score_unlocked(60.0)
    assert s["conflits_resolus"] == 0 and s["conflits"] == 0.0


def test_score_radio_ratio_accepte():
    e = _engine()
    e._commands = [{"t": 1.0, "text": "x", "accepted": 3, "rejected": 1}]
    s = e._score_unlocked(10.0)
    assert s["radio"] == round(15.0 * 3 / 4, 1)


def test_score_borne_a_zero_si_multi_los():
    e = _engine()
    e._los = {f"{i}/{i}b": {"pair": [f"{i}", f"{i}b"], "t_start": 0.0,
                            "t_end": 40.0, "min_nm": 1.0, "open": False}
              for i in range(5)}
    s = e._score_unlocked(40.0)
    assert s["separation"] == 0.0            # max(0, 50 - 25*5 - ...) -> 0


# ------------------------------------------- _sample() : episodes multiples
def _snap(t, conflicts=(), aircraft=None):
    if aircraft is None:
        aircraft = [{"id": "A", "x": 0.0, "y": 0.0, "alt_ft": 30000.0},
                    {"id": "B", "x": 2.0, "y": 0.0, "alt_ft": 30000.0}]
    return {"t": t, "aircraft": aircraft, "conflicts": [list(c) for c in conflicts],
            "predicted": []}


def _sampling_engine():
    e = _engine()
    e._active = True
    e._meta = {"duration_s": 1e9}          # jamais de stop(auto) pendant le test
    return e


def test_los_reentree_compte_deux_episodes_et_duree_cumulee():
    """Une paire qui re-perd la separation apres resolution = 2 episodes ;
    t_los ne doit PAS englober l'intervalle correctement separe (bug corrige :
    310 s fantomes aneantissaient S_sep)."""
    e = _sampling_engine()
    e._sample(_snap(1000.0, conflicts=[("A", "B")]))   # episode 1 : rel 0
    e._sample(_snap(1010.0))                           # ferme a rel 10 (10 s)
    e._sample(_snap(1400.0, conflicts=[("A", "B")]))   # episode 2 : rel 400
    e._sample(_snap(1410.0))                           # ferme a rel 410 (10 s)
    s = e._score_unlocked(410.0)
    assert s["n_los"] == 2
    assert s["t_los_s"] == 20.0                        # 10 + 10, pas 410
    # S_sep = 50 - 25*2 - 0.5*20 = -10 -> borne 0
    assert s["separation"] == 0.0


def test_zone_reentree_compte_deux_episodes():
    """Sortir puis re-entrer dans la MEME zone doit rouvrir l'evenement
    (bug corrige : la re-entree n'etait jamais re-comptee)."""
    e = _sampling_engine()
    inz = [{"id": "A", "x": 0.0, "y": 0.0, "alt_ft": 30000.0, "inzone": "storm"}]
    out = [{"id": "A", "x": 50.0, "y": 0.0, "alt_ft": 30000.0}]
    e._sample(_snap(1000.0, aircraft=inz))             # entree 1 : rel 0
    e._sample(_snap(1010.0, aircraft=out))             # sortie a rel 10
    e._sample(_snap(1400.0, aircraft=inz))             # re-entree : rel 400
    e._sample(_snap(1410.0, aircraft=out))             # sortie a rel 410
    s = e._score_unlocked(410.0)
    assert s["n_zone"] == 2
    assert s["t_zone_s"] == 20.0
