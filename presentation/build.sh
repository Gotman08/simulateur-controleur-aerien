#!/usr/bin/env bash
# Compilation de la soutenance : pdflatex x3 (latexmk n'est pas installe).
#   bash presentation/build.sh        (depuis la racine du depot, Git Bash)
#
# TROIS passes, pas deux : le script supprime les fichiers auxiliaires a la fin,
# donc chaque build repart de zero. Avec deux passes seulement,
# appendixnumberbeamer n'a pas le temps de fixer le nombre total de
# diapositives et le pied de page affiche "4/100" au lieu de "4/24".
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

# chemin Windows -> chemin WSL
WSLPATH="$(echo "$HERE" | sed 's|^/\([a-zA-Z]\)/|/mnt/\1/|; s|^\([A-Za-z]\):|/mnt/\L\1|; s|\\\\|/|g')"

for i in 1 2 3; do
  echo "[build] pdflatex passe $i/3..."
  wsl -e bash -c "cd '$WSLPATH' && pdflatex -interaction=nonstopmode soutenance.tex >/dev/null"
done
wsl -e bash -c "cd '$WSLPATH' && tail -2 soutenance.log"

echo "[build] controle qualite :"
echo "  erreurs      : $(grep -cE '^! ' "$HERE/soutenance.log" || true)"
echo "  debordements : $(grep -c 'Overfull' "$HERE/soutenance.log" || true)"

# garde-fou : le pied de page doit afficher un total plausible, pas le
# placeholder 100 de beamer.
TOTAL="$(grep -o 'inserttotalframenumber}{[0-9]*}' "$HERE/soutenance.aux" \
         | tail -1 | grep -o '[0-9]*' || true)"
if [ -z "$TOTAL" ] || [ "$TOTAL" -gt 60 ] 2>/dev/null; then
  echo "  numerotation : /!\\ ANORMALE (total = ${TOTAL:-inconnu}) - relancer"
else
  echo "  numerotation : x/$TOTAL"
fi

rm -f "$HERE"/soutenance.{aux,log,nav,out,snm,toc,vrb}
ls -la "$HERE/soutenance.pdf"
