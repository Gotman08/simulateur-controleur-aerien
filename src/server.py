"""
Facade d'inference OpenAI-compatible (auto-hebergee) - ATC
==========================================================
Expose les modeles du projet (Whisper+LoRA, Mistral-7B, XTTS voix clonees)
derriere le CONTRAT STANDARD OpenAI : c'est UN fournisseur possible parmi
d'autres pour l'application (ai_client.py) — interchangeable avec un service
cloud en changeant simplement ATC_*_URL / ATC_*_KEY / ATC_*_MODEL dans .env.

  GET  /v1/models                      -> {"object":"list","data":[{"id":...}]}
  POST /v1/audio/transcriptions        multipart file [+model] -> {"text": ...}
  POST /v1/chat/completions            {model,messages,max_tokens} -> chat.completion
  POST /v1/audio/speech                {model,input,voice,response_format} -> audio/wav

NB : la degradation VHF est desormais appliquee COTE CLIENT (ai_client) pour
rester identique quel que soit le fournisseur -> synthese ici avec vhf=False.
L'intelligence de prompt (KB OACI, NER, validation des bornes) est aussi cote
client : cette facade ne sert que l'inference brute des modeles.

Lance par job_server.slurm sur un noeud armgpu ; pilote depuis le PC local via
tunnel SSH (ATC_STT_URL/ATC_LLM_URL=http://localhost:8765, ATC_TTS_URL=...:8766).
"""
import os
import io
import time
from contextlib import asynccontextmanager

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("HF_HOME", os.path.join(WORK, "hf_cache"))
os.environ.setdefault("XDG_DATA_HOME", os.path.join(WORK, "tts_data"))
os.environ.setdefault("COQUI_TOS_AGREED", "1")

import glob
import numpy as np
import soundfile as sf

import atc_asr
import atc_llm
import tts_atc

# Adaptateur LoRA : par defaut l'adaptateur fraichement entraine sur le cluster
# (WORK/outputs), sinon celui commite dans le depot (model/whisper-lora-adapter).
# Surchargeable via ATC_ADAPTER.
_HERE = os.path.dirname(os.path.abspath(__file__))
_CLUSTER_ADAPTER = os.path.join(WORK, "outputs", "lora_small", "adapter")
_REPO_ADAPTER = os.path.join(os.path.dirname(_HERE), "model", "whisper-lora-adapter")
ADAPTER = os.environ.get("ATC_ADAPTER") or (
    _CLUSTER_ADAPTER if os.path.isdir(_CLUSTER_ADAPTER) else _REPO_ADAPTER)
VOICES = os.path.join(os.environ["XDG_DATA_HOME"], "voices")
_S = {}

# Identifiants de modeles exposes par la facade (cf. .env.example, config A).
STT_MODEL_ID = "whisper-atc-lora"
LLM_MODEL_ID = "mistral-7b-atc"
TTS_MODEL_ID = "xtts-atc"


def get_asr():
    if "asr" not in _S:
        _S["asr"] = atc_asr.build_inference_model("openai/whisper-small", adapter_path=ADAPTER)
    return _S["asr"]


def default_voice():
    refs = sorted(glob.glob(os.path.join(VOICES, "*.wav")))
    return refs[0] if refs else None


def _voice_ref(voice):
    """Nom de voix OpenAI ('pilot_1' ou 'pilot_1.wav') -> wav de reference XTTS.
    Voix inconnue/absente -> voix par defaut (1er wav du repertoire VOICES)."""
    if voice:
        name = str(voice)
        if not name.endswith(".wav"):
            name += ".wav"
        path = os.path.join(VOICES, os.path.basename(name))
        if os.path.isfile(path):
            return path
    return default_voice()


def _to_16k_mono(raw_bytes):
    data, sr = sf.read(io.BytesIO(raw_bytes), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(int(sr), 16000)
        data = resample_poly(data, 16000 // g, int(sr) // g).astype("float32")
    return np.ascontiguousarray(data, dtype=np.float32)


# Role du process : 'asrllm' (Whisper+Mistral, GPU0), 'tts' (XTTS, GPU1), ou 'all'.
# XTTS et Whisper/Mistral ne doivent PAS partager le meme GPU (conflit cuFFT torchaudio
# sur GH200) -> on les place sur des GPU distincts via 2 process (CUDA_VISIBLE_DEVICES).
# C'est une contrainte d'infra du FOURNISSEUR, invisible du contrat OpenAI.
ROLE = os.environ.get("ATC_ROLE", "all")


@asynccontextmanager
async def lifespan(app):
    print(f"[server] role={ROLE} : chargement des modeles...", flush=True)
    if ROLE in ("all", "asrllm"):
        get_asr()
        try:
            atc_llm.load_llm()
        except Exception as e:
            print("[server] LLM warm:", e, flush=True)
    if ROLE in ("all", "tts"):
        try:
            tts_atc._load()
        except Exception as e:
            print("[server] TTS warm:", e, flush=True)
    print(f"[server] PRET (role={ROLE}).", flush=True)
    yield


from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException
from fastapi.responses import Response

app = FastAPI(title="ATC inference (facade OpenAI-compatible)", lifespan=lifespan)


@app.get("/v1/models")
def models():
    """Liste des modeles servis par CE process (selon ROLE). Sert aussi de ping
    de sante au client (ai_client.ping)."""
    data = []
    if ROLE in ("all", "asrllm"):
        data += [{"id": STT_MODEL_ID, "object": "model", "owned_by": "atc-project"},
                 {"id": LLM_MODEL_ID, "object": "model", "owned_by": "atc-project"}]
    if ROLE in ("all", "tts"):
        data += [{"id": TTS_MODEL_ID, "object": "model", "owned_by": "atc-project"}]
    return {"object": "list", "data": data}


@app.post("/v1/audio/transcriptions")
async def transcriptions(file: UploadFile = File(...), model: str = Form(default=STT_MODEL_ID),
                         response_format: str = Form(default="json")):
    if ROLE not in ("all", "asrllm"):
        raise HTTPException(503, "role != asrllm (STT indisponible sur ce port)")
    try:
        arr = _to_16k_mono(await file.read())
    except Exception:
        raise HTTPException(400, "fichier audio illisible (WAV/FLAC/OGG attendu)") from None
    proc, mdl = get_asr()
    text = atc_asr.transcribe_arrays(mdl, proc, [arr], bandpass=True)[0]
    return {"text": text}


@app.post("/v1/chat/completions")
def chat_completions(payload: dict = Body(...)):
    if ROLE not in ("all", "asrllm"):
        raise HTTPException(503, "role != asrllm (LLM indisponible sur ce port)")
    messages = payload.get("messages") or []
    if not isinstance(messages, list) or not messages:
        raise HTTPException(400, "messages doit etre une liste non vide")
    try:
        max_new = int(payload.get("max_tokens") or payload.get("max_completion_tokens") or 512)
    except (TypeError, ValueError):
        raise HTTPException(400, "max_tokens doit etre un entier") from None
    max_new = max(1, min(4096, max_new))
    content = atc_llm.generate_from_messages(messages, max_new_tokens=max_new)
    return {"id": f"chatcmpl-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": str(payload.get("model") or LLM_MODEL_ID),
            "choices": [{"index": 0,
                         "message": {"role": "assistant", "content": content},
                         "finish_reason": "stop"}]}


@app.post("/v1/audio/speech")
def audio_speech(payload: dict = Body(...)):
    if ROLE not in ("all", "tts"):
        raise HTTPException(503, "role != tts (TTS indisponible sur ce port)")
    text = str(payload.get("input") or "")
    if not text:
        raise HTTPException(400, "input vide")
    ref = _voice_ref(payload.get("voice"))
    if not ref:
        raise HTTPException(503, "aucune voix de reference (lancer make_pilot_voices.py)")
    # vhf=False : la degradation radio est appliquee cote client (provider-agnostique).
    wav = tts_atc.synth(text, ref, out_path=None, vhf=False)
    buf = io.BytesIO()
    sf.write(buf, wav, 16000, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")
