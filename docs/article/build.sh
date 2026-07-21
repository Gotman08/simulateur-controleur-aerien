#!/usr/bin/env bash
# Compilation de l'article : figures + tableaux generes + pdflatex x2 (WSL).
#   bash docs/article/build.sh        (depuis la racine du depot, Git Bash)
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"

echo "[build] figures..."
mkdir -p "$HERE/figures"
cp -f "$ROOT/bench/figures/"*.png "$HERE/figures/" 2>/dev/null || true
cp -f "$ROOT/docs/assets/validation/fig_bluesky_scatter.png" "$HERE/figures/" 2>/dev/null || true

echo "[build] tableaux + macros..."
python "$HERE/gen_tables.py"

echo "[build] pdflatex (WSL)..."
# Git Bash donne /c/... ; cmd donne C:\... ; WSL veut /mnt/c/...
WSLPATH="$(echo "$HERE" | sed 's|^/\([a-zA-Z]\)/|/mnt/\1/|; s|^\([A-Za-z]\):|/mnt/\L\1|; s|\\\\|/|g')"
wsl -e bash -c "cd '$WSLPATH' && pdflatex -interaction=nonstopmode article.tex >/dev/null && pdflatex -interaction=nonstopmode article.tex | tail -3"
ls -la "$HERE/article.pdf"
