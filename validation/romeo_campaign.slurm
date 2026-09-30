#!/usr/bin/env bash
# Submit from the repository root: sbatch --account=<account> validation/romeo_campaign.slurm
# Prepare .venv, frontend/node_modules and Playwright on a compute node first.
# Optional: export NODE_BIN=/path/to/node/bin PLAYWRIGHT_BROWSERS_PATH=/path/to/browsers
# Do not edit the checkout while this array is running.
#SBATCH --job-name=atc-validation
#SBATCH --partition=instant
#SBATCH --constraint=x64cpu
#SBATCH --time=00:10:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --array=0-14%4
#SBATCH --output=atc-validation-%A_%a.out
#SBATCH --error=atc-validation-%A_%a.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit from the repository root}"
romeo_load_x64cpu_env
spack load python@3.12.5
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
if [[ -n "${NODE_BIN:-}" ]]; then export PATH="$NODE_BIN:$PATH"; fi
out="reports/romeo-${SLURM_ARRAY_JOB_ID}"
mkdir -p "$out"
index="${SLURM_ARRAY_TASK_ID}"
if (( index < 12 )); then
    counts=(20 100 250 1000)
    seeds=(7 19 41)
    count="${counts[index / 3]}"
    seed="${seeds[index % 3]}"
    .venv/bin/python validation/romeo_campaign.py sim --aircraft "$count" --seed "$seed" --output "$out/sim-$count-$seed.json"
elif (( index == 12 )); then
    .venv/bin/python validation/romeo_campaign.py api --output "$out/api.json"
elif (( index == 13 )); then
    cd frontend
    npm run build
    npm test
    npm run test:e2e
    npx playwright test --config=playwright.live.config.ts
else
    .venv/bin/pytest --junitxml="$out/unit.xml"
    .venv/bin/ruff check src tests validation tools bench
fi
