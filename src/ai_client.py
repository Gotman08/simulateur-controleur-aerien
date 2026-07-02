"""
Client IA unifie (contrat OpenAI-compatible) - Application d'entrainement ATC
=============================================================================
UN SEUL mode de fonctionnement : STT, LLM et TTS sont des services REST au
contrat OpenAI, configures par variables d'environnement (ou fichier .env a la
racine, voir .env.example) :

    ATC_STT_URL / ATC_STT_KEY / ATC_STT_MODEL   -> POST {url}/v1/audio/transcriptions
    ATC_LLM_URL / ATC_LLM_KEY / ATC_LLM_MODEL   -> POST {url}/v1/chat/completions
    ATC_TTS_URL / ATC_TTS_KEY / ATC_TTS_MODEL   -> POST {url}/v1/audio/speech
    ATC_TTS_VOICES  pool de voix (CSV) ; ATC_TTS_VHF degradation radio cote client

Changer de fournisseur (facade auto-hebergee server.py, OpenAI, Mistral API,
Groq, serveur TTS compatible...) = changer URL + cle + modele. Rien d'autre.

AUCUN repli silencieux : toute erreur de fournisseur leve ProviderError, que
l'application remonte visiblement (HTTP 502 + log UI). L'__init__ ne fait AUCUN
appel reseau (import instantane, testable sans reseau).

L'intelligence de prompt reste dans le projet : la KB OACI (kb_oaci, ~2,5 Ko)
est inlinee INTEGRALEMENT dans le prompt systeme et la validation deterministe
des bornes (03_bluesky_connector) s'applique a toute sortie LLM — identique
pour tous les fournisseurs.
"""
import io
import os
import logging
from dataclasses import dataclass

import requests

try:                                   # .env optionnel ; os.environ reste prioritaire
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:                    # python-dotenv absent : config par env uniquement
    pass

import voices

_log = logging.getLogger("ai_client")


# --- erreurs typees --------------------------------------------------------
class ProviderError(RuntimeError):
    """Erreur d'un fournisseur IA (reseau, HTTP, reponse invalide). Toujours
    remontee a l'appelant — jamais de repli silencieux."""

    def __init__(self, provider, message, status=None):
        self.provider = provider
        self.status = status
        prefix = f"HTTP {status} - " if status else ""
        super().__init__(f"{provider.upper()} : {prefix}{message}")


class ProviderConfigError(ProviderError):
    """Configuration manquante (URL/modele) detectee A L'APPEL, pas a l'init."""


# --- configuration ----------------------------------------------------------
@dataclass(frozen=True)
class ProviderConfig:
    name: str      # "stt" | "llm" | "tts"
    url: str       # normalisee : sans "/" final ni suffixe "/v1"
    key: str       # "" -> pas d'en-tete Authorization
    model: str

    @classmethod
    def from_env(cls, name):
        prefix = f"ATC_{name.upper()}"
        url = os.environ.get(f"{prefix}_URL", "").strip().rstrip("/")
        if url.endswith("/v1"):
            url = url[:-3].rstrip("/")
        return cls(name=name.lower(), url=url,
                   key=os.environ.get(f"{prefix}_KEY", "").strip(),
                   model=os.environ.get(f"{prefix}_MODEL", "").strip())


def _headers(cfg):
    return {"Authorization": f"Bearer {cfg.key}"} if cfg.key else {}


def _require_url(cfg):
    if not cfg.url:
        raise ProviderConfigError(
            cfg.name, f"ATC_{cfg.name.upper()}_URL non configuree (copiez .env.example en .env)")


def _http_detail(r):
    """Message d'erreur court et lisible depuis une reponse HTTP non-2xx.
    Robuste a un corps JSON non-objet (liste / chaine) : on ne suppose jamais
    .get() sur le corps (sinon AttributeError -> 500 brut au lieu d'un 502)."""
    try:
        j = r.json()
    except ValueError:
        return (r.text or "")[:200] or r.reason
    if isinstance(j, dict):
        err = j.get("error")
        if isinstance(err, dict):
            err = err.get("message")
        msg = err or j.get("detail")
        if msg:
            return str(msg)
    return (r.text or "")[:200] or r.reason


def ping(cfg):
    """Sante d'un fournisseur : GET {url}/v1/models. Booleen, jamais d'exception."""
    if not cfg.url:
        return False
    try:
        return bool(requests.get(f"{cfg.url}/v1/models", headers=_headers(cfg), timeout=3).ok)
    except Exception:
        return False


# --- clients ----------------------------------------------------------------
class SttClient:
    def __init__(self, cfg):
        self.cfg = cfg

    def transcribe(self, wav_bytes):
        """wav 16 kHz mono -> texte. POST /v1/audio/transcriptions (multipart)."""
        _require_url(self.cfg)
        try:
            r = requests.post(f"{self.cfg.url}/v1/audio/transcriptions",
                              headers=_headers(self.cfg),
                              files={"file": ("utterance.wav", wav_bytes, "audio/wav")},
                              data={"model": self.cfg.model, "response_format": "json"},
                              timeout=60)
        except requests.RequestException as e:
            raise ProviderError("stt", f"{self.cfg.url} injoignable : {e}") from e
        if not r.ok:
            raise ProviderError("stt", _http_detail(r), r.status_code)
        try:
            return str(r.json().get("text", "")).strip()
        except ValueError as e:
            raise ProviderError("stt", f"reponse non JSON : {r.text[:200]}") from e


class LlmClient:
    def __init__(self, cfg):
        self.cfg = cfg

    def chat(self, messages, temperature=0.0, max_tokens=512, timeout=90):
        """messages chat -> contenu texte de la 1re completion. POST /v1/chat/completions."""
        _require_url(self.cfg)
        payload = {"model": self.cfg.model, "messages": messages,
                   "temperature": temperature, "max_tokens": max_tokens}
        try:
            r = requests.post(f"{self.cfg.url}/v1/chat/completions",
                              headers=_headers(self.cfg), json=payload, timeout=timeout)
        except requests.RequestException as e:
            raise ProviderError("llm", f"{self.cfg.url} injoignable : {e}") from e
        if not r.ok:
            raise ProviderError("llm", _http_detail(r), r.status_code)
        try:
            return str(r.json()["choices"][0]["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise ProviderError("llm", f"reponse chat.completion invalide : {r.text[:200]}") from e


class TtsClient:
    def __init__(self, cfg):
        self.cfg = cfg

    def speak(self, text, voice, response_format="wav"):
        """texte -> audio (bytes). POST /v1/audio/speech."""
        _require_url(self.cfg)
        payload = {"model": self.cfg.model, "input": text, "voice": voice,
                   "response_format": response_format}
        try:
            r = requests.post(f"{self.cfg.url}/v1/audio/speech",
                              headers=_headers(self.cfg), json=payload, timeout=120)
        except requests.RequestException as e:
            raise ProviderError("tts", f"{self.cfg.url} injoignable : {e}") from e
        if not r.ok:
            raise ProviderError("tts", _http_detail(r), r.status_code)
        return r.content


# --- degradation VHF cote client (provider-agnostique) -----------------------
def _apply_vhf(audio_bytes):
    """Applique la bande passante radio 300-3400 Hz a un WAV (bytes -> bytes).
    Contenu non-WAV (mp3...) : renvoye tel quel avec un avertissement — l'audio
    reste jouable, seule la coloration radio est perdue (ATC_TTS_FORMAT=wav requis)."""
    if audio_bytes[:4] != b"RIFF":
        _log.warning("TTS : contenu non WAV, degradation VHF ignoree "
                     "(mettre ATC_TTS_FORMAT=wav ou ATC_TTS_VHF=0)")
        return audio_bytes
    try:
        import numpy as np
        import soundfile as sf
        from scipy.signal import resample_poly
        from atc_audio import FS, preprocess_waveform
        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != FS:
            data = resample_poly(data, FS, sr).astype(np.float32)
        data = preprocess_waveform(data, training=False)
        buf = io.BytesIO()
        sf.write(buf, data, FS, format="WAV")
        return buf.getvalue()
    except Exception:
        _log.exception("TTS : degradation VHF echouee, audio original conserve")
        return audio_bytes


# --- facade ------------------------------------------------------------------
class AIClient:
    """Facade unique de l'application. __init__ SANS appel reseau."""

    def __init__(self):
        self._stt = SttClient(ProviderConfig.from_env("stt"))
        self._llm = LlmClient(ProviderConfig.from_env("llm"))
        self._tts = TtsClient(ProviderConfig.from_env("tts"))
        self.tts_pool = voices.parse_pool(os.environ.get("ATC_TTS_VOICES"))
        self._tts_vhf = os.environ.get("ATC_TTS_VHF", "1").strip().lower() not in ("0", "false", "")
        self._tts_format = os.environ.get("ATC_TTS_FORMAT", "wav").strip() or "wav"

    # --- sante ---------------------------------------------------------------
    def health(self):
        """{'stt': bool, 'llm': bool, 'tts': bool} — pings legers, sans exception."""
        return {"stt": ping(self._stt.cfg), "llm": ping(self._llm.cfg), "tts": ping(self._tts.cfg)}

    # --- STT -------------------------------------------------------------------
    def asr(self, wav_bytes):
        return self._stt.transcribe(wav_bytes)

    # --- interpretation (prompt + KB inlinee + validation deterministe) ---------
    def interpret(self, text):
        """Clairance -> {text, orders, trafscript, rejected, cited}.
        MEME forme de sortie que l'ancien parseur local (atc_ai.local_interpret) :
        seuls les ordres VALIDES (bornes 03, waypoints du graphe) sont conserves."""
        import atc_llm                       # pur sans torch (verifie) ; lazy: numpy
        import kb_oaci
        ner = atc_llm.ner_extract(text)
        docs = kb_oaci.build_documents()     # 9 fiches ~2,5 Ko -> KB inlinee integralement
        messages = atc_llm.build_messages(text, [(d, 1.0) for d in docs], ner)
        raw = self._llm.chat(messages)
        valid, rejected = atc_llm.postprocess_orders(atc_llm.parse_orders(raw))
        return {"text": text,
                "orders": [v["order"] for v in valid],
                "trafscript": [v["trafscript"] for v in valid],
                "rejected": [r["erreur"] for r in rejected],
                "cited": [d["id"] for d in docs]}

    # --- generation de scenario --------------------------------------------------
    def scenario(self, description):
        """Description instructeur -> liste d'avions prets pour SIM.create_aircraft."""
        import atc_llm
        import atc_ai                        # _items_to_aircraft (bibliotheque pure)
        raw = self._llm.chat(atc_llm.build_scenario_messages(description),
                             max_tokens=768, timeout=120)
        items = atc_llm.clean_scenario_items(atc_llm.parse_orders(raw))
        return atc_ai._items_to_aircraft(items)

    # --- TTS -----------------------------------------------------------------------
    def tts(self, text, voice=None):
        """Texte -> audio WAV (bytes). voice=None -> 1re voix du pool ; degradation
        VHF appliquee cote client si ATC_TTS_VHF=1 (independant du fournisseur)."""
        voice = voice or (self.tts_pool[0] if self.tts_pool else "default")
        audio = self._tts.speak(text, voice, response_format=self._tts_format)
        return _apply_vhf(audio) if self._tts_vhf else audio
