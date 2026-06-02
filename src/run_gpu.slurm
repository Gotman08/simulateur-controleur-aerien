#!/bin/bash
# =====================================================================
#  Semaine 4 - lanceur GPU generique (eval / inference)
#  Usage : sbatch run_gpu.slurm <script.py> [args...]
#    ex.  sbatch run_gpu.slurm 09_evaluate.py --adapter outputs/lora_small/adapter
# =====================================================================
#SBATCH --job-name=wh-gpu
#SBATCH --account=r250127
#SBATCH --partition=short
#SBATCH --constraint=armgpu
#SBATCH --gres=gpu:h100:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=/gpfs/scratch/nimarano/atc-whisper-s4/logs/gpu.%j.out

set -euo pipefail
WORK="${ATC_WORK:-/gpfs/scratch/$(whoami)/atc-whisper-s4}"
export ATC_WORK="$WORK"
export HF_HOME="$WORK/hf_cache"
export TRANSFORMERS_VERBOSITY=error
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TOKENIZERS_PARALLELISM=false

source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate "$WORK/env"
cd "$WORK"
echo "[*] noeud=$(hostname) | python $*"
python "$@"
echo "[OK] termine."
