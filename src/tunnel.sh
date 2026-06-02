#!/usr/bin/env bash
# =====================================================================
#  Semaines 6&8 (V3) : tunnel SSH PC local -> noeud serveur ROMEO
#  Forwarde localhost:PORT vers <noeud>:PORT (via le login romeo).
#  Usage : ./tunnel.sh <SERVER_NODE> [PORT]
#    (SERVER_NODE est imprime au demarrage de job_server.slurm)
#  ex.  ./tunnel.sh romeo-a044 8765
# =====================================================================
NODE="${1:?usage: tunnel.sh <server_node>}"
echo "[tunnel] localhost:8765 (asr/llm) + localhost:8766 (tts)  ->  ${NODE}  (via romeo)"
exec ssh -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
     -N -L 8765:"${NODE}":8765 -L 8766:"${NODE}":8766 romeo
