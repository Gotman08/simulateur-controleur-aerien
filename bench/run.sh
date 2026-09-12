#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export MPLBACKEND=Agg
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"${PYTHON:-python3}" bench/measure_local.py "$@"
