#!/usr/bin/env bash
# =====================================================================
#  Campagne VoiceChat-11B - execution cote noeud de calcul ROMEO
#  A lancer DANS le job d'allocation :
#     srun --jobid=<id> --overlap bash /dev/shm/vc/run_campaign.sh <etape>
#  Etapes :
#     smoke   : echantillon officiel NVIDIA (verifie que le modele tourne)
#     pilote  : 3 stimuli ATC (verifie l'invite systeme + les appels d'outil)
#     complet : les 100 stimuli (4 conditions x 25 clairances)
# =====================================================================
set -uo pipefail
VC=/dev/shm/vc
ETAPE="${1:-pilote}"

source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate "$VC/env"
export PYTHONPATH="$VC/Speech:${PYTHONPATH:-}"
# la libstdc++ du systeme (GCC 11, CXXABI_1.3.13) est trop ancienne pour les
# bibliotheques conda (libicui18n -> CXXABI_1.3.15) : l'env doit primer, sinon
# meme `import sqlite3` echoue et casse la chaine d'import de NeMo.
export LD_LIBRARY_PATH="$VC/env/lib:${LD_LIBRARY_PATH:-}"
export HF_HOME="$VC/hf" TMPDIR="$VC/tmp"
# AUCUNE ecriture sur GPFS : les trois espaces (home/scratch/projet) sont
# satures, ecriture refusee (Errno 122). On deplace le HOME lui-meme sur le
# disque RAM APRES l'activation conda, plus tous les caches qui ignorent
# XDG_CACHE_HOME (Triton compile ses noyaux au premier appel et ecrivait
# dans $HOME/.triton -> OSError 122 sur chaque stimulus).
mkdir -p "$VC/cache/mpl" "$VC/cache/triton" "$VC/cache/inductor" \
         "$VC/cache/numba" "$VC/home"
export HOME="$VC/home"
export XDG_CACHE_HOME="$VC/cache" MPLCONFIGDIR="$VC/cache/mpl"
export TRITON_CACHE_DIR="$VC/cache/triton"
export TORCHINDUCTOR_CACHE_DIR="$VC/cache/inductor"
export NUMBA_CACHE_DIR="$VC/cache/numba"
export TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE=0

cd "$VC"
echo "=== etape=$ETAPE  noeud=$(hostname)  $(date) ==="

case "$ETAPE" in
  smoke)
    python "$VC/Speech/examples/speechlm2/offline_voicechat_infer.py" \
      --checkpoint "$VC/ckpt" \
      --wav "$VC/Speech/examples/speechlm2/sample_audio/sample_general.wav" \
      --output-dir "$VC/out/smoke" 2>&1 | tail -40
    ;;
  pilote)
    python "$VC/voicechat_infer.py" --checkpoint "$VC/ckpt" \
      --manifest "$VC/stim/manifest.json" --output-dir "$VC/out/pilote" \
      --mode both --limit 3 2>&1 | tail -60
    ;;
  complet)
    python "$VC/voicechat_infer.py" --checkpoint "$VC/ckpt" \
      --manifest "$VC/stim/manifest.json" --output-dir "$VC/out/complet" \
      --mode both 2>&1 | tail -200
    ;;
  *)
    echo "etape inconnue : $ETAPE" ; exit 2 ;;
esac
echo "=== fin etape=$ETAPE  $(date) ==="
