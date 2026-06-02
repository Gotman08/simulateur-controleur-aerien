#!/bin/bash
# =====================================================================
#  Stage IA & Controle Aerien - Semaine 4 : job d'entrainement (T5)
#  Fine-tuning LoRA de Whisper sur 1 GPU GH200 (noeud armgpu aarch64).
#  Usage : sbatch job_finetune.slurm [args pour 08_finetune_whisper_lora.py]
#    ex.  sbatch job_finetune.slurm --num-epochs 3 --run-name lora_small
# =====================================================================
#SBATCH --job-name=wh-ft
#SBATCH --account=r250127
#SBATCH --partition=short
#SBATCH --constraint=armgpu
#SBATCH --gres=gpu:h100:1
#SBATCH --cpus-per-task=32
#SBATCH --mem=96G
#SBATCH --time=08:00:00
#SBATCH --output=/gpfs/scratch/nimarano/atc-whisper-s4/logs/finetune.%j.out

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

echo "[*] noeud=$(hostname) arch=$(uname -m)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo "[*] python=$(which python)"
echo "[*] args = $*"

srun python 08_finetune_whisper_lora.py "$@"
echo "[OK] job termine."
