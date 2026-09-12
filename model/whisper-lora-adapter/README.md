---
base_model: openai/whisper-small
library_name: peft
license: mit
language:
- en
pipeline_tag: automatic-speech-recognition
tags:
- lora
- peft
- whisper
- air-traffic-control
datasets:
- Jzuluaga/uwb_atcc
- Jzuluaga/atcosim_corpus
- Jzuluaga/atco2_corpus_1h
metrics:
- wer
---

# Whisper LoRA adapter for ATC speech

This checkpoint is the project's domain adapter for `openai/whisper-small`.
It is retained as an intentional research input. The base model and the
speech datasets are separate dependencies.

## Provenance and use

The training implementation is
[`08_finetune_whisper_lora.py`](../../src/08_finetune_whisper_lora.py).
The shared inference and audio preprocessing are in
[`atc_asr.py`](../../src/atc_asr.py) and
[`atc_audio.py`](../../src/atc_audio.py). The adapter configuration is
recorded in [`adapter_config.json`](adapter_config.json).

Use the project inference path when evaluating the checkpoint; changing
audio filtering or text normalization changes the experiment. Model
weights, preprocessing, corpus revision and split must all be recorded.

## What works

The checkpoint and tokenizer assets are present. The WSL portfolio audit
preserves them byte for byte. It does not claim that the speech model has
been loaded or its accuracy reproduced in this campaign.

## What does not work and limitations

WER, latency and robustness across accents: **non mesuré** in the current
WSL campaign because the speech provider and evaluation corpora were not
configured. Earlier evaluations are retained in
[`bench/results/`](../../bench/results/), clearly separated from the new
local parser and simulation checks.

Training data are centered on ATC phraseology. The adapter has not been
validated here for general transcription or operational air traffic
control. Transcription errors can propagate to callsigns and numeric orders.

## Installation and repository layout

Follow the [project README](../../README.md) for provider configuration.
This directory contains the adapter weights, configuration and tokenizer
assets; it does not contain the base Whisper model or a standalone server.

## License

The existing adapter metadata declares MIT; see the [project license](../../LICENSE).
The base model and datasets retain their own published terms.
