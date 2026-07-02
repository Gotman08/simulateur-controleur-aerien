#!/usr/bin/env bash
# =====================================================================
#  Tunnel SSH PC local -> noeud de la facade OpenAI-compatible (ROMEO)
#  Forwarde localhost:8765/8766 vers <noeud> (via le login romeo).
#  Usage : ./tunnel.sh <SERVER_NODE>
#    (SERVER_NODE est imprime au demarrage de job_server.slurm)
#  PUIS configurez .env : ATC_STT_URL/ATC_LLM_URL=http://localhost:8765,
#                         ATC_TTS_URL=http://localhost:8766
# =====================================================================
NODE="${1:?usage: tunnel.sh <server_node>}"
echo "[tunnel] localhost:8765 (stt/llm) + localhost:8766 (tts)  ->  ${NODE}  (via romeo)"
exec ssh -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
     -N -L 8765:"${NODE}":8765 -L 8766:"${NODE}":8766 romeo
