---
base_model: openai/whisper-small
library_name: peft
license: mit
language:
- en
pipeline_tag: automatic-speech-recognition
tags:
- base_model:adapter:openai/whisper-small
- lora
- peft
- transformers
- whisper
- automatic-speech-recognition
- air-traffic-control
- atc
datasets:
- Jzuluaga/uwb_atcc
- Jzuluaga/atcosim_corpus
- Jzuluaga/atco2_corpus_1h
metrics:
- wer
---

# Whisper-small LoRA adapter - Air Traffic Control ASR

LoRA (PEFT) adapter that fine-tunes [`openai/whisper-small`](https://huggingface.co/openai/whisper-small)
for **English air traffic control (ATC) radiotelephony**, using real, noisy VHF recordings and a VHF
band-pass front-end. It is the speech-to-text brick of an ATC controller **training simulator**: the
controller speaks over a (simulated) VHF channel, Whisper transcribes, a rule-based NER + LLM (RAG on
ICAO Doc 4444) turns the transcript into a validated JSON clearance, and the BlueSky simulator flies
the aircraft with a synthesized pilot readback.

## Model Details

### Model Description

- **Developed by:** Nicolas Marano (student internship project - ATC controller training simulator)
- **Model type:** LoRA adapter (PEFT) over Whisper, an encoder–decoder ASR model
- **Language(s):** English (ICAO aviation phraseology; some French phraseology is handled downstream)
- **License:** MIT (same as the project; the base `whisper-small` is also MIT)
- **Finetuned from model:** `openai/whisper-small`

### Model Sources

- **Repository:** the *ATC controller training simulator* project (see the project root `README.md`).
  Training code: `src/08_finetune_whisper_lora.py`; shared ASR helpers: `src/atc_asr.py`;
  data loading: `src/atc_data.py`.

## Uses

### Direct Use

Transcribe short (~0.4–30 s) English ATC radio transmissions sampled at 16 kHz mono. For results
consistent with training, apply the same VHF band-pass preprocessing (300–3400 Hz) used during
fine-tuning (`src/atc_audio.py::preprocess_waveform`).

### Downstream Use

STT front-end of the simulator's voice loop (served through the self-hosted
OpenAI-compatible façade, `src/server.py`):
`pilot/controller VHF → Whisper STT → NER + LLM (RAG, ICAO Doc 4444) → validated JSON → BlueSky`.

### Out-of-Scope Use

Not certified and **not for operational or real air traffic control**. Not intended for
general-purpose transcription outside the ATC domain, nor for non-English speech. It remains an
imperfect transcriber (≈29 % WER on real-world ATCO2 audio) and must not be a single point of safety.

## Bias, Risks, and Limitations

- Trained mainly on European and simulated ATC corpora (UWB-ATCC, ATCOSIM); accents, sectors, or radio
  conditions outside this distribution can degrade accuracy.
- Real-world noisy audio (ATCO2) still yields ≈29 % WER - expect transcription errors on callsigns and
  numbers, which downstream parsing and safety checks must catch.

### Recommendations

Keep the downstream safety guard (out-of-bounds / unknown-callsign rejection) and give the controller
a text fallback. Verify performance on your own audio before relying on it.

## How to Get Started with the Model

```python
import torch
from transformers import WhisperProcessor, WhisperForConditionalGeneration
from peft import PeftModel

base = "openai/whisper-small"
adapter = "model/whisper-lora-adapter"  # this folder

processor = WhisperProcessor.from_pretrained(adapter, language="en", task="transcribe")
model = WhisperForConditionalGeneration.from_pretrained(base, torch_dtype=torch.float32)
model = PeftModel.from_pretrained(model, adapter).merge_and_unload()  # fuse LoRA for fast inference
model.eval()

# `wav` = 16 kHz mono float32 waveform (ideally after VHF band-pass preprocessing)
feats = processor.feature_extractor(wav, sampling_rate=16000, return_tensors="pt").input_features
ids = model.generate(feats, language="en", task="transcribe", max_new_tokens=128)
print(processor.batch_decode(ids, skip_special_tokens=True)[0])
```

Or use the project helper: `src/atc_asr.py::build_inference_model(adapter_path=...)`.

## Training Details

### Training Data

| Split | Source(s) |
|---|---|
| train / val | `Jzuluaga/uwb_atcc` + `Jzuluaga/atcosim_corpus` |
| test | `Jzuluaga/atco2_corpus_1h` (fallback: `uwb_atcc[test]`) |

Audio resampled to 16 kHz mono; clips filtered to 0.4–30 s with non-empty transcripts; 5 % of the
concatenated training data held out as validation.

### Training Procedure

#### Preprocessing

- VHF band-pass filter (300–3400 Hz) applied to every clip; random augmentation on the training split.
- Whisper log-mel features (80 channels); text normalized with Whisper's `BasicTextNormalizer` for an
  honest, tokenizer-agnostic WER (same normalization for baseline and fine-tuned).

#### Training Hyperparameters

- **LoRA:** r = 32, α = 64, dropout = 0.05, target modules = `q_proj`, `v_proj` (attention layers,
  encoder + decoder), bias = none.
- **Optimization:** 3 epochs, learning rate 1e-3, warmup 50 steps, train batch 48 / eval batch 24,
  gradient accumulation 1.
- **Training regime:** bf16 mixed precision (autocast); evaluation (`generate`) runs in fp32 to avoid
  the input-features/weights dtype conflict. Best checkpoint selected by lowest WER.
- **Framework:** PEFT + 🤗 Transformers `Seq2SeqTrainer` (`predict_with_generate`).

#### Speeds, Sizes, Times

Trained on a single GH200 (96 GB) GPU node (HPC / SLURM). Only the LoRA adapter is saved (a few MB);
the base `whisper-small` weights are unchanged.

## Evaluation

### Testing Data, Factors & Metrics

- **Testing data:** `Jzuluaga/atco2_corpus_1h` (real-world ATC audio) for the headline WER; the
  held-out UWB + ATCOSIM validation split for in-domain WER.
- **Metric:** Word Error Rate (WER) via `jiwer`, on normalized text.

### Results

| Evaluation | WER |
|---|---|
| ATCO2 test - zero-shot `whisper-small` | 74.3 % |
| ATCO2 test - after LoRA fine-tuning | **29.2 %** (≈60 % relative reduction) |
| Validation (UWB + ATCOSIM), 3 epochs | **6.68 %** |

#### Summary

LoRA fine-tuning of `whisper-small` on domain ATC audio cuts real-world (ATCO2) WER by about 60 %
relative, at the cost of a few-MB adapter, while leaving the base model intact.

## Citation

If you use this adapter, please cite the project and the underlying datasets, e.g. the ATCO2 corpus:

> Zuluaga-Gomez, J. et al. *ATCO2 corpus: A Large-Scale Dataset for Research on ASR and NLU of Air
> Traffic Control Communications.* arXiv:2211.04054, 2023.

## Model Card Authors

Nicolas Marano.

### Framework versions

- PEFT 0.19.1
