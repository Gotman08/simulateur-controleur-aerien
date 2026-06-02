#!/bin/bash
# =====================================================================
#  Semaine 5 - lanceur GPU pour le RAG/LLM (cache modeles sur PROJET)
#  Usage : sbatch job_rag.slurm <script.py> [args...]
#    ex.  sbatch job_rag.slurm 13_llm_interpret.py
# =====================================================================
#SBATCH --job-name=wh-rag
#SBATCH --account=r250127
#SBATCH --partition=short
#SBATCH --constraint=armgpu
#SBATCH --gres=gpu:h100:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=80G
#SBATCH --time=01:00:00
#SBATCH --output=/gpfs/scratch/nimarano/atc-whisper-s4/logs/rag.%j.out

set -euo pipefail
WORK="/gpfs/scratch/$(whoami)/atc-whisper-s4"
export ATC_WORK="$WORK"
export HF_HOME="$WORK/hf_cache"                          # datasets/whisper/embedder = scratch
export ATC_LLM_CACHE="/gpfs/projet/r250127/hf_cache/hub" # gros LLM Mistral = projet (cache_dir)
export TRANSFORMERS_VERBOSITY=error
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TOKENIZERS_PARALLELISM=false

source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate "$WORK/env"
cd "$WORK"
echo "[*] node=$(hostname) arch=$(uname -m) | python $*"
python "$@"
echo "[OK] termine."
