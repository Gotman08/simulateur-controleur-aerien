# Reproducible local campaign

The current portfolio report uses the WSL campaign in
[`results/wsl-2026-09-12/`](results/wsl-2026-09-12/). It calls the existing
production parser, conflict detector, exercise constructor and BlueSky
runtime. Every parser decision and geometry case is saved, together with
each timing repetition and its warmup flag.

```bash
python3.12 -m venv .venv-bench
source .venv-bench/bin/activate
python -m pip install -r bench/requirements-wsl.txt
bash bench/run.sh
python bench/plot.py --latest
```

Run the commands from the repository root. Each run writes a fresh timestamped
directory under `bench/results/local/`. Existing output directories are rejected
to prevent interrupted or repeated campaigns from mixing their files.
Use `python bench/plot.py` without `--latest` to regenerate the committed campaign.
An explicit `--output` can select a different, new directory. The optional
`--skip-simulator` flag records the simulator as `non mesuré`.

The protocol excludes one warmup and keeps five timed repetitions for each
input size. Parser prefixes contain 16, 68 and 116 annotated clearances;
their language mix differs, so the graph does not establish asymptotic
scaling. BlueSky trials contain 5, 25 and 100 aircraft, using the same seeded
initial traffic at each repetition. Reported speed is actual simulated
seconds divided by wall-clock seconds. Setup, aircraft creation and model
loading are outside that timer. Graphs show the median and interquartile
range, using linear quantile interpolation. These intervals describe the
observed spread and are not confidence intervals.

BlueSky is initialized with the recorded `bench/bluesky.cfg` in the ignored
`.bench-runtime/` directory. The benchmark then uses the unchanged application
wrapper for traffic creation, resets, state reads and time stepping. This keeps
an existing user's BlueSky settings out of the experiment.

The numerical geometry reference samples straight-line trajectories every
0.05 seconds over 300 seconds. It cannot resolve every threshold boundary;
ambiguous cases are marked in the CSV. The constructor check uses an
independent relative-motion calculation. Neither is an operational flight
safety validation.

`measure_local.py` records the machine, exposed processors and memory,
interpreter, installed packages, source hashes, seeds and all inputs.
`plot.py` regenerates the summary and both SVG themes in `docs/assets/`.
The optional PNG files are local previews and are ignored by Git.

## Historical experiments

The existing `sim_bench.py`, `llm_bench.py`, `stt_bench.py`, `tts_bench.py`,
`e2e_bench.py`, `human_e2e.py` and `run_all.py` describe earlier experiments.
Their JSON files remain at the top of `results/` and their figures under
`figures/`. They are preserved as historical records and are not presented
as new measurements in the portfolio README.

Speech-recognition WER, LLM accuracy, speech-synthesis intelligibility,
complete voice-loop latency and ROMEO parity: **non mesuré** in this WSL
campaign because no corresponding model services were configured. A GPU
being visible does not by itself reproduce their providers, models,
audio corpora or preprocessing. The previous scripts and result files
remain available for a separate replay with those dependencies.

The local corpus is hand-authored and reuses development examples. Its
extended cases reveal parser failures, but neither stratum is a held-out
sample of spontaneous controller speech. The full parser contract includes
vertical-speed commands; the older LLM comparison filters those commands.
Those accuracy figures must not be compared as identical tasks.
