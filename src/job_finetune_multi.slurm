#!/bin/bash
# =====================================================================
#  Semaine 4 - entrainement MULTI-GPU (4x H100 DDP) via torchrun
#  Debit maximal : utile surtout pour whisper-medium/large.
#  Pour whisper-small, le mono-GPU bien regle (job_finetune.slurm) suffit.
#  Usage : sbatch job_finetune_multi.slurm --num-epochs 3 --run-name lora_small_x4
# =====================================================================
#SBATCH --job-name=wh-ft4
#SBATCH --account=r250127
#SBATCH --partition=short
#SBATCH --constraint=armgpu
#SBATCH --gres=gpu:h100:4
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --mem=200G
#SBATCH --time=08:00:00
#SBATCH --output=/gpfs/scratch/nimarano/atc-whisper-s4/logs/finetune4.%j.out

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
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
echo "[*] DDP 4x H100 via torchrun | args = $*"

# torchrun gere les 4 process (1 par GPU) ; le Trainer detecte le DDP.
# batch effectif = --train-bs x 4 ; pensez a baisser --num-workers (x4 process).
torchrun --standalone --nnodes=1 --nproc_per_node=4 \
  08_finetune_whisper_lora.py --num-workers 12 "$@"
echo "[OK] job multi-GPU termine."
