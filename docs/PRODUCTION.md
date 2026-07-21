# Rapport de préparation à la production

État de préparation du simulateur pour une remise commerciale : périmètre,
posture de sûreté, revue de code (juillet 2026), correctifs appliqués, guide
de déploiement et limites assumées. Complète `AUDIT.md` (audit de traçabilité
des résultats) et `VALIDATION.md` (preuves de justesse).

## 1. Périmètre du produit

Application web locale mono-poste d'entraînement au contrôle aérien :
radar temps réel (BlueSky), poste instructeur (génération de trafic en
langage naturel, météo, zones), poste élève (clairances tapées **et
parlées**, collationnement vocal), exercices notés avec débrief. Les trois
briques IA (STT/LLM/TTS) sont des services externes au contrat
OpenAI-compatible, configurés par `.env` — trois points de déploiement
validés : façade cluster (ROMEO), **façade 100 % locale** (`bench/local_server.py`,
llama.cpp + faster-whisper + Kokoro sur GPU grand public), API cloud.

## 2. Posture de sûreté (architecture en couches)

1. **Validation déterministe de toute sortie LLM** (`03_bluesky_connector`) :
   coercition stricte de types, bornes physiques (HDG 0-360°, ALT 0-45 000 ft,
   SPD 0-350 kt), 4 actions autorisées, waypoints validés contre le graphe
   secteur. Mesuré : mêmes petits modèles hallucinant des ordres, **0 ordre
   hors bornes exécuté** sur les 116 clairances du banc (`bench/llm_bench.py`).
2. **Gardes applicatives** : indicatif inconnu au radar = silence radio ;
   incohérence sémantique climb/descend rejetée avec message.
3. **Aucun repli silencieux** : panne fournisseur → `ProviderError` → HTTP 502
   → événement `error` visible au journal de bord. Témoin de vie du thread de
   simulation exposé dans chaque snapshot (`sim_alive`).
4. **Entrées bornées** : payloads numériques finis (NaN/Inf → 400), durée
   d'exercice 1-180 min, uploads audio ≤ 20 Mo (413 au-delà), scénarios JSON
   malformés → 400.

## 3. Revue de code multi-agents (2026-07)

Protocole : 5 relecteurs spécialisés (correction backend, concurrence,
robustesse API, frontend, contrat IA) + **vérification adversariale** de
chaque constat (l'agent vérificateur doit d'abord tenter de le réfuter sur le
code réel). Résultat : 32 constats confirmés (3 critiques), 10 réfutés,
1 choix assumé documenté. **Tous les constats confirmés sont corrigés**, avec
tests de non-régression (la suite passe de 186 à 209 tests).

Correctifs critiques :

| Défaut | Impact avant correctif | Correctif |
|---|---|---|
| Durée de perte de séparation gonflée à la ré-entrée d'une même paire (`atc_exercise._sample`) | 300 s « fantômes » pouvaient anéantir S_sep (50 % de la note) ; épisodes non recomptés | Épisodes cumulés (`dur_s`, `episodes`), score = somme des épisodes réels ; idem zones |
| Garde sémantique climb/descend contournable (`atc_app._check_alt_coherence`) | Un ordre ALT **rejeté et annoncé comme bloqué** pouvait quand même être exécuté (comparaison de chaîne sur valeur brute LLM `32000.0` ≠ `32000`) | Filtrage positionnel des listes parallèles ordres/lignes |
| Valeur d'ordre au type brut LLM (`atc_llm.postprocess_orders`) | Incohérences de type en aval (readback, gardes) | Valeur alignée sur l'entier coercé du TrafScript ; copie défensive (plus de mutation de l'appelant) |

Sélection des correctifs de robustesse : réponses fournisseur dégénérées
(STT JSON non-objet, LLM `content:null`, TTS corps vide ou JSON) → erreurs
typées 502 ; courses au démarrage d'exercice (verrou + jointure du thread
précédent + 409) ; radar préservé si le LLM tombe pendant la construction
d'exercice ; exceptions du thread sim journalisées (plus de `except: pass`) ;
garde anti-blocage de `advance()` ; ré-essai automatique du chargement de la
carte côté front ; anti-repliement avant décimation micro ; fuite d'URL blob
TTS colmatée ; push-to-talk insensible à Ctrl/Cmd+V ; throttle d'état avec
bord de fuite ; validation des saisies vent ; auto-scroll du journal
respectueux de la lecture.

Améliorations issues du banc de mesure : `parse_orders` répare les nombres
JSON à zéro de tête (`"value": 090`, produit par de vrais modèles — cas
mesuré) ; compagnies d'exercice alignées avec la téléphonie du readback et la
normalisation d'indicatifs ; collationnement limité au premier indicatif
(une transmission = un aéronef) ; `run_all.py` de validation muni de
**portes de non-régression** sur les métriques elles-mêmes.

## 4. Vérification continue

- `pytest` : 209 tests (modules purs, sans réseau ni GPU) — CI GitHub.
- `ruff` : zéro erreur (config unifiée `pyproject.toml`).
- `tsc --noEmit` : zéro erreur ; `npm run build` reproductible.
- `validation/run_all.py` : campagne de justesse **avec portes** (CPA, F1,
  parseur, générateur) ; reproductibilité vérifiée champ à champ.
- `bench/run_all.py` : campagne de mesure complète (simulateur, STT, LLM,
  TTS, E2E) → JSON + figures versionnés.

## 5. Guide de déploiement

```bash
# 1. Python 3.12 impératif (wheels BlueSky) :
py -3.12 -m venv src/bluesky-env
src/bluesky-env/Scripts/pip install -r requirements-local.txt

# 2. Fournisseurs IA : copier .env.example -> .env et choisir UNE config :
#    A. façade ROMEO (tunnel SSH, start_romeo.ps1)
#    B. cloud OpenAI-compatible (clés API)
#    C. façade 100% locale (GPU >= 8 Go) :
#       bench/bench-env/Scripts/python bench/local_server.py --role all \
#         --llm-gguf bench/models/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf --warm
#       puis ATC_{STT,LLM,TTS}_URL=http://127.0.0.1:8901 dans .env

# 3. Lancer :
cd src && bluesky-env/Scripts/python atc_app.py    # http://127.0.0.1:8000
```

## 6. Résilience au fournisseur (fait vécu)

Pendant la campagne de mesure de juillet 2026, le supercalculateur ROMEO
était **entièrement indisponible** (maintenance de sécurité : logins et
nœuds ARM GPU down dans l'attente des correctifs RedHat). L'application est
restée pleinement opérationnelle en basculant la configuration `.env` vers la
façade 100 % locale (RTX 4070) — sans toucher au code. C'est précisément le
scénario de continuité que le contrat OpenAI-compatible garantit : la panne
d'un fournisseur (cluster, cloud) est un risque opérationnel réel, couvert
par bascule de configuration.

## 7. Limites assumées (documentées)

- **Mono-poste local** : pas d'authentification ni de TLS — l'app écoute sur
  127.0.0.1 par défaut. Une exposition réseau exigerait un reverse-proxy
  authentifiant (hors périmètre actuel).
- `t_cross_s` des conflits construits est calculé sur la vitesse CAS donnée à
  BlueSky (la TAS réelle avance le croisement) : la **garantie de conflit**
  (dCPA ≈ 0) est démontrée insensible à ce facteur (`bench/sim_bench.py`,
  2 000 tirages, 100 %), l'horodatage annoncé est nominal.
- Le scoring d'exercice inclut tout trafic présent (y compris ajouté en cours
  d'exercice par l'instructeur) : comportement assumé — le secteur entier est
  sous responsabilité de l'élève.
- Façade `server.py` (cluster) : inférence synchrone dans l'event loop —
  dimensionnée pour un poste unique, pas pour la concurrence (documenté).
