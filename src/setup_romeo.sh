#!/usr/bin/env bash
# =====================================================================
#  Stage IA & Controle Aerien - Semaine 4 : setup environnement ROMEO
#  Cluster heterogene : login x86_64, calcul GPU aarch64 (GH200/H100).
#  -> A LANCER SUR UN NOEUD armgpu (aarch64), pas sur le login.
#  Le HOME est quota-limite : env conda + caches + donnees sur le SCRATCH.
#  Idempotent. Auteur : Nicolas Marano
# =====================================================================
set -euo pipefail

USER_NAME="$(whoami)"
WORK="${ATC_WORK:-/gpfs/scratch/${USER_NAME}/atc-whisper-s4}"
ENV_PREFIX="$WORK/env"
PY_VER="3.11"

echo "[*] Noeud   : $(hostname)  arch=$(uname -m)"
echo "[*] WORK    : $WORK  (scratch)"
mkdir -p "$WORK"/hf_cache "$WORK"/data_proc "$WORK"/outputs "$WORK"/logs \
         "$WORK"/conda_pkgs "$WORK"/pip_cache "$WORK"/tmp

# --- caches sur le scratch (eviter le quota du HOME) ---------------------
export CONDA_PKGS_DIRS="$WORK/conda_pkgs"
export PIP_CACHE_DIR="$WORK/pip_cache"
export HF_HOME="$WORK/hf_cache"
export TMPDIR="$WORK/tmp"

# --- Miniforge aarch64 deja installe (~/miniforge3) ----------------------
source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate base
SOLVER="$(command -v mamba || command -v conda)"
echo "[*] Resolveur : $SOLVER | pkgs_dir=$CONDA_PKGS_DIRS"

# --- env conda en PREFIX sur le scratch ----------------------------------
if [ ! -x "$ENV_PREFIX/bin/python" ]; then
  echo "[*] Creation env (prefix=$ENV_PREFIX, python $PY_VER)..."
  "$SOLVER" create -y -p "$ENV_PREFIX" "python=${PY_VER}"
else
  echo "[=] Env deja present : $ENV_PREFIX"
fi
conda activate "$ENV_PREFIX"
echo "[*] python actif : $(which python) ($(python --version 2>&1))"

# --- ffmpeg + libsndfile (conda-forge, roues aarch64) --------------------
echo "[*] Installation ffmpeg / libsndfile (conda-forge)..."
"$SOLVER" install -y -p "$ENV_PREFIX" -c conda-forge ffmpeg libsndfile

# --- PyTorch (aarch64 + CUDA) --------------------------------------------
echo "[*] Installation PyTorch (CUDA cu124, aarch64)..."
python -m pip install --upgrade pip
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# --- pile HuggingFace + outils ASR ---------------------------------------
echo "[*] Installation transformers / datasets / peft / ..."
python -m pip install \
  "transformers>=4.44" \
  "datasets[audio]>=2.20" \
  "peft>=0.12" \
  "accelerate>=0.33" \
  evaluate jiwer librosa soundfile tensorboard matplotlib scipy

# --- recapitulatif des versions + test GPU (T0) --------------------------
echo "[*] Versions + test GPU (T0) :"
python - <<'PY'
import torch, transformers, datasets, peft, accelerate, evaluate, jiwer, librosa, soundfile
print("  torch         :", torch.__version__, "| CUDA build:", torch.version.cuda)
print("  cuda_available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("  device        :", torch.cuda.get_device_name(0))
    print("  bf16_supported:", torch.cuda.is_bf16_supported())
print("  transformers  :", transformers.__version__)
print("  datasets      :", datasets.__version__)
print("  peft          :", peft.__version__)
print("  accelerate    :", accelerate.__version__)
print("  jiwer/librosa/soundfile : OK")
assert torch.cuda.is_available(), "GPU NON visible (relancer sur --constraint=armgpu --gres=gpu:h100:1)"
print("[T0] SMOKE TEST OK")
PY

echo "[OK] Environnement pret : $ENV_PREFIX"
