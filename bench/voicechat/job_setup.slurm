#!/bin/bash
# =====================================================================
#  Campagne VoiceChat-11B sur ROMEO - job d'allocation et de preparation
#  ---------------------------------------------------------------------
#  CONTRAINTE MAJEURE : les trois espaces GPFS (home / scratch / projet)
#  sont satures (17,5 Go pour 15 Go de quota souple, delai de grace
#  expire -> toute ecriture est refusee) et plafonnes a 20 Go durs, alors
#  que le checkpoint pese 44,4 Go. TOUT se passe donc sur le disque RAM
#  du noeud (/dev/shm, 239 Go) : environnement conda, depot NeMo,
#  checkpoint, sorties. Rien n'est ecrit sur GPFS, rien n'est supprime.
#
#  Le job prepare l'environnement puis RESTE VIVANT : on pilote ensuite
#  l'inference via  srun --jobid=<id> --overlap  depuis le noeud de login.
#
#  Usage : sbatch job_setup.slurm      (journal : /dev/shm/vc/logs/setup.log)
# =====================================================================
#SBATCH --job-name=vc-setup
#SBATCH --account=r250127
#SBATCH --partition=short
#SBATCH --constraint=armgpu
#SBATCH --gres=gpu:h100:1
#SBATCH --cpus-per-task=32
#SBATCH --mem=250G
#SBATCH --time=23:30:00
#SBATCH --output=/dev/shm/vc_setup.%j.out

set -uo pipefail
VC=/dev/shm/vc
mkdir -p "$VC"/{logs,ckpt,out,tmp,pkgs}
LOG="$VC/logs/setup.log"
exec > >(tee -a "$LOG") 2>&1

ts() { date +"%H:%M:%S"; }
stage() { echo ""; echo "########## [$(ts)] $* ##########"; }

echo "NODE=$(hostname) JOB=$SLURM_JOB_ID ARCH=$(uname -m) DATE=$(date)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
df -h /dev/shm | tail -1

export TMPDIR="$VC/tmp"
export PIP_CACHE_DIR="$VC/pkgs/pip"
export CONDA_PKGS_DIRS="$VC/pkgs/conda"
export HF_HOME="$VC/hf"
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TOKENIZERS_PARALLELISM=false
export MAX_JOBS=32

# ---------------------------------------------------------------------
stage "0. telechargement du checkpoint EN TACHE DE FOND (44,4 Go)"
# ---------------------------------------------------------------------
cat > "$VC/dl.sh" <<'EOS'
set -uo pipefail
VC=/dev/shm/vc
source "$HOME/miniforge3/etc/profile.d/conda.sh"; conda activate base
export HF_HOME="$VC/hf" TMPDIR="$VC/tmp" PIP_CACHE_DIR="$VC/pkgs/pip"
export HF_HUB_DISABLE_PROGRESS_BARS=1 HF_XET_HIGH_PERFORMANCE=1
python -m pip install -q --target "$VC/hfcli" "huggingface_hub[hf_xet,cli]" 2>&1 | tail -2
export PYTHONPATH="$VC/hfcli:${PYTHONPATH:-}"
echo "[dl $(date +%H:%M:%S)] debut"
for i in 1 2 3; do
  python -c "
from huggingface_hub import snapshot_download
p = snapshot_download('nvidia/NVIDIA-NemotronLabs-VoiceChat-11B',
                      local_dir='/dev/shm/vc/ckpt', max_workers=16)
print('OK', p)
" && break
  echo "[dl] tentative $i echouee, nouvelle tentative dans 30 s"; sleep 30
done
echo "[dl $(date +%H:%M:%S)] fin ; contenu :"
du -sh "$VC/ckpt"; ls -la "$VC/ckpt"
touch "$VC/DL_DONE"
EOS
bash "$VC/dl.sh" > "$VC/logs/download.log" 2>&1 &
DLPID=$!
echo "telechargement lance (pid $DLPID) -> $VC/logs/download.log"

# ---------------------------------------------------------------------
stage "1. environnement conda python 3.12 sur /dev/shm"
# ---------------------------------------------------------------------
source "$HOME/miniforge3/etc/profile.d/conda.sh"
ENVP="$VC/env"
if [ ! -x "$ENVP/bin/python" ]; then
  conda create -y -q -p "$ENVP" python=3.12 2>&1 | tail -5
fi
conda activate "$ENVP"
python -V; which python

# ---------------------------------------------------------------------
stage "2. PyTorch 2.10 (aarch64 + CUDA)"
# ---------------------------------------------------------------------
python -m pip install -q --upgrade pip setuptools wheel 2>&1 | tail -2
INSTALLED=""
for IDX in "https://download.pytorch.org/whl/cu128" "https://download.pytorch.org/whl/cu126" "PYPI"; do
  echo "--- tentative index=$IDX ---"
  if [ "$IDX" = "PYPI" ]; then
    python -m pip install -q torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 2>&1 | tail -5
  else
    python -m pip install -q torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url "$IDX" 2>&1 | tail -5
  fi
  if python -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
    INSTALLED="$IDX"; break
  fi
  echo "  -> torch absent ou CUDA indisponible avec $IDX"
  python -c "import torch;print('  version installee:',torch.__version__,'cuda build:',torch.version.cuda)" 2>/dev/null
done
echo "TORCH_INDEX_RETENU=$INSTALLED"
python -c "
import torch
print('torch', torch.__version__, '| cuda build', torch.version.cuda, '| dispo', torch.cuda.is_available())
print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'aucun')
print('bf16', torch.cuda.is_bf16_supported() if torch.cuda.is_available() else None)
"

# ---------------------------------------------------------------------
stage "3. pile HuggingFace / audio (versions du modele card)"
# ---------------------------------------------------------------------
python -m pip install -q transformers==4.56.0 tokenizers==0.22.0 lhotse==1.32.2 \
    "huggingface-hub==0.34.4" hf-xet==1.1.9 jinja2 einops soundfile librosa \
    jiwer omegaconf hydra-core sentencepiece webdataset braceexpand editdistance \
    pyloudnorm 2>&1 | tail -8
python -m pip install -q torchcodec==0.10.0 2>&1 | tail -3
python -m pip install -q torch_audiomentations 2>&1 | tail -3
python -c "import transformers, lhotse; print('transformers', transformers.__version__, '| lhotse', lhotse.__version__)"

# ---------------------------------------------------------------------
stage "4. depot NeMo (branche nemotron-labs-voicechat)"
# ---------------------------------------------------------------------
cd "$VC"
if [ ! -d "$VC/Speech/.git" ]; then
  git clone -q --depth 1 --branch nemotron-labs-voicechat https://github.com/NVIDIA-NeMo/Speech.git "$VC/Speech" 2>&1 | tail -3
fi
cd "$VC/Speech" && git log --oneline -1 && ls

# ---------------------------------------------------------------------
stage "5. noyaux Mamba (compilation source, aucune roue aarch64)"
# ---------------------------------------------------------------------
module load cuda/12.6 2>/dev/null || true
export CUDA_HOME="${CUDA_HOME:-$(dirname $(dirname $(which nvcc 2>/dev/null)))}"
echo "CUDA_HOME=$CUDA_HOME"; nvcc --version | tail -2
python -m pip install -q ninja packaging wheel 2>&1 | tail -2
export CAUSAL_CONV1D_FORCE_BUILD=TRUE MAMBA_FORCE_BUILD=TRUE
echo "[$(ts)] build causal-conv1d ..."
python -m pip install -v --no-build-isolation causal-conv1d==1.6.2.post1 \
    > "$VC/logs/build_causal.log" 2>&1 && echo "  causal-conv1d OK" || echo "  causal-conv1d ECHEC (voir logs/build_causal.log)"
echo "[$(ts)] build mamba-ssm ..."
python -m pip install -v --no-build-isolation mamba-ssm==2.3.2.post1 \
    > "$VC/logs/build_mamba.log" 2>&1 && echo "  mamba-ssm OK" || echo "  mamba-ssm ECHEC (voir logs/build_mamba.log)"
python -c "
try:
    import causal_conv1d, mamba_ssm
    print('noyaux mamba importables :', causal_conv1d.__version__, mamba_ssm.__version__)
except Exception as e:
    print('IMPORT KO :', type(e).__name__, e)
"

# ---------------------------------------------------------------------
stage "6. etat du telechargement"
# ---------------------------------------------------------------------
while [ ! -f "$VC/DL_DONE" ]; do
  echo "  [$(ts)] checkpoint : $(du -sh $VC/ckpt 2>/dev/null | cut -f1) / 44,4 Go"
  sleep 120
done
du -sh "$VC/ckpt"; ls -la "$VC/ckpt"

stage "7. PRET - le job reste vivant pour l'inference pilotee (srun --overlap)"
echo "JOBID=$SLURM_JOB_ID NODE=$(hostname)"
touch "$VC/SETUP_DONE"
sleep infinity
