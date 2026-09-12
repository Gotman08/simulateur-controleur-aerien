# Local verification

The Python tests exercise the parser, callsigns, readbacks, sector graph,
simulator geometry, exercise scoring, radio filtering, voice assignment,
application helpers and mocked provider clients. They do not run a trained
speech model or validate a complete spoken interaction.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r tests/requirements.txt
python -m pytest -ra
ruff check src tests validation tools bench
```

The WSL campaign passed 205 tests. The recorded test output and dependency
versions are in [the campaign results](../bench/results/wsl-2026-09-12/).
The frontend was also built with `npm ci` and `npm run build` from `frontend/`.

These are functional checks. Their durations were collected while other
repositories were being built and are not comparative performance results.
Use [bench/run.sh](../bench/run.sh) for the separate measurement protocol.
