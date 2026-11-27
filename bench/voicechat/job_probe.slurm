#!/bin/bash
# =====================================================================
#  Sondage de faisabilite : NVIDIA-NemotronLabs-VoiceChat-11B sur ROMEO
#  Les noeuds GPU sont aarch64 (Grace + H100) : on verifie AVANT toute
#  build longue la disponibilite des roues torch 2.10 / transformers /
#  mamba-ssm / causal-conv1d et l'acces reseau (PyPI, GitHub, HF).
#  Usage : sbatch job_probe.slurm
# =====================================================================
#SBATCH --job-name=vc-probe
#SBATCH --account=r250127
#SBATCH --partition=instant
#SBATCH --constraint=armgpu
#SBATCH --gres=gpu:h100:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=00:50:00
#SBATCH --output=/gpfs/scratch/nimarano/atc-voicechat/logs/probe.%j.out

set -uo pipefail
WORK="/gpfs/scratch/$(whoami)/atc-voicechat"
mkdir -p "$WORK"/logs "$WORK"/tmp "$WORK"/pip_cache

echo "=== NOEUD ==="
hostname; uname -m; nproc; free -g | head -2
echo "=== GPU ==="
nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv
echo "=== CUDA modules ==="
module avail 2>&1 | tr ' ' '\n' | grep -i cuda
for m in cuda/12.6 nvhpc/nvhpc/24.11; do
  echo "--- module $m ---"
  ( module load $m 2>&1 && which nvcc && nvcc --version | tail -2 ) || echo "  echec $m"
done
echo "=== conda ==="
source "$HOME/miniforge3/etc/profile.d/conda.sh" && conda activate base && python -V && which python || echo "conda KO"

echo "=== reseau ==="
curl -sI -m 20 https://pypi.org/simple/ | head -1
curl -sI -m 20 https://github.com | head -1
curl -sI -m 20 https://huggingface.co | head -1
curl -sI -m 20 https://download.pytorch.org/whl/cu128/ | head -1

echo "=== roues disponibles (index PyPI, plateforme du noeud) ==="
export PIP_CACHE_DIR="$WORK/pip_cache" TMPDIR="$WORK/tmp"
python -m pip --version
for pkg in torch transformers tokenizers lhotse causal-conv1d mamba-ssm nemo_toolkit; do
  echo "--- $pkg ---"
  python -m pip index versions "$pkg" 2>&1 | head -3
done

echo "=== roues torch 2.10 aarch64 : test de resolution (dry-run, sans install) ==="
for idx in "https://download.pytorch.org/whl/cu128" "https://download.pytorch.org/whl/cu126" ""; do
  echo "--- index='${idx:-PyPI}' ---"
  if [ -n "$idx" ]; then
    python -m pip download --no-deps --dry-run -d "$WORK/tmp/dl" torch==2.10.0 --index-url "$idx" 2>&1 | tail -3
  else
    python -m pip download --no-deps --dry-run -d "$WORK/tmp/dl" torch==2.10.0 2>&1 | tail -3
  fi
done

echo "=== roues mamba-ssm / causal-conv1d : source ou binaire ? ==="
python -m pip download --no-deps --no-build-isolation --dry-run -d "$WORK/tmp/dl" "causal-conv1d==1.6.2.post1" 2>&1 | tail -5
python -m pip download --no-deps --no-build-isolation --dry-run -d "$WORK/tmp/dl" "mamba-ssm==2.3.2.post1" 2>&1 | tail -5

echo "=== depot NeMo (branche nemotron-labs-voicechat) ==="
git ls-remote --heads https://github.com/NVIDIA-NeMo/Speech.git nemotron-labs-voicechat 2>&1 | head -3

echo "=== taille du checkpoint HF ==="
curl -s -m 30 "https://huggingface.co/api/models/nvidia/NVIDIA-NemotronLabs-VoiceChat-11B?blobs=true" \
  | python -c "import json,sys; d=json.load(sys.stdin); s=d.get('siblings',[]); tot=sum(x.get('size',0) or 0 for x in s); print('fichiers:',len(s)); print('taille totale: %.1f Go'%(tot/1e9)); [print('  ',x['rfilename'], x.get('size')) for x in s[:40]]" 2>&1 | head -50

echo "=== FIN SONDAGE ==="
