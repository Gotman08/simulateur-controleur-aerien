"""
Serveur d'inference ATC - Semaines 6&8 (V2)
===========================================
Service FastAPI unique (env whisper-atc) qui garde charges Whisper (S4),
Mistral+RAG+graphe (S5) et XTTS (S6). Endpoints :
  GET  /health
  POST /asr        (fichier wav)              -> {"text": ...}
  POST /interpret  {"text": ...}              -> {"orders","trafscript","rejected","cited"}
  POST /tts        {"text","voice","vhf"}     -> audio/wav (voix clonee + VHF)

Lance par job_server.slurm sur un noeud armgpu ; pilote depuis le PC local via tunnel SSH.
"""
import os
import io
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

ADAPTER = os.path.join(WORK, "outputs", "lora_small", "adapter")
VOICES = os.path.join(os.environ["XDG_DATA_HOME"], "voices")
_S = {}


def get_asr():
    if "asr" not in _S:
        _S["asr"] = atc_asr.build_inference_model("openai/whisper-small", adapter_path=ADAPTER)
    return _S["asr"]


def get_retriever():
    if "ret" not in _S:
        _S["ret"] = atc_llm.Retriever()
    return _S["ret"]


def default_voice():
    refs = sorted(glob.glob(os.path.join(VOICES, "*.wav")))
    return refs[0] if refs else None


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
ROLE = os.environ.get("ATC_ROLE", "all")


@asynccontextmanager
async def lifespan(app):
    print(f"[server] role={ROLE} : chargement des modeles...", flush=True)
    if ROLE in ("all", "asrllm"):
        get_asr(); get_retriever()
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


from fastapi import FastAPI, UploadFile, File, Body, HTTPException
from fastapi.responses import Response

app = FastAPI(title="ATC inference (ROMEO)", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True, "role": ROLE, "loaded": sorted(_S.keys()),
            "voices": len(glob.glob(os.path.join(VOICES, "*.wav")))}


@app.post("/asr")
async def asr(file: UploadFile = File(...)):
    if ROLE not in ("all", "asrllm"):
        raise HTTPException(503, "role != asrllm")
    arr = _to_16k_mono(await file.read())
    proc, model = get_asr()
    text = atc_asr.transcribe_arrays(model, proc, [arr], bandpass=True)[0]
    return {"text": text}


@app.post("/interpret")
def interpret(payload: dict = Body(...)):
    if ROLE not in ("all", "asrllm"):
        raise HTTPException(503, "role != asrllm")
    res = atc_llm.interpret(payload["text"], get_retriever())
    return {"orders": res["orders"],
            "trafscript": [v["trafscript"] for v in res["valid"]],
            "rejected": [rj["erreur"] for rj in res["rejected"]],
            "cited": res["cited"]}


@app.post("/tts")
def tts(payload: dict = Body(...)):
    if ROLE not in ("all", "tts"):
        raise HTTPException(503, "role != tts")
    voice = payload.get("voice")
    ref = os.path.join(VOICES, voice) if voice else default_voice()
    wav = tts_atc.synth(payload["text"], ref, out_path=None, vhf=payload.get("vhf", True))
    buf = io.BytesIO()
    sf.write(buf, wav, 16000, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")
