"""
Tests du client IA unifie (src/ai_client.py) - contrats OpenAI-compatibles.
==========================================================================
Tout le reseau est mocke (monkeypatch de requests) : aucun appel reel.
Verifie les contrats des 3 clients, la remontee d'erreurs typees (JAMAIS de
repli silencieux), la sante, la config .env et la degradation VHF cote client.
"""
import io
import json

import pytest
import requests

import ai_client
from ai_client import (AIClient, LlmClient, ProviderConfig, ProviderConfigError,
                       ProviderError, SttClient, TtsClient, ping)


class FakeResp:
    def __init__(self, status=200, json_data=None, content=b"", text=""):
        self.status_code = status
        self._json = json_data
        self.content = content
        self.text = text or (json.dumps(json_data) if json_data is not None else "")
        self.reason = "err"

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


CFG = ProviderConfig(name="stt", url="http://fake:1", key="sk-test", model="whisper-x")


def _cfg(name):
    return ProviderConfig(name=name, url="http://fake:1", key="", model=f"{name}-model")


# ------------------------------------------------------------ ProviderConfig
def test_config_normalise_url_v1(monkeypatch):
    monkeypatch.setenv("ATC_LLM_URL", "https://api.openai.com/v1/")
    monkeypatch.setenv("ATC_LLM_KEY", " sk-abc ")
    monkeypatch.setenv("ATC_LLM_MODEL", "gpt-4o-mini")
    cfg = ProviderConfig.from_env("llm")
    assert cfg.url == "https://api.openai.com"
    assert cfg.key == "sk-abc"
    assert cfg.model == "gpt-4o-mini"


def test_config_absente_leve_a_l_appel(monkeypatch):
    monkeypatch.delenv("ATC_STT_URL", raising=False)
    client = SttClient(ProviderConfig.from_env("stt"))     # init OK, pas d'erreur
    with pytest.raises(ProviderConfigError):
        client.transcribe(b"RIFFxxxx")


# --------------------------------------------------------------------- STT
def test_stt_contrat_et_extraction(monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen["url"] = url
        seen["files"] = kw.get("files")
        seen["data"] = kw.get("data")
        seen["headers"] = kw.get("headers")
        return FakeResp(json_data={"text": " turn left heading two seven zero "})

    monkeypatch.setattr(requests, "post", fake_post)
    out = SttClient(CFG).transcribe(b"RIFF1234")
    assert out == "turn left heading two seven zero"
    assert seen["url"] == "http://fake:1/v1/audio/transcriptions"
    assert "file" in seen["files"] and seen["data"]["model"] == "whisper-x"
    assert seen["headers"] == {"Authorization": "Bearer sk-test"}


def test_stt_http_500_leve_provider_error(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp(status=500, text="boom"))
    with pytest.raises(ProviderError) as ei:
        SttClient(CFG).transcribe(b"RIFF")
    assert "STT" in str(ei.value) and "500" in str(ei.value)


# --------------------------------------------------------------------- LLM
def test_llm_contrat_et_extraction(monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen["url"] = url
        seen["payload"] = kw.get("json")
        return FakeResp(json_data={"choices": [{"message": {"role": "assistant",
                                                            "content": "[]"}}]})

    monkeypatch.setattr(requests, "post", fake_post)
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    out = LlmClient(_cfg("llm")).chat(msgs)
    assert out == "[]"
    assert seen["url"] == "http://fake:1/v1/chat/completions"
    p = seen["payload"]
    assert p["model"] == "llm-model" and p["messages"] == msgs and p["temperature"] == 0.0


def test_llm_reponse_sans_choices(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp(json_data={"oops": 1}))
    with pytest.raises(ProviderError):
        LlmClient(_cfg("llm")).chat([{"role": "user", "content": "x"}])


# --------------------------------------------------------------------- TTS
def test_tts_contrat_et_bytes(monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen["url"] = url
        seen["payload"] = kw.get("json")
        return FakeResp(content=b"AUDIOBYTES")

    monkeypatch.setattr(requests, "post", fake_post)
    out = TtsClient(_cfg("tts")).speak("roger", voice="pilot_2")
    assert out == b"AUDIOBYTES"
    assert seen["url"] == "http://fake:1/v1/audio/speech"
    p = seen["payload"]
    assert p == {"model": "tts-model", "input": "roger", "voice": "pilot_2",
                 "response_format": "wav"}


# ------------------------------------------------------------------- sante
def test_ping_ok_ko_et_sans_url(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(status=200, json_data={}))
    assert ping(_cfg("llm")) is True
    monkeypatch.setattr(requests, "get",
                        lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("down")))
    assert ping(_cfg("llm")) is False                       # jamais d'exception
    assert ping(ProviderConfig("llm", "", "", "")) is False  # URL absente


# ------------------------------------------------- facade : anti-fallback
def _env_all(monkeypatch):
    for name in ("STT", "LLM", "TTS"):
        monkeypatch.setenv(f"ATC_{name}_URL", "http://fake:1")
        monkeypatch.setenv(f"ATC_{name}_KEY", "")
        monkeypatch.setenv(f"ATC_{name}_MODEL", f"{name.lower()}-model")
    monkeypatch.setenv("ATC_TTS_VOICES", "pilot_1,pilot_2,pilot_3")
    monkeypatch.setenv("ATC_TTS_VHF", "0")


def test_interpret_ne_retombe_jamais_sur_le_parseur_local(monkeypatch):
    """LLM injoignable -> ProviderError, MEME pour une phrase que l'ancien
    parseur local savait traiter (plus aucun fallback silencieux)."""
    _env_all(monkeypatch)
    monkeypatch.setattr(requests, "post",
                        lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("down")))
    with pytest.raises(ProviderError):
        AIClient().interpret("air france one two three four turn left heading two seven zero")


def test_interpret_bout_en_bout_validation_bornes(monkeypatch):
    """Faux LLM (code fences + 1 ordre hors bornes + 1 valide) -> normalisation
    callsign, rejet HDG 400 par les bornes 03, trafscript pour l'ordre valide."""
    _env_all(monkeypatch)
    content = ('```json\n'
               '[{"callsign": "air france 1234", "action": "HDG", "value": 400},\n'
               ' {"callsign": "speedbird 42", "action": "ALT", "value": 10000}]\n'
               '```')

    def fake_post(url, **kw):
        assert url.endswith("/v1/chat/completions")
        return FakeResp(json_data={"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(requests, "post", fake_post)
    out = AIClient().interpret("whatever")
    assert out["trafscript"] == ["ALT BAW42 10000"]
    assert [o["callsign"] for o in out["orders"]] == ["BAW42"]
    assert len(out["rejected"]) == 1 and "HDG" in out["rejected"][0]
    assert "act-heading" in out["cited"]                    # KB inlinee citee


def test_scenario_bout_en_bout(monkeypatch):
    _env_all(monkeypatch)
    content = ('[{"callsign": "AFR100", "type": "a320", "bearing_deg": 0, '
               '"dist_nm": 40, "hdg": 180, "alt_ft": 30000, "spd_kt": 280}]')
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp(
        json_data={"choices": [{"message": {"content": content}}]}))
    ac = AIClient().scenario("one a320 from the north at fl300")
    assert len(ac) == 1
    a = ac[0]
    assert a["callsign"] == "AFR100" and a["type"] == "A320"
    assert {"lat", "lon", "hdg", "alt_ft", "spd_kt"} <= set(a)


def test_tts_voix_par_defaut_du_pool(monkeypatch):
    _env_all(monkeypatch)
    seen = {}

    def fake_post(url, **kw):
        seen["voice"] = kw["json"]["voice"]
        return FakeResp(content=b"WAVDATA")

    monkeypatch.setattr(requests, "post", fake_post)
    ai = AIClient()
    assert ai.tts_pool == ["pilot_1", "pilot_2", "pilot_3"]
    assert ai.tts("readback") == b"WAVDATA" and seen["voice"] == "pilot_1"
    ai.tts("readback", voice="pilot_3")
    assert seen["voice"] == "pilot_3"


# ------------------------------------------------------ degradation VHF client
def _make_wav(sr=24000, freq=1000.0, dur=0.25):
    import numpy as np
    import soundfile as sf
    t = np.arange(int(sr * dur)) / sr
    buf = io.BytesIO()
    sf.write(buf, (0.5 * np.sin(2 * np.pi * freq * t)).astype("float32"), sr, format="WAV")
    return buf.getvalue()


def test_apply_vhf_resample_16k_et_riff():
    import soundfile as sf
    out = ai_client._apply_vhf(_make_wav(sr=24000))
    assert out[:4] == b"RIFF"
    data, sr = sf.read(io.BytesIO(out), dtype="float32")
    assert sr == 16000 and len(data) > 0


def test_apply_vhf_non_wav_renvoye_tel_quel():
    mp3ish = b"ID3\x04rest-of-mp3"
    assert ai_client._apply_vhf(mp3ish) == mp3ish
