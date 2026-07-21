# Banc de benchmark scientifique

Campagne de mesures **réelles et reproductibles** de chaque étage du système
(STT, LLM, TTS, simulateur, boucle vocale complète), exécutée localement
(GPU grand public) et conçue pour compléter les mesures ROMEO historiques
(`validation/results_perf.json`, `rapport_S6-S7`).

Les chiffres publiés dans `docs/` et dans l'article (`docs/article/`) sont
générés par ces scripts — aucune valeur n'est saisie à la main.

## Principes de rigueur

- **Chemin de production, pas de reconstitution** : le benchmark LLM passe par
  `atc_llm.build_messages` (prompt système + KB OACI inlinée + indices NER),
  `ai_client.LlmClient` (HTTP OpenAI-compatible, température 0) et
  `atc_llm.postprocess_orders` (bornes + graphe secteur) — exactement le code
  exécuté par l'application. Idem STT (`atc_asr`) et TTS (`readback`,
  `voices`, dégradation VHF client).
- **Vérité terrain annotée** : 116 clairances (68 historiques + 48 étendues
  dont paraphrases hors grammaire, bruit STT, cas mixtes valide+invalide,
  14 négatifs de sécurité supplémentaires) ; 20 descriptions de scénarios
  (116 contraintes vérifiables) ; corpus audio ATC **réels** (ATCO2, UWB-ATCC).
- **Statistiques** : IC 95 % bootstrap (B=10 000, graine fixée) pour les
  moyennes, IC de Wilson pour les proportions, McNemar exact pour les
  comparaisons appariées de modèles, bootstrap apparié pour les deltas de WER.
- **Graines fixées partout** ; chaque script écrit un JSON auto-suffisant
  (protocole + résultats) dans `bench/results/`.

## Scripts

| Script | Venv | Mesure |
|---|---|---|
| `sim_bench.py` | app (`src/bluesky-env`) | CPA multi-graines (5×200 k), garantie de conflit de l'exercice (2 000 tirages), montée en charge BlueSky répétée (5×), latence parseur |
| `llm_bench.py` | bench | Exactitude TrafScript exacte de 4 LLM locaux + parseur à règles sur 116 clairances ; scénarios ; JSON strict ; latence ; tokens/s |
| `stt_bench.py` | bench | WER de whisper-small (vanilla vs **LoRA ATC du dépôt**) et faster-whisper tiny/base/small sur ATCO2 + UWB-ATCC, avec/sans passe-bande VHF d'inférence ; RTF |
| `tts_bench.py` | bench | RTF et intelligibilité aller-retour (TTS→juge STT fixe→WER) de Kokoro-82M (4 voix) et Windows SAPI, avant/après dégradation VHF |
| `e2e_bench.py` | bench | Boucle vocale complète (voix contrôleur SAPI + canal radio SNR 12 dB → STT → LLM → validation → TTS) : taux de réussite, attribution des échecs STT/LLM, latences par étage |
| `figures.py` | bench | Toutes les figures (`bench/figures/*.png`) |
| `run_all.py` | bench | Orchestrateur complet |
| `local_server.py` | bench | Façade OpenAI-compatible **100 % locale** (llama.cpp GPU / faster-whisper / Kokoro) — miroir de `src/server.py`, utilisable aussi comme fournisseur de l'application |

## Reproduire

```bat
:: 1. venv de benchmark (une fois) — Python 3.12
py -3.12 -m venv bench\bench-env
bench\bench-env\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu124
bench\bench-env\Scripts\python -m pip install faster-whisper transformers peft datasets jiwer soundfile matplotlib scipy pandas httpx requests fastapi uvicorn python-multipart kokoro-onnx
bench\bench-env\Scripts\python -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124

:: 2. modèles GGUF + Kokoro dans bench\models\ (voir URLs dans l'historique git
::    ou les en-têtes des scripts) : Llama-3.2-1B, Qwen2.5-1.5B/3B,
::    Mistral-7B-Instruct-v0.3 (Q4_K_M), kokoro-v1.0.onnx + voices-v1.0.bin

:: 3. campagne complète
bench\bench-env\Scripts\python bench\run_all.py
```

Matériel de référence : RTX 4070 Laptop 8 Go, i9-13900H, 32 Go RAM, Windows 11.

## Limites documentées

- L'intelligibilité TTS aller-retour partage le biais du juge STT entre tous
  les moteurs : métrique **relative**, pas absolue.
- Les énoncés contrôleur E2E sont synthétiques (SAPI + canal VHF simulé) :
  le WER STT y est optimiste par rapport à de la parole spontanée ; les corpus
  ATCO2/UWB (voix réelles) couvrent ce cas dans `stt_bench`.
- `_analyze` publie dCPA arrondi à 0,1 NM : l'erreur mesurée vs grille fine est
  bornée par cette quantification d'affichage (0,05 NM), la décision de
  prédiction étant elle exacte (0 désaccord / 10⁶ géométries).
- Les LLM locaux quantifiés Q4_K_M minorent légèrement la qualité des mêmes
  modèles en pleine précision (Mistral-7B ROMEO tourne en bf16).
