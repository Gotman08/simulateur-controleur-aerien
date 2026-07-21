"""
Validation d'entree des endpoints (src/atc_app.py) - une entree malformee doit
renvoyer HTTP 400 propre, jamais 500 (fuite de trace interne).

Importe atc_app (donc FastAPI) -> saute automatiquement dans la CI minimale.
Les fonctions d'endpoint sont appelees DIRECTEMENT avec un payload dict :
la validation (theme C) leve avant tout acces a BlueSky / aux fournisseurs IA.
"""
import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException  # noqa: E402

import atc_app  # noqa: E402


def _status(fn, *args):
    with pytest.raises(HTTPException) as ei:
        fn(*args)
    return ei.value.status_code


def test_command_text_non_string_400():
    assert _status(atc_app.command, {"text": 12345}) == 400


def test_sim_speed_non_numerique_400():
    assert _status(atc_app.sim_speed, {"value": "vite"}) == 400


def test_turbulence_non_numerique_400():
    assert _status(atc_app.weather_turb, {"level": "beaucoup"}) == 400


def test_wind_direction_non_numerique_400():
    assert _status(atc_app.weather_wind, {"dir": "nord", "spd": "fort"}) == 400


def test_zone_circle_sans_xy_400():
    assert _status(atc_app.weather_zone, {"ztype": "storm", "shape": "CIRCLE", "r": 10}) == 400


def test_exercise_duration_mauvais_type_400():
    assert _status(atc_app.exercise_start,
                   {"difficulty": "facile", "duration_min": [1, 2]}) == 400


def test_exercise_seed_mauvais_type_400():
    assert _status(atc_app.exercise_start,
                   {"difficulty": "facile", "seed": {"a": 1}}) == 400


def test_wind_suppression_ok():
    # dir vide = suppression du vent : ne doit PAS lever (comportement nominal)
    assert atc_app.weather_wind({"dir": ""}) == {"ok": True}


# ------------------------------------------- garde semantique climb/descend
def test_alt_coherence_retire_ordre_ET_ligne_meme_si_value_float():
    """Bug corrige : la ligne TrafScript etait retiree par egalite de chaine
    reconstruite ('ALT CS 32000.0' != 'ALT CS 32000') -> l'ordre rejete par le
    garde-fou etait quand meme execute. Le filtrage est desormais positionnel."""
    orders = [{"callsign": "AFR123", "action": "ALT", "value": 32000.0}]
    lines = ["ALT AFR123 32000"]
    rejected = []
    kept, kept_lines = atc_app._check_alt_coherence(
        "descend flight level three two zero", orders, lines, rejected,
        {"AFR123": 28000.0})
    assert kept == [] and kept_lines == []
    assert len(rejected) == 1 and "incohérence" in rejected[0]


def test_alt_coherence_conserve_les_ordres_coherents():
    orders = [{"callsign": "AFR123", "action": "ALT", "value": 22000},
              {"callsign": "AFR123", "action": "SPD", "value": 250}]
    lines = ["ALT AFR123 22000", "SPD AFR123 250"]
    rejected = []
    kept, kept_lines = atc_app._check_alt_coherence(
        "descend flight level two two zero reduce speed two five zero",
        orders, lines, rejected, {"AFR123": 28000.0})
    assert kept == orders and kept_lines == lines and rejected == []
