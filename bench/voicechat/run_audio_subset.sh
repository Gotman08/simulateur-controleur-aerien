#!/usr/bin/env bash
# =====================================================================
#  Sous-echantillon AUDIO de la campagne VoiceChat
#  Le decodage du codec audio coute ~230 s par stimulus contre ~30 s pour
#  la seule generation : on ne le fait donc que sur quelques cas, pour
#  disposer de la parole reellement produite (ecoute qualitative,
#  intelligibilite aller-retour avec le juge STT fixe, RTF).
#
#  Usage : srun --jobid=<id> --overlap bash /dev/shm/vc/run_audio_subset.sh [N]
# =====================================================================
set -uo pipefail
V=/dev/shm/vc
N="${1:-6}"

source "$HOME/miniforge3/etc/profile.d/conda.sh"; conda activate "$V/env"
export PYTHONPATH="$V/Speech" LD_LIBRARY_PATH="$V/env/lib" HF_HOME="$V/hf" TMPDIR="$V/tmp"
mkdir -p "$V/cache/mpl" "$V/cache/triton" "$V/cache/inductor" "$V/cache/numba" "$V/home"
export HOME="$V/home" XDG_CACHE_HOME="$V/cache" MPLCONFIGDIR="$V/cache/mpl"
export TRITON_CACHE_DIR="$V/cache/triton" TORCHINDUCTOR_CACHE_DIR="$V/cache/inductor"
export NUMBA_CACHE_DIR="$V/cache/numba" TOKENIZERS_PARALLELISM=false

# manifeste reduit : un echantillon de chaque condition, cas varies (cap,
# niveau, vitesse) pour que l'ecoute soit representative
python - "$N" <<'PY'
import json, sys
n = int(sys.argv[1])
m = json.load(open("/dev/shm/vc/stim/manifest.json"))
choix = [("sapi_radio", 0), ("sapi_radio", 8), ("sapi_radio", 18),
         ("sapi_propre", 0), ("humain_micro", 0), ("humain_radio", 0)][:n]
sel = [x for x in m if (x["condition"], x["cas"]) in choix]
json.dump(sel, open("/dev/shm/vc/stim/manifest_audio.json", "w"), ensure_ascii=False)
print("sous-echantillon :", [x["id"] for x in sel])
PY

python -u "$V/voicechat_infer.py" --checkpoint "$V/ckpt" \
  --manifest "$V/stim/manifest_audio.json" --output-dir "$V/out/audio" \
  --mode s2s --invite simple > "$V/out/audio.log" 2>&1
echo "SOUS_ECHANTILLON_AUDIO_TERMINE"
tail -12 "$V/out/audio.log"
