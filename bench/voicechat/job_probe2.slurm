#!/bin/bash
# =====================================================================
#  Sondage #2 : stockage utilisable sur le NOEUD de calcul.
#  Les quotas GPFS (home/scratch/projet : 20 Go durs, deja satures) ne
#  peuvent pas accueillir le checkpoint de 44,4 Go : on cherche un disque
#  local au noeud (/tmp, /local, $SLURM_TMPDIR) ou /dev/shm (RAM 857 Go).
# =====================================================================
#SBATCH --job-name=vc-probe2
#SBATCH --account=r250127
#SBATCH --partition=instant
#SBATCH --constraint=armgpu
#SBATCH --gres=gpu:h100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=200G
#SBATCH --time=00:25:00
#SBATCH --output=/gpfs/scratch/nimarano/atc-voicechat/logs/probe2.%j.out

set -uo pipefail
echo "=== NOEUD $(hostname) ==="
echo "SLURM_TMPDIR=${SLURM_TMPDIR:-<vide>}  TMPDIR=${TMPDIR:-<vide>}  JOB_SCRATCH=${JOB_SCRATCH:-<vide>}"
echo "=== points de montage candidats ==="
df -h / /tmp /var/tmp /dev/shm /local /scratch /localscratch 2>&1 | grep -v "^df:"
echo "=== ecriture reelle (1 Go) ==="
for d in /tmp /var/tmp /dev/shm /local /localscratch /scratch; do
  [ -d "$d" ] || continue
  t="$d/vctest.$$"
  if dd if=/dev/zero of="$t" bs=1M count=1024 status=none 2>/tmp/err.$$; then
    echo "  $d : OK 1 Go  (libre: $(df -h "$d" | tail -1 | awk '{print $4}'))"
  else
    echo "  $d : ECHEC ($(cat /tmp/err.$$ 2>/dev/null | tail -1))"
  fi
  rm -f "$t"
done
echo "=== debit reseau HF (telechargement de 300 Mo, mesure) ==="
URL="https://huggingface.co/nvidia/NVIDIA-NemotronLabs-VoiceChat-11B/resolve/main/model.safetensors"
S=$(date +%s)
curl -sL -r 0-314572799 -o /dev/shm/vcpart.bin "$URL"
E=$(date +%s)
SZ=$(stat -c %s /dev/shm/vcpart.bin 2>/dev/null || echo 0)
echo "  telecharge: $SZ octets en $((E-S)) s  -> $(python3 -c "print('%.1f Mo/s'%($SZ/1e6/max(1,$E-$S)))" 2>/dev/null || echo '?')"
rm -f /dev/shm/vcpart.bin
echo "=== FIN ==="
