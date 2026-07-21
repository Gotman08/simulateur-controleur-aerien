"""
Facade d'inference OpenAI-compatible 100 % LOCALE - banc de benchmark
=====================================================================
Miroir exact du contrat de src/server.py (facade ROMEO), mais adosse a des
moteurs d'inference locaux grand public :

  LLM : llama.cpp (GGUF, GPU si wheel CUDA)   POST /v1/chat/completions
  STT : faster-whisper (CTranslate2) ou       POST /v1/audio/transcriptions
        transformers Whisper (+ LoRA ATC du depot)
  TTS : Kokoro-82M (ONNX)                     POST /v1/audio/speech
  Sante : GET /v1/models

Usage (benchmarks ET mode local de l'application) :
  python local_server.py --role llm  --llm-gguf models/x.gguf --port 8901
  python local_server.py --role all  --llm-gguf ... --stt fw:small --port 8901

L'application s'y connecte comme a n'importe quel fournisseur :
  ATC_LLM_URL=http://127.0.0.1:8901   (idem STT/TTS)

Chaque requete LLM est journalisee dans --usage-log (JSONL) avec les tokens
et la duree serveur -> debit tokens/s mesure au plus pres du moteur.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

# Les wheels CUDA (llama.cpp cu124, ctranslate2) cherchent les DLL CUDA :
# celles embarquees par le wheel torch Windows font l'affaire.
try:
    import torch as _torch
    _torch_lib = os.path.join(os.path.dirname(_torch.__file__), "lib")
    if os.name == "nt" and os.path.isdir(_torch_lib):
        os.add_dll_directory(_torch_lib)
except ImportError:
    pass

STT_BANDPASS_DEFAULT = True     # miroir de server.py (transcribe bandpass=True)
KOKORO_LANG = {"a": "en-us", "b": "en-gb", "f": "fr-fr"}

_S = {}          # moteurs charges (lazy)
_LOCK = threading.Lock()
ARGS = None


# --- moteurs -----------------------------------------------------------------
def get_llm():
    with _LOCK:
        if "llm" not in _S:
            from llama_cpp import Llama
            t0 = time.perf_counter()
            _S["llm"] = Llama(model_path=ARGS.llm_gguf, n_ctx=4096,
                              n_gpu_layers=ARGS.gpu_layers, verbose=False, seed=42)
            _S["llm_load_s"] = time.perf_counter() - t0
        return _S["llm"]


def get_stt():
    """--stt 'fw:small' (faster-whisper) | 'hf:openai/whisper-small' |
    'hf-lora:<chemin adaptateur>' (whisper-small + LoRA ATC du depot)."""
    with _LOCK:
        if "stt" not in _S:
            kind, _, spec = ARGS.stt.partition(":")
            if kind == "fw":
                from faster_whisper import WhisperModel
                try:
                    m = WhisperModel(spec, device="cuda", compute_type="float16")
                    m.transcribe(__import__("numpy").zeros(1600, dtype="float32"))
                except Exception:
                    m = WhisperModel(spec, device="cpu", compute_type="int8")
                _S["stt"] = ("fw", m)
            elif kind in ("hf", "hf-lora"):
                import torch
                from transformers import WhisperForConditionalGeneration, WhisperProcessor
                base = "openai/whisper-small"
                model_id = spec if kind == "hf" else base
                proc = WhisperProcessor.from_pretrained(model_id)
                mdl = WhisperForConditionalGeneration.from_pretrained(model_id)
                if kind == "hf-lora":
                    from peft import PeftModel
                    mdl = PeftModel.from_pretrained(mdl, spec)
                    mdl = mdl.merge_and_unload()
                dev = "cuda" if torch.cuda.is_available() else "cpu"
                mdl = mdl.to(dev).eval()
                _S["stt"] = ("hf", (proc, mdl, dev))
            else:
                raise ValueError(f"backend STT inconnu : {ARGS.stt}")
        return _S["stt"]


def get_tts():
    with _LOCK:
        if "tts" not in _S:
            from kokoro_onnx import Kokoro
            _S["tts"] = Kokoro(os.path.join(HERE, "models", "kokoro-v1.0.onnx"),
                               os.path.join(HERE, "models", "voices-v1.0.bin"))
        return _S["tts"]


def _log_usage(entry):
    if ARGS.usage_log:
        with open(ARGS.usage_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def _to_16k_mono(raw_bytes):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(io.BytesIO(raw_bytes), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(int(sr), 16000)
        data = resample_poly(data, 16000 // g, int(sr) // g).astype("float32")
    return np.ascontiguousarray(data, dtype=np.float32)


# --- app ----------------------------------------------------------------------
app = FastAPI(title="ATC inference locale (facade OpenAI-compatible)")


@app.get("/v1/models")
def models():
    data = []
    if ARGS.role in ("all", "llm"):
        data.append({"id": ARGS.llm_name, "object": "model", "owned_by": "bench-local"})
    if ARGS.role in ("all", "stt"):
        data.append({"id": f"stt-{ARGS.stt}", "object": "model", "owned_by": "bench-local"})
    if ARGS.role in ("all", "tts"):
        data.append({"id": "kokoro-82m", "object": "model", "owned_by": "bench-local"})
    return {"object": "list", "data": data}


@app.post("/v1/chat/completions")
def chat_completions(payload: dict = Body(...)):
    if ARGS.role not in ("all", "llm"):
        raise HTTPException(503, "role != llm")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(400, "messages vide")
    # Mistral v0.3 : le template GGUF de llama.cpp PERD le role system (verifie
    # empiriquement). Le template officiel Mistral prefixe le system au premier
    # message user : on reproduit ce comportement quand --merge-system est actif.
    if ARGS.merge_system and messages and messages[0].get("role") == "system":
        sys_txt = str(messages[0].get("content") or "")
        rest = [dict(m) for m in messages[1:]]
        for m in rest:
            if m.get("role") == "user":
                m["content"] = f"{sys_txt}\n\n{m.get('content') or ''}"
                break
        else:
            rest.insert(0, {"role": "user", "content": sys_txt})
        messages = rest
    try:
        max_tokens = int(payload.get("max_tokens") or 512)
        temperature = float(payload.get("temperature") or 0.0)
    except (TypeError, ValueError):
        raise HTTPException(400, "max_tokens/temperature invalides") from None
    llm = get_llm()
    t0 = time.perf_counter()
    with _LOCK:                      # llama.cpp n'est pas thread-safe
        out = llm.create_chat_completion(messages=messages, max_tokens=max_tokens,
                                         temperature=temperature)
    dt = time.perf_counter() - t0
    usage = out.get("usage", {})
    _log_usage({"model": ARGS.llm_name, "duration_s": round(dt, 4),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens")})
    out["model"] = str(payload.get("model") or ARGS.llm_name)
    return out


@app.post("/v1/audio/transcriptions")
async def transcriptions(file: UploadFile = File(...), model: str = Form(default=""),
                         response_format: str = Form(default="json")):
    if ARGS.role not in ("all", "stt"):
        raise HTTPException(503, "role != stt")
    try:
        arr = _to_16k_mono(await file.read())
    except Exception:
        raise HTTPException(400, "fichier audio illisible") from None
    if ARGS.stt_bandpass:
        from atc_audio import preprocess_waveform
        arr = preprocess_waveform(arr, training=False)
    kind, engine = get_stt()
    with _LOCK:
        if kind == "fw":
            segments, _ = engine.transcribe(arr, language="en", beam_size=1)
            text = " ".join(s.text.strip() for s in segments).strip()
        else:
            import torch
            proc, mdl, dev = engine
            feats = proc(arr, sampling_rate=16000, return_tensors="pt").input_features.to(dev)
            with torch.no_grad():
                ids = mdl.generate(feats, language="en", task="transcribe", max_new_tokens=200)
            text = proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
    return {"text": text}


@app.post("/v1/audio/speech")
def audio_speech(payload: dict = Body(...)):
    if ARGS.role not in ("all", "tts"):
        raise HTTPException(503, "role != tts")
    text = str(payload.get("input") or "")
    if not text:
        raise HTTPException(400, "input vide")
    fmt = str(payload.get("response_format") or "wav").lower()
    if fmt != "wav":
        raise HTTPException(400, "seul response_format=wav est supporte")
    voice = str(payload.get("voice") or "af_bella")
    lang = KOKORO_LANG.get(voice[:1], "en-us")
    import soundfile as sf
    tts = get_tts()
    with _LOCK:
        try:
            samples, sr = tts.create(text, voice=voice, speed=1.0, lang=lang)
        except Exception as e:
            raise HTTPException(400, f"voix '{voice}' indisponible : {e}") from None
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")


def main():
    global ARGS
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--role", choices=["all", "llm", "stt", "tts"], default="all")
    p.add_argument("--llm-gguf", default="")
    p.add_argument("--llm-name", default="")
    p.add_argument("--gpu-layers", type=int, default=-1)
    p.add_argument("--stt", default="fw:small")
    p.add_argument("--merge-system", action="store_true",
                   help="fusionner le message system dans le premier user "
                        "(modeles sans role system, ex. Mistral v0.3)")
    p.add_argument("--stt-bandpass", type=int, default=int(STT_BANDPASS_DEFAULT))
    p.add_argument("--port", type=int, default=8901)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--usage-log", default="")
    p.add_argument("--warm", action="store_true", help="charger les moteurs au demarrage")
    ARGS = p.parse_args()
    if not ARGS.llm_name and ARGS.llm_gguf:
        ARGS.llm_name = os.path.splitext(os.path.basename(ARGS.llm_gguf))[0]
    if ARGS.warm:
        if ARGS.role in ("all", "llm") and ARGS.llm_gguf:
            get_llm()
        if ARGS.role in ("all", "stt"):
            get_stt()
        if ARGS.role in ("all", "tts"):
            get_tts()
    import uvicorn
    uvicorn.run(app, host=ARGS.host, port=ARGS.port, log_level="warning")


if __name__ == "__main__":
    main()
