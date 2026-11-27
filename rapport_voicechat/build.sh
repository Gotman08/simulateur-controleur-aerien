#!/usr/bin/env bash
# Compilation de la note technique VoiceChat : figures + pdflatex x2 (WSL).
#   bash rapport_voicechat/build.sh        (depuis la racine du depot, Git Bash)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

echo "[build] figures (depuis bench/results/voicechat_*.json)..."
"$ROOT/bench/bench-env/Scripts/python.exe" "$HERE/gen_figures.py"

echo "[build] pdflatex (WSL, deux passes pour la table des matieres)..."
# Git Bash donne /c/... ; WSL veut /mnt/c/...
WSLPATH="$(echo "$HERE" | sed 's|^/\([a-zA-Z]\)/|/mnt/\1/|; s|^\([A-Za-z]\):|/mnt/\L\1|; s|\\\\|/|g')"
wsl -e bash -c "cd '$WSLPATH' && pdflatex -interaction=nonstopmode rapport_voicechat.tex >/dev/null && pdflatex -interaction=nonstopmode rapport_voicechat.tex | tail -3"
ls -la "$HERE/rapport_voicechat.pdf"
