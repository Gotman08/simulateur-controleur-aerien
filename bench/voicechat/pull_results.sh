#!/usr/bin/env bash
# =====================================================================
#  Rapatriement des sorties de la campagne VoiceChat depuis le disque RAM
#  du noeud de calcul ROMEO.
#
#  Les quotas GPFS etant satures (ecriture refusee sur home/scratch/projet),
#  les resultats ne peuvent pas transiter par un fichier partage : on les
#  fait passer par la sortie standard de `srun --overlap`, encodee en base64
#  (sur pour Windows/Git Bash, aucun risque de traduction CRLF).
#
#  Usage : bash bench/voicechat/pull_results.sh <jobid> [etape] [destination]
#     ex : bash bench/voicechat/pull_results.sh 695845 complet bench/results/voicechat_raw
# =====================================================================
set -euo pipefail
JOBID="${1:?jobid requis}"
ETAPE="${2:-complet}"
DEST="${3:-bench/results/voicechat_raw}"

mkdir -p "$DEST"
TMP="$(mktemp -t vcpull.XXXXXX)"

echo "[pull] recuperation de /dev/shm/vc/out/$ETAPE depuis le job $JOBID ..."
ssh -o BatchMode=yes romeo \
    "srun --jobid=$JOBID --overlap bash -c 'cd /dev/shm/vc/out && tar czf - $ETAPE | base64 -w0'" \
    > "$TMP"

echo "[pull] $(wc -c < "$TMP") octets base64 recus ; decodage ..."
base64 -d "$TMP" | tar xz -C "$DEST" --strip-components=1
rm -f "$TMP"

echo "[pull] contenu de $DEST :"
ls -la "$DEST" | head
echo "[pull] $(ls "$DEST/wav" 2>/dev/null | wc -l) fichiers audio"
