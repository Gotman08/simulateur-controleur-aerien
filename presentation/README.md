# Soutenance de stage : « Parler aux avions »

Presentation Beamer (theme metropolis, 16:9) pour la soutenance de fin de stage.
Chaque chiffre affiche provient d'un fichier de resultats versionne dans
`bench/results/` : aucune valeur n'est saisie a la main.

## Compiler

```bash
bash presentation/build.sh
```

Deux passes de `pdflatex` via WSL (`latexmk` n'est pas installe sur ce poste).
Le script affiche a la fin le nombre d'erreurs et de debordements, puis nettoie
les fichiers auxiliaires.

## Structure du deck

| Pages | Contenu |
|---|---|
| 1-4 | Le probleme, l'objectif, la boucle en cinq etapes, **le pivot** : le modele propose, le code verifie |
| 5-7 | Ce qu'il a fallu construire : l'application d'entrainement, le banc de mesure |
| 8-11 | **Entendre** : le taux d'erreur mots explique, l'adaptation LoRA, les resultats sur radio reelle |
| 12-17 | **Comprendre** : l'ancrage documentaire, la comparaison regles / modele, le prix du langage naturel |
| 18-22 | **Les epreuves** : l'enquete du gabarit Mistral, les gardes en action, la garde contournable, la preuve geometrique |
| 23-26 | **Repondre et boucler** : le canal VHF, la boucle complete, la panne de ROMEO |
| 27-30 | **Bilan** : perimetre assume, recapitulatif, remerciements |
| 31-42 | Diapositives de reserve pour les questions (dont : cout de la
quantification 4 bits, pourquoi pas le petit modele, pourquoi pas un modele
vocal de bout en bout) |

Duree visee : environ 20 minutes (24 diapositives numerotees ; les diapositives
de reserve ne comptent pas dans le temps de parole).

## Notes de l'orateur

Chaque slide porte un `\note{...}` avec le message a faire passer. Pour les
afficher sur un second ecran, ajouter dans le preambule :

```latex
\setbeameroption{show notes on second screen=right}
```

puis recompiler (le PDF fait alors le double de largeur : ecran de projection a
gauche, notes a droite).

## Figures

Les graphiques de `figures/` sont produits par `gen_figures_slides.py`, qui
reutilise les fonctions de `bench/figures.py` avec une typographie d'ecran.
A relancer apres toute nouvelle campagne de mesure :

```bash
bench/bench-env/Scripts/python.exe presentation/gen_figures_slides.py
```

Les captures `demo_radar_*.png` sont des images fixes extraites des GIF de
`docs/assets/` (un PDF ne peut pas animer un GIF).
