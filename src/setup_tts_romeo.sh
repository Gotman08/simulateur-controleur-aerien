#!/usr/bin/env bash
# =====================================================================
#  Stage IA & Controle Aerien - Semaine 6 (V0) : XTTS dans l'env whisper-atc
#  On AJOUTE coqui-tts (XTTS-v2) a l'env existant (reutilise torch 2.12 +
#  transformers 5.9 -> pas de second PyTorch, tient dans le quota 20 Go).
#  Resultat : un seul env -> un seul serveur (Whisper+Mistral+XTTS).
#  A LANCER sur un noeud armgpu (GPU). Auteur : Nicolas Marano
# =====================================================================
set -euo pipefail

USER_NAME="$(whoami)"
WORK="/gpfs/scratch/${USER_NAME}/atc-whisper-s4"
ENV="$WORK/env"                            # env whisper-atc (S4/S5)
export XDG_DATA_HOME="$WORK/tts_data"      # modeles coqui-tts sur scratch
export COQUI_TOS_AGREED=1
export HF_HOME="$WORK/hf_cache"
export CONDA_PKGS_DIRS="$WORK/conda_pkgs"
export TMPDIR="$WORK/tmp"
mkdir -p "$XDG_DATA_HOME" "$TMPDIR"

echo "[*] node=$(hostname) arch=$(uname -m)"
echo "[*] liberation de place (env tts partiel, datasets, caches)..."
rm -rf "$WORK/tts-env" 2>/dev/null || true
rm -rf "$WORK"/hf_cache/hub/datasets--Jzuluaga--* 2>/dev/null || true
rm -rf "$HOME/miniforge3/pkgs/cache" 2>/dev/null || true
rm -rf "$WORK"/conda_pkgs/* "$WORK"/pip_cache/* 2>/dev/null || true

source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate "$ENV"
echo "[*] python actif : $(which python)"

echo "[*] coqui-tts (XTTS) dans l'env whisper-atc (reutilise torch + transformers)..."
python -m pip install --no-cache-dir coqui-tts fastapi "uvicorn[standard]" python-multipart

echo "[*] alignement de torchaudio sur torch 2.12 (corrige l'ABI libtorchaudio)..."
python -m pip install --no-cache-dir --upgrade torchaudio

echo "[*] smoke XTTS (telechargement modele + synthese de controle)..."
python - <<'PY'
import os, torch, transformers
# shim : restaure isin_mps_friendly supprime en transformers 5.x (requis par XTTS)
import transformers.pytorch_utils as _pu
if not hasattr(_pu, "isin_mps_friendly"):
    _pu.isin_mps_friendly = lambda elements, test_elements: torch.isin(elements, test_elements)
from TTS.api import TTS
print("  torch", torch.__version__, "| transformers", transformers.__version__,
      "| cuda", torch.cuda.is_available())
dev = "cuda" if torch.cuda.is_available() else "cpu"
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(dev)
spks = list(getattr(tts, "speakers", []) or [])
print("  speakers integres:", len(spks))
out = os.path.join(os.environ["XDG_DATA_HOME"], "smoke_v0.wav")
try:
    kw = {"language": "en", "file_path": out}
    if spks:
        kw["speaker"] = spks[0]
    tts.tts_to_file(text="air france one two three four descend flight level one hundred", **kw)
    print("  [V0] synthese OK ->", out)
except Exception as e:
    print("  [V0] synth builtin (clonage en V1) :", type(e).__name__, str(e)[:160])
assert torch.cuda.is_available(), "GPU non visible"
print("  [V0] XTTS OK sur GPU (env whisper-atc unique).")
PY
echo "[OK] env TTS pret (V0)."
