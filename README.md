# Simulateur Controleur Aerien

### An AI co-pilot for air traffic control: from pilot speech to simulator action, and back to voice

![Python](https://img.shields.io/badge/Python-3.11%20|%203.12-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/status-proof%20of%20concept-orange)
![HPC](https://img.shields.io/badge/HPC-ROMEO%20GH200-7b3fa0)

A proof of concept that automates the pilot and controller radio dialogue inside an air traffic
simulator. A spoken instruction is transcribed, grounded in ICAO phraseology, turned into a
validated command, executed in the BlueSky simulator, and answered by a synthesized pilot readback
voice. The full chain runs as a real time loop, with the AI models hosted on a GPU cluster and the
simulator running on a local machine.

![Radar control session](docs/assets/radar_session.gif)

> Internship project (10 week PoC), University of Reims Champagne-Ardenne (URCA). AI compute on the
> ROMEO supercomputer (NVIDIA GH200, Grace-Hopper, aarch64). Author: Nicolas Marano.

---

## Table of contents

1. [What it does](#what-it-does)
2. [Architecture](#architecture)
3. [Key results](#key-results)
4. [Demos](#demos)
5. [Pipeline stages](#pipeline-stages)
6. [How to run](#how-to-run)
7. [Repository layout](#repository-layout)
8. [Tech stack](#tech-stack)
9. [Status and roadmap](#status-and-roadmap)
10. [Limitations](#limitations)
11. [References](#references)
12. [License and acknowledgements](#license-and-acknowledgements)

---

## What it does

The target pipeline closes a full voice loop between a pilot, an AI controller, and a traffic
simulator:

```
pilot voice (VHF) -> Whisper STT -> NER + LLM with RAG (ICAO Doc 4444) -> validated JSON
                  -> BlueSky simulator (aircraft maneuver) -> synthesized pilot readback voice -> loop
```

Every brick is trained or grounded on its own, then assembled:

- Speech recognition is a Whisper model fine tuned on real, noisy air traffic control audio.
- The reasoning layer is a local LLM grounded by retrieval in a phraseology knowledge base, and by a
  graph model of the airspace sector. It outputs a strict JSON command and refuses unsafe orders.
- The command is executed in BlueSky, a research air traffic simulator, which moves the aircraft.
- The aircraft answers with a readback, synthesized in a cloned pilot voice and degraded to sound
  like a real VHF radio.

## Architecture

The AI models stay on the GPU cluster, the simulator runs on the local PC, and the two sides are
linked by an SSH tunnel. This mirrors a realistic split between a heavy compute backend and a light
operational frontend.

```
        LOCAL PC (Windows, Python 3.12)                 ROMEO cluster (armgpu node, GH200)
  +------------------------------------+   SSH tunnel   +-----------------------------------+
  | pipeline orchestrator              |  ===========>  | FastAPI inference server          |
  |   + BlueSky simulator (headless)   |  /asr /interpret  ASR  : fine tuned Whisper (GPU)  |
  |   executes TrafScript, reads state |  <-- JSON ----    LLM  : Mistral 7B + RAG + graph  |
  |   renders the radar scope          |  /tts (text)  ->  TTS  : XTTS voice cloning (CPU)  |
  +------------------------------------+  <-- wav -----  +-----------------------------------+
```

## Key results

| Brick | Metric | Result |
|---|---|---|
| Whisper fine tuning (S4) | WER on ATCO2 test, zero shot to fine tuned | 74.3% to 29.2% (about 60% relative) |
| Whisper fine tuning (S4) | Validation WER (UWB + ATCOSIM), 3 epochs | 6.68% |
| RAG to JSON (S5) | Parseable JSON on 40 real transcriptions | 100% |
| RAG to JSON (S5) | Valid orders among proposed | 27 / 33 (81.8%) |
| Safety (S5) | Out of bounds or unknown orders blocked | 5 / 5 (100%) |
| Sector graph (S5) | Shortest path ENTRY_W to EXIT_E | 101 NM, ADDWPT validated against sector fixes |
| Voice loop (S6 + S8) | Re-transcription WER of the synthesized voice | about 22 to 24% |
| Live interaction (S8) | Aircraft maneuver on spoken instruction | confirmed (heading and level changes in BlueSky) |
| Conflict prediction (CPA) | Closed form vs numerical minimum, 100 000 random geometries | max error 5.5e-4 NM (~1 m) |
| Conflict prediction (CPA) | Predicted vs measured in BlueSky, 200 encounters | MAE 0.067 NM, precision = recall = F1 = **1.000** |
| Clearance parser (local) | 68 annotated phrases (EN + FR), 10 negative/safety cases | **100%** exact, 100% unsafe rejected |
| Scenario generator (local) | 20 descriptions, 116 constraints | **100%** conformity |
| Unit tests | pytest suite over the pure modules | 110 / 110 pass |

The full mathematical derivation (CPA closed form, convexity proof, conflict
predicate), the empirical campaign against BlueSky, the exercise scoring model
and the guaranteed-conflict construction are documented with figures in
**[docs/VALIDATION.md](docs/VALIDATION.md)** — reproducible with
`src\bluesky-env\Scripts\python.exe validation\run_all.py`.

## Demos

### Realistic radar scope, built from the simulator data

A controller style radar scope rendered from the real BlueSky simulation state and the real
navigation database (waypoints, airports), centered on the Reims sector. Aircraft show a velocity
leader and a data block (callsign, flight level, ground speed).

![Radar scope Reims](docs/assets/radar_reims.png)

### Live interaction: spoken instructions deviate the aircraft

Four aircraft fly straight (heading 090). Natural language instructions are sent through the
pipeline and the aircraft deviate. Left: before. Right: after the pipeline commands.

![Before and after](docs/assets/radar_live_beforeafter.png)

Animated replay with the rotating radar sweep:

![Live radar replay](docs/assets/radar_live.gif)

### Whisper fine tuning and RAG results

| Whisper WER | RAG and safety | VHF preprocessing |
|---|---|---|
| ![WER](docs/assets/fig_wer_s4.png) | ![RAG](docs/assets/fig_rag_s5.png) | ![Mel](docs/assets/fig_mel_avant_apres_s4.png) |

### Two way voice (the aircraft talk back)

The controller speaks, the order is executed, then the pilot reads it back in the cloned aircraft
voice over VHF. Listen to the recorded radio exchange: [audio/session_radio.wav](audio/session_radio.wav)
and the per exchange files in [audio/](audio/).

## Pipeline stages

| Stage | What | Key files | Result |
|---|---|---|---|
| Foundations | VHF bandpass, airspace graph, JSON to BlueSky connector, rule based NER | `src/01_..05_`, `src/secteur_graphe.json` | reusable building blocks |
| Whisper fine tuning | LoRA fine tuning of whisper-small on ATC audio, VHF augmentation | `src/06_..10_`, `src/atc_*` | WER 74.3% to 29.2% |
| RAG OACI | phraseology knowledge base, retrieval, Mistral strict JSON, graph validation | `src/11_..16_`, `src/atc_llm.py`, `src/kb_oaci.py`, `src/graph_secteur.py` | 100% valid JSON, 100% unsafe blocked |
| Voice synthesis | XTTS zero shot voice cloning + VHF degradation, pilot readback | `src/tts_atc.py`, `src/readback.py`, `src/make_pilot_voices.py` | intelligible cloned voices |
| BlueSky live | run the simulator, execute TrafScript, read flight state, radar render | `src/bluesky_runtime.py`, `src/radar_*.py` | aircraft maneuver for real |
| Real time link | FastAPI server (ROMEO) + SSH tunnel + local orchestrator | `src/server.py`, `src/tunnel.sh`, `src/pipeline_e2e.py` | full closed loop |

## How to run

The AI side runs on the ROMEO cluster (SLURM), the simulator side runs locally.

### ROMEO (AI server)

```bash
# one time environment setup (Whisper + Mistral + RAG, then XTTS)
sbatch setup_romeo.sh           # base env, fine tuning stack
sbatch setup_rag.sh             # Mistral + embeddings
sbatch setup_tts_romeo.sh       # XTTS voice cloning

# launch the inference server (ASR + LLM on GPU, TTS on CPU)
sbatch job_server.slurm         # prints SERVER_NODE in the log
```

### Local PC (BlueSky + orchestrator)

```bash
bash setup_bluesky_local.sh                  # Python 3.12 venv + bluesky-simulator
bash tunnel.sh <SERVER_NODE>                 # forward ports 8765 and 8766

# demos
bluesky-env/Scripts/python.exe pipeline_e2e.py        # audio -> Whisper -> LLM -> BlueSky
bluesky-env/Scripts/python.exe live_demo.py           # instructions deviate the aircraft
bluesky-env/Scripts/python.exe voice_exchange.py      # controller and pilot radio exchange
bluesky-env/Scripts/python.exe radar_anim.py          # radar scope image + animation
```

### Training app (interactive radar + voice) — recommended

A single launchable application with a professional control-room interface (React + Tailwind,
pre-built — **no Node.js needed to run it**): a live radar scope with zoom/pan and flight strips,
an instructor panel that turns a natural-language description into traffic, a push-to-talk
controller position, and a full **exercise mode** where the AI builds the situation and the
student is scored like in a real check-ride.

![Training app — radar and flight strips](docs/assets/app_radar.png)

```bash
cd src
bash setup_bluesky_local.sh                                  # one time: venv + BlueSky
bluesky-env/Scripts/python.exe -m pip install -r ../requirements-local.txt
bluesky-env/Scripts/python.exe atc_app.py                    # opens http://127.0.0.1:8000
```

The AI backend is **hybrid**:

- **With ROMEO** — one command from Windows: `.\start_romeo.ps1` (submits the SLURM job, waits for
  the node, opens the SSH tunnel). Speech recognition then uses the fine-tuned Whisper,
  interpretation uses Mistral + RAG, scenario generation uses Mistral, and the pilot reads back in
  the cloned VHF voice (XTTS). The status badge shows `ROMEO`.
- **Without ROMEO** (default, fully offline): the browser's Web Speech API does speech-to-text and the
  pilot read-back voice, and a local phraseology parser (validated at 100% on 68 phrases, EN **and**
  FR) handles clearances and scenario generation. The badge shows `LOCAL`. Nothing else is required.

Workflow: the instructor types a situation (e.g. `three A320 from the north at FL300 heading 180, 8
miles apart` or `trois A320 venant du nord au niveau 300`) or loads a saved scenario from
`src/scenarios/`; the aircraft appear and fly live; the student holds the push-to-talk button (or the
space bar) and says e.g. `air france one two three four descend flight level one zero zero` (French
phraseology works too: `... descendez niveau 1 0 0`); the aircraft maneuvers and the pilot reads
back. A clearance to a callsign that is not on the scope gets **no answer**, like on a real
frequency. App code: `src/atc_app.py` (server), `src/atc_sim.py` (real-time BlueSky),
`src/atc_ai.py` (hybrid AI client), `src/atc_exercise.py` (exercise engine), `frontend/` (UI).

### Exercise mode (the AI builds the situation, the student adapts)

Pick a difficulty (Facile / Moyen / Difficile) and a duration: the engine constructs aircraft pairs
that are **mathematically guaranteed to conflict** (same arrival time at a crossing point — proof in
[docs/VALIDATION.md](docs/VALIDATION.md) §7), adds AI-generated filler traffic, wind, storm cells
and turbulence, then measures everything in real time: losses of separation (5 NM / 1000 ft),
predicted conflicts resolved before they degenerate, weather-zone penetrations, radio quality. The
final debrief shows a 0-100 score with the documented breakdown (§6), the minimum-separation
timeline, every event and every clearance:

![Exercise debrief](docs/assets/app_debrief.png)

The app leans on BlueSky's own engine for the hard parts, and the web radar renders everything it
computes:

- **Conflict detection (BlueSky CD&R, StateBased)**: predicted conflicts (amber, with time-to-CPA and
  minimum distance) and actual loss of separation (red), in 3D. The radar badge shows `CD BlueSky`.
- **Weather — wind**: `WIND` from the instructor (e.g. `200/40`); aircraft crab and their **ground speed**
  changes (shown in the data block); a wind vector is drawn on the scope.
- **Weather — storm cells and restricted zones**: click the radar to drop a `CIRCLE` area; aircraft that
  penetrate it are ringed and a banner fires (containment is computed locally because BlueSky's compiled
  `kwikdist` is incompatible with numpy 2.x).
- **Turbulence**: BlueSky's turbulence model, set from a slider.
- **Routes / FMS**: `proceed direct <fix>` (ADDWPT), vertical-speed clearances (`expedite`, `rate 1500`);
  each aircraft's FMS route and active waypoint are drawn.
- **Native BlueSky GUI**: the "GUI BlueSky natif" button exports the current situation to a `.scn` and
  launches BlueSky's official Qt/OpenGL scope on it. This needs the optional GUI dependencies:
  `bluesky-env/Scripts/python.exe -m pip install pyqt5 pyopengl`.

Python dependencies are listed in `requirements-romeo.txt` (AI side) and `requirements-local.txt`
(simulator side).

## Repository layout

```
simulateur-controleur-aerien/
  README.md
  LICENSE
  requirements-romeo.txt        AI stack (cluster side)
  requirements-local.txt        BlueSky client (local side)
  start_romeo.ps1               one-command ROMEO backend (sbatch + tunnel, Windows)
  pytest.ini / tests/           unit tests (110 tests over the pure modules)
  validation/                   mathematical + empirical validation campaign (reproducible)
  docs/VALIDATION.md            CPA derivation, BlueSky campaign, scoring model, proofs
  docs/assets/                  figures, screenshots and radar GIFs used in this page
  frontend/                     web UI source (React + TypeScript + Tailwind)
  frontend/dist/                pre-built UI served by atc_app.py (no Node.js needed)
  src/                          all runtime code (flat, see note below)
  src/scenarios/                saved training scenarios (JSON)
  model/whisper-lora-adapter/   trained LoRA adapter for whisper-small
  audio/                        recorded radio exchanges (controller and pilot)
  reports/                      exercise debrief reports (generated at use)
```

Note: `src/` is intentionally flat. The reasoning and server modules load sibling files by path
(for example `03_bluesky_connector.py`, `04_ner_extraction.py`, `graph_secteur`, `atc_callsign`,
`atc_asr`, `tts_atc`). Keeping them together preserves these imports and matches the working
directory used on the cluster.

To rebuild the web UI after changing `frontend/src/` (requires Node 20+):

```bash
cd frontend && npm install && npm run build      # output goes to frontend/dist
```

## Tech stack

- Speech recognition: OpenAI Whisper (small), LoRA fine tuning with Hugging Face Transformers and PEFT.
- Reasoning: Mistral 7B Instruct, retrieval with sentence-transformers (bge-small), numpy cosine search.
- Airspace model: a graph of the sector (nodes, segments, separation), Dijkstra routing.
- Voice synthesis: Coqui XTTS v2 (zero shot voice cloning), VHF bandpass degradation.
- Simulator: BlueSky (TU Delft), headless, driven by TrafScript.
- Serving: FastAPI and Uvicorn, WebSocket state streaming, SSH tunnel between the cluster and the local PC.
- Web UI: React 19 + TypeScript, Vite, Tailwind CSS 4, Recharts (debrief charts), lucide icons;
  canvas-rendered radar scope at 60 fps (zoom, pan, selection, trails, data blocks).
- Quality: pytest unit suite (110 tests), reproducible validation campaign (`validation/run_all.py`).
- Datasets: ATCO2, UWB-ATCC, ATCOSIM (public ATC speech corpora).
- HPC: ROMEO (URCA), NVIDIA GH200 (Grace-Hopper, aarch64), SLURM.

## Status and roadmap

Done: foundations (S1 to S3), Whisper fine tuning (S4), RAG and sector graph (S5), voice synthesis
(S6), BlueSky live and the real time loop (S8), the two way voice readback, the professional
training interface (radar, strips, instructor, radio), the scored exercise mode with debrief, and
the mathematical/empirical validation campaign (docs/VALIDATION.md).

Next: unified situation aware query that feeds the live traffic state to the LLM (S7), scripted end
to end scenarios (S9), and a quantitative evaluation over 20 scenarios with a demonstration video (S10).

## Limitations

- Speech recognition can still mishear some callsigns and digit groups on long or noisy utterances.
  An unsafe or unknown order is rejected by the validation layer rather than applied.
- Voice synthesis runs on CPU on the cluster (a known cuFFT issue with torchaudio on the GH200 GPU),
  so it is reliable but not real time fast.

## References

State of the art that informed the design (full BibTeX in `src/references.bib`):

1. Zuluaga-Gomez, J. et al. ATCO2 corpus: A Large-Scale Dataset for Research on ASR and NLU of Air Traffic Control Communications. arXiv:2211.04054, 2023. https://arxiv.org/abs/2211.04054
2. Zhang, Q. and Mott, J. H. An Exploratory Assessment of LLM's Potential Toward Flight Trajectory Reconstruction Analysis. arXiv:2401.06204, 2024. https://arxiv.org/abs/2401.06204
3. Sharifi, I., Zongo, A. and Wei, P. Fine-Tuning Large Language Models for Cooperative Tactical Deconfliction of Small Unmanned Aerial Systems. arXiv:2603.28561, 2026. https://arxiv.org/abs/2603.28561
4. Sid, D. et al. AirTrafficGen: Configurable Air Traffic Scenario Generation with Large Language Models. arXiv:2508.02269, 2025. https://arxiv.org/abs/2508.02269
5. van Doorn, J. L. P. M. Applying Large-Scale Weakly Supervised Automatic Speech Recognition to Air Traffic Control. Master's Thesis, TU Delft, 2023.
6. Su, J. and Haq, O. Fine-Tuning Whisper for American English Air Traffic Control Speech Recognition: A Data-Efficient Pipeline. Research Square, 2026. https://doi.org/10.21203/rs.3.rs-8970162/v1
7. ICAO. Doc 4444: Procedures for Air Navigation Services, Air Traffic Management (PANS-ATM), 16th edition, 2016.

## License and acknowledgements

Released under the MIT License (see `LICENSE`).

This work builds on open research and tools: the ATCO2, UWB-ATCC and ATCOSIM speech corpora, the
BlueSky simulator (TU Delft), OpenAI Whisper, Mistral, Coqui XTTS, and the ICAO radiotelephony
phraseology standards. The phraseology knowledge base is made of concise factual rule cards written
for this project, not a reproduction of any protected document.

Author: Nicolas Marano. Internship in Artificial Intelligence and Air Traffic Control, 2026.
