"""
Tests de la couche LLM pure (atc_llm) : parsing tolerant des reponses modele.
=============================================================================
parse_orders doit survivre aux ecarts REELS observes en benchmark (bench/) :
code fences, prose autour du tableau, zeros de tete non JSON ('"value": 090'),
objets isoles. Aucune dependance GPU/torch : fonctions pures uniquement.
"""
import atc_llm


# --- parse_orders : chemins nominaux -----------------------------------------
def test_parse_orders_tableau_direct():
    raw = '[{"callsign": "AFR1234", "action": "HDG", "value": 270}]'
    assert atc_llm.parse_orders(raw) == [
        {"callsign": "AFR1234", "action": "HDG", "value": 270}]


def test_parse_orders_code_fence_et_prose():
    raw = ('Voici les ordres :\n```json\n'
           '[{"callsign": "BAW57", "action": "ALT", "value": 8000}]\n```')
    assert atc_llm.parse_orders(raw) == [
        {"callsign": "BAW57", "action": "ALT", "value": 8000}]


def test_parse_orders_tableau_vide():
    assert atc_llm.parse_orders("[]") == []
    assert atc_llm.parse_orders("rien d'actionnable ici") == []


# --- parse_orders : zeros de tete (observe avec Qwen2.5, caps a 3 chiffres) ---
def test_parse_orders_zero_de_tete_heading():
    raw = '[{"callsign": "BAW57", "action": "HDG", "value": 090}]'
    assert atc_llm.parse_orders(raw) == [
        {"callsign": "BAW57", "action": "HDG", "value": 90}]


def test_parse_orders_zero_de_tete_objet_isole():
    raw = 'ordre : {"callsign": "EZY21", "action": "HDG", "value": 045} fin'
    assert atc_llm.parse_orders(raw) == [
        {"callsign": "EZY21", "action": "HDG", "value": 45}]


def test_parse_orders_zero_seul_intact():
    raw = '[{"callsign": "AFR1234", "action": "HDG", "value": 0}]'
    assert atc_llm.parse_orders(raw)[0]["value"] == 0


def test_parse_orders_zero_dans_chaine_intact():
    raw = '[{"callsign": "AFR1234", "action": "ADDWPT", "value": 1, "wpt": "ENTRY_090"}]'
    assert atc_llm.parse_orders(raw)[0]["wpt"] == "ENTRY_090"


def test_fix_leading_zeros_ne_touche_pas_les_chaines():
    blob = '{"a": "FL090", "b": 070, "c": [010, 2]}'
    assert atc_llm._fix_leading_zeros(blob) == '{"a": "FL090", "b": 70, "c": [10, 2]}'


# --- postprocess_orders : la validation reste stricte apres parsing ------------
def test_postprocess_rejette_hors_bornes_meme_apres_reparation():
    valid, rejected = atc_llm.postprocess_orders(
        [{"callsign": "AFR1234", "action": "SPD", "value": 400}])
    assert valid == []
    assert len(rejected) == 1


def test_postprocess_coerce_value_en_entier():
    """La valeur de l'ordre valide est alignee sur l'entier du TrafScript
    (le LLM peut renvoyer 32000.0) — coherence de type pour l'aval."""
    valid, _ = atc_llm.postprocess_orders(
        [{"callsign": "AFR1234", "action": "ALT", "value": 32000.0}])
    assert valid[0]["order"]["value"] == 32000
    assert isinstance(valid[0]["order"]["value"], int)
    assert valid[0]["trafscript"] == "ALT AFR1234 32000"


def test_postprocess_ne_mute_pas_la_liste_appelante():
    brut = [{"callsign": "air france 1234", "action": "HDG", "value": 270.0}]
    atc_llm.postprocess_orders(brut)
    assert brut[0]["callsign"] == "air france 1234"    # original intact
    assert brut[0]["value"] == 270.0
