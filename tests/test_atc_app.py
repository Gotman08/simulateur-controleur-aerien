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
