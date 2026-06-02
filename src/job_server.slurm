#!/bin/bash
# =====================================================================
#  Semaines 6&8 (V2) : serveur d'inference ATC (Whisper+Mistral+XTTS)
#  Service FastAPI long-running sur un noeud armgpu ; pilote depuis le PC
#  local via tunnel SSH. Usage : sbatch job_server.slurm
#  -> recuperer "SERVER_NODE=..." dans le log pour ouvrir le tunnel.
# =====================================================================
#SBATCH --job-name=wh-server
#SBATCH --account=r250127
#SBATCH --partition=short
#SBATCH --constraint=armgpu
#SBATCH --gres=gpu:h100:1
#SBATCH --cpus-per-task=24
#SBATCH --mem=90G
#SBATCH --time=04:00:00
#SBATCH --output=/gpfs/scratch/nimarano/atc-whisper-s4/logs/server.%j.out

set -euo pipefail
WORK="/gpfs/scratch/$(whoami)/atc-whisper-s4"
export ATC_WORK="$WORK"
export HF_HOME="$WORK/hf_cache"
export XDG_DATA_HOME="$WORK/tts_data"
export COQUI_TOS_AGREED=1
export TRANSFORMERS_VERBOSITY=error
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TOKENIZERS_PARALLELISM=false

source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate "$WORK/env"
cd "$WORK"

echo "SERVER_NODE=$(hostname) PORT_ASRLLM=8765 PORT_TTS=8766"
echo "[server] demarrage : GPU0=asrllm:8765 (Whisper+Mistral), CPU=tts:8766 (XTTS) ..."
CUDA_VISIBLE_DEVICES=0 ATC_ROLE=asrllm python -m uvicorn server:app --host 0.0.0.0 --port 8765 \
    --log-level warning > "$WORK/logs/srv_asrllm.out" 2>&1 &
P1=$!
ATC_ROLE=tts ATC_TTS_DEVICE=cpu CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=16 \
    python -m uvicorn server:app --host 0.0.0.0 --port 8766 \
    --log-level warning > "$WORK/logs/srv_tts.out" 2>&1 &
P2=$!
echo "[server] PIDs asrllm=$P1 tts=$P2 (logs: srv_asrllm.out / srv_tts.out)"
wait
