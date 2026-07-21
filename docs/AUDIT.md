# Audit de fonctionnement - Simulateur d'entraînement au contrôle aérien

> **⚠️ Note (2026-07-02) - refactoring majeur postérieur à cet audit.** L'architecture décrite ici
> (deux modes LOCAL/ROMEO avec bascule silencieuse) a été remplacée par une architecture
> **API-first à mode unique** : STT/LLM/TTS sont désormais trois services au contrat
> OpenAI-compatible configurés par `.env` (`src/ai_client.py`), `src/server.py` est devenu une
> façade OpenAI-compatible auto-hébergée, le parseur local (`src/atc_ai.py`) est sorti du runtime
> (conservé comme bibliothèque de référence pour tests/validation), chaque avion a une voix TTS
> stable (hachage d'indicatif) et tout readback est vocalisé par l'API TTS. Les sections
> ci-dessous restent valables comme **état des lieux au 2026-07-01** ; les points marqués
> « corrigé » l'ont été avant le refactoring.

> **Date :** 2026-07-01 · **Branche :** `main` · **Portée :** l'ensemble du dépôt (back Python, chaîne IA, runtime BlueSky, frontend React, campagne de validation, CI/infra).
>
> **Objet de l'audit :** répondre à trois questions - (1) *qu'est-ce que le projet fait réellement ?* (2) *est-ce que ça fonctionne vraiment ?* (3) *qu'a-t-on oublié, en particulier côté tests ?*
>
> **Méthode :** vérité terrain mesurée par exécution (pytest, ruff, build, imports, sondes runtime) **+** audit multi-agents (14 agents : 12 sous-systèmes, 1 analyse transversale de couverture, 1 critique anti-oubli). Chaque verdict ci-dessous est adossé à une preuve d'exécution ou à une lecture de code référencée `fichier:ligne`. Les briques nécessitant GPU/cluster/réseau HuggingFace sont marquées **non vérifiables ici** (et non « en échec »).

---

## 1. Verdict global

**Le projet fonctionne réellement dans son mode principal (LOCAL, sans GPU) et il est honnête** : les chiffres annoncés dans la campagne de validation sont reproductibles, l'app démarre et exécute le pipeline `texte → interprétation → BlueSky → collationnement` de bout en bout sur un poste ordinaire. La qualité des tests existants est bonne (assertions réelles, cas limites).

**Mais** l'audit a mis au jour **des bugs réels (vérifiés par exécution)** et surtout **un déséquilibre de couverture** : les modules purs sont bien testés, tandis que **le cœur produit** (barème de notation d'exercice, API et garde-fous du serveur, frontend) et **toute la chaîne IA lourde** (ASR Whisper, LLM+RAG, TTS) n'ont **aucun test**. La CI n'exerce que les modules purs, donc un bug d'intégration passerait inaperçu.

| Axe | État |
|---|---|
| Fonctionne en mode LOCAL (radar + interprétation + sim + readback) | ✅ Vérifié de bout en bout |
| Tests unitaires (modules purs) | ✅ 110 tests, verts, de bonne qualité |
| Lint / build | ✅ ruff clean · frontend build OK |
| Campagne de validation (CPA, parseur, générateur) | ✅ Reproductible à l'identique (01/03/04) |
| Chaîne IA lourde (Whisper, Mistral+RAG, XTTS) | ⚠️ Câblée, **non exécutable hors cluster ROMEO/GPU** |
| Couverture de test du cœur applicatif | ⚠️ Encore partielle (API, frontend, TTS, ASR non testés), mais **notation + audio VHF désormais couverts** |
| Bugs vérifiés | ✅ **Tous corrigés** : repli CD (B2), except silencieux (B4), chemin adaptateur (B5), repli UI mort (B6), détection processor (B3). B1 reclassé (comportement documenté). |
| Reproductibilité long terme (déps épinglées) | ⚠️ **Non épinglées** (pas de lock Python) - `.python-version` ajouté |

---

## 2. Vérité terrain mesurée (reproductible)

Toutes ces commandes ont été exécutées pendant l'audit ; les résultats sont factuels.

```bash
# Tests unitaires (env dédié, Python 3.12.10 - identique à la CI)
./src/bluesky-env/Scripts/python.exe -m pytest        # → 110 passed in ~0.9s

# Lint
ruff check src tests validation tools                 # → All checks passed!

# Build frontend
cd frontend && npm run build                          # → built OK (tsc -b + vite)

# Simulation BlueSky réelle (CPU, sans GPU)
./src/bluesky-env/Scripts/python.exe src/bluesky_runtime.py
#   → A320 créé, HDG 90→270, ALT 10000→5559 ft sur 180 s simulés, exit 0

# Validation rejouée (seed 42)
./src/bluesky-env/Scripts/python.exe validation/01_cpa_analytique.py   # → err max 5.5e-4 NM, 446/446 accords
./src/bluesky-env/Scripts/python.exe validation/03_parseur_eval.py     # → 68 phrases, 100 %
./src/bluesky-env/Scripts/python.exe validation/04_generateur_eval.py  # → 116/116 contraintes, 100 %
```

**Précisions importantes :**
- L'environnement qui exécute les tests (`src/bluesky-env`) est en **Python 3.12.10**, **identique à la CI** - l'écart « 3.14 » ne concerne que le Python nu du système, pas l'env de test. Il manque toutefois un `.python-version` pour verrouiller ce choix.
- `src/bluesky-env` contient : `bluesky-simulator 1.1.1`, `numpy 2.4.6`, `scipy`, `soundfile`, `fastapi`, `requests`. Il **ne contient pas** `torch`, `transformers`, `peft`, `sentence_transformers`, `coqui-tts`, `jiwer` → toute la chaîne IA lourde n'est pas exécutable dans cet environnement (c'est voulu : elle tourne sur le cluster ROMEO/GPU).

---

## 3. Points confirmés et correctifs appliqués

> Mise à jour 2026-07-01 : **tous les défauts ci-dessous ont été corrigés** (ou reclassés après relecture du code). La suite `pytest` reste verte (désormais **148 tests**, +38 de non-régression), `ruff` clean, build OK.

| # | Sévérité | Fichier | Défaut | Correctif appliqué |
|---|---|---|---|---|
| B2 | 🔴 Haute | `src/atc_sim.py` | Le repli de sécurité testait `type(cd).__name__ == "ConflictDetection"`, mais l'objet BlueSky est un `Proxy` → condition **jamais vraie**, repli géométrique `_analyze()` = code mort. | ✅ **Corrigé** : état CD suivi par un flag `self._cd_on` (positionné dans `_enable_cd`, avec log si échec) ; `_analyze_cd` devient une méthode d'instance qui renvoie `None` - donc bascule sur la géométrie - quand la CD n'est pas active. |
| B4 | 🟠 Moyenne | `src/atc_exercise.py` | `try/except: pass` nus dans `_run` et `_save` → erreurs d'échantillonnage / d'écriture du rapport **avalées silencieusement**. | ✅ **Corrigé** : logger `atc_exercise` + `_log.exception(...)` dans les deux blocs (l'erreur est tracée au lieu d'être masquée). |
| B5 | 🟠 Moyenne | `src/server.py` | Chemin d'adaptateur figé sur `WORK/outputs/...` (scratch GPFS) → l'adaptateur commité n'était jamais utilisé hors cluster. | ✅ **Corrigé** : défaut = adaptateur cluster **s'il existe**, sinon `model/whisper-lora-adapter/` commité ; surchargeable via `ATC_ADAPTER`. |
| B6 | 🟠 Moyenne | `src/atc_app.py` | `WEB_LEGACY = src/web` **inexistant** → repli mort ; si `frontend/dist` manque, aucune UI servie sans alerte. | ✅ **Corrigé** : repli `src/web` supprimé ; **avertissement loggé** si `frontend/dist` est absent (l'API reste servie). |
| B3 | 🟡 Faible | `src/atc_asr.py` | Détection du *processor* sur `preprocessor_config.json` seul → le dossier commité (`processor_config.json`) tombait sur le *processor* de base. | ✅ **Corrigé** : les deux noms de fichier sont acceptés. (Impact réel cosmétique : les poids LoRA étaient de toute façon appliqués, `atc_asr.py:54-57`.) |
| B1 | ⚪ **Non-bug (revu)** | `src/atc_exercise.py` | *Signalé initialement comme « pénalité de conflit permanente ».* Un conflit prédit qui devient une perte de séparation reste compté « non résolu ». | ⚪ **Aucun correctif - comportement documenté.** Le barème (`docstring:11,21` + docs/VALIDATION.md par. 6) définit S_conf comme *« résolus **avant** la perte de séparation »* : un conflit devenu LoS n'est légitimement pas « résolu à temps » (S_sep et S_conf mesurent deux compétences distinctes, pas une double peine). Un **test documente** désormais ce comportement voulu. À rediscuter seulement si la pédagogie est jugée trop sévère. |

> Correctifs tous petits et localisés. Deux tests de non-régression ont été ajoutés (`tests/test_atc_exercise.py`, `tests/test_atc_audio.py`) pour couvrir le barème de notation et le prétraitement VHF, jusque-là sans aucun test.

---

## 4. Matrice de couverture des tests

**148 tests** répartis sur 8 fichiers (110 initiaux + 38 ajoutés pour la notation et l'audio VHF). Les cases mises à jour après correctifs sont marquées **(nouveau)**.

| Module `src/` | Testé ? | Testable en CI (sans GPU/réseau) ? |
|---|---|---|
| `atc_callsign` | ✅ oui (14) | oui |
| `readback` | ✅ oui (18) | oui |
| `03_bluesky_connector` | ✅ oui (18) | oui |
| `graph_secteur` | ✅ oui (10) | oui |
| `atc_sim` (géométrie + `_analyze`) | ✅ oui (18) | oui (helpers purs) |
| `atc_ai` - repli **local** | ✅ oui (32) | oui |
| `atc_ai` - **AIClient / ROMEO** | ❌ non | **oui** (mock `requests`) |
| `atc_exercise` (grade, conflit, **notation**) | ✅ **oui (32) - nouveau** | oui |
| `atc_audio` (bande passante VHF) | ✅ **oui (6) - nouveau** | oui |
| `atc_app` (API FastAPI, garde-fous) | ❌ non | **oui** (`fastapi.TestClient` présent) |
| `04_ner_extraction` | ❌ non | **oui** (regex pur) |
| `kb_oaci` | ❌ non | **oui** (pur) |
| `atc_llm` (`parse_orders`, interpret) | ❌ non | partiel (`parse_orders` pur ; reste = torch) |
| `atc_asr` | ❌ non | ❔ non (torch/transformers absents) |
| `tts_atc` | ❌ non | ❔ non (TTS/torch absents) |
| `server` (FastAPI ROMEO) | ❌ non | ❔ non (dépend ASR/LLM/TTS) |
| `atc_data` (corpus HF) | ❌ non | ❔ non (réseau HF) |
| **Frontend React** | ❌ non | ❔ aucun outil de test (ni vitest/jest ni ESLint) |

**Lecture :** la colonne de droite distingue deux classes d'oublis - **(a) testables mais non testés** (`atc_exercise`, `atc_app`, `atc_ai/AIClient`, `04_ner_extraction`, `kb_oaci`, `atc_audio`) : ce sont les **vrais oublis**, à combler ; **(b) non testables ici** (chaîne ROMEO) : dépendance GPU/cluster assumée, à couvrir par des tests mockés ou une CI GPU dédiée.

> ⚠️ **Frein de conception à la testabilité :** `import atc_app` prend ≈ 10 s car `AIClient()` et `SimManager()` sont instanciés **au niveau module** (`atc_app.py:44-45`), déclenchant des health-checks réseau bloquants. Rendre ces instances *lazy* est un prérequis pratique pour tester l'API proprement.

---

## 5. Détail par sous-système

### 5.1 Prétraitement audio (VHF) - `src/atc_audio.py`, `src/01_audio_preprocessing.py`

**Verdict : ✅ fonctionne (vérifié en local, module pur numpy/scipy).**

`preprocess_waveform` s'importe et tourne. Testé sur un signal factice 16 kHz (tons 60 / 1000 / 6000 Hz) :
- `FS=16000`, `LOWCUT/HIGHCUT=300/3400`, `ORDER=6`, `_SOS.shape=(6,6)`.
- **eval** : énergie hors-bande **66.7 % → 0.0 % (≈ −47.7 dB)** → le filtre passe-bande Butterworth ordre 6 fait bien son travail.
- Robustesse : entrée liste Python et signal muet `[0.0]*100` → sortie finie (epsilon `1e-12` ligne 32).

**Cohérence FS = 16 kHz : ✅ vérifiée partout** - `atc_asr.py:73-76`, `06_prepare_dataset.py:72-74` (avec `assert sr == FS`), `08_finetune_whisper_lora.py:87-88`, `tts_atc.py:48`, `server.py:57-61` (resample avant ASR). Le module est **réellement utilisé partout**, pas seulement câblé.

**Lacunes :**
- **Aucun test** alors que le module est 100 % testable en CI (numpy/scipy). Un test d'atténuation hors-bande + reproductibilité serait trivial.
- **Docstring inexacte** (`atc_audio.py:9-10`) : « module non importable car commence par `01_` » est faux (`importlib` réussit) ; la vraie raison de dupliquer est d'éviter matplotlib.
- **`augment` S1 ≠ S4** : `01_audio_preprocessing.py:39` n'a pas l'epsilon de `atc_audio.py:32` (division 0/0 possible sur signal muet côté S1). Sans impact app.
- Augmentation non déterministe (rng non seedé par défaut) ; SNR effectif post-filtrage non mesuré.

### 5.2 ASR Whisper + adaptateur LoRA - `src/atc_asr.py`, `06..10`, `model/whisper-lora-adapter/`

**Verdict : ⚠️ câblé et plausible, mais l'inférence réelle n'est pas vérifiable ici et les WER annoncés ne sont adossés à aucun artefact commité.**

**Vérifié (OK) :** l'adaptateur est **présent et structurellement valide** - `adapter_model.safetensors` (14 MB), 144 tenseurs (72 `lora_A` + 72 `lora_B`), shapes `[32,768]`/`[768,32]` → r=32 sur d_model=768 (whisper-small), modules `q_proj`/`v_proj`, cohérent avec `adapter_config.json`. `get_normalizer()` fonctionne (repli regex).

**Ce qui bloque :** `torch`/`transformers`/`peft`/`jiwer`/`datasets` **absents** de `src/bluesky-env` → brique non exécutable de bout en bout hors cluster ; `08_finetune:126` force `assert torch.cuda.is_available()`.

**Lacunes :**
- ❌ **WER 74.3 → 29.2 (ATCO2) et val 6.68 non traçables** : ces valeurs n'existent que dans les README ; **aucun** `train_summary.json` / `evaluation_s4.json` / CSV n'est commité, alors que `07`/`08`/`09` sont censés les produire. Non reproductibles sans relancer un job GPU.
- ❌ **Aucun test** ASR (même `compute_wer`, pur, n'est pas testé).
- 🟡 **Bug B3** (`atc_asr.py:50`) : `preprocessor_config.json` cherché, `processor_config.json` fourni → le *processor* retombe sur la base (**cosmétique** : les poids LoRA sont bien appliqués, `atc_asr.py:54-57`). → ✅ **corrigé** (les deux noms acceptés).
- ⚠️ **Bug B5** (`server.py:31`) : chemin adaptateur = scratch cluster, jamais le dossier commité (contexte cluster uniquement). → ✅ **corrigé** (défaut sur l'adaptateur commité + override `ATC_ADAPTER`).
- ⚠️ Poids base whisper-small (~1 Go) téléchargés au 1er lancement (réseau HF non contourné).

### 5.3 NER + LLM + RAG - `src/atc_ai.py` (repli local), `src/atc_llm.py` + `src/kb_oaci.py` (ROMEO)

**Verdict : ⚠️ partiel - deux moitiés bien distinctes.**

**✅ Repli LOCAL (vérifié, hors-ligne) :** `atc_ai.local_interpret` (parseur regex **FR/EN** → ordres JSON → TrafScript) : **32 tests passent**. **Garde de sécurité confirmée en direct** : HDG 400 / ALT 99000 / SPD 500 → entièrement rejetés (motif dans `rejected`), borne issue de `03_bluesky_connector.LIMITS`, **partagée par les deux chemins**. `kb_oaci.build_documents()` : pur, 9 fiches OACI hors-ligne.

**⚠️ Chemin ROMEO (LLM Mistral + RAG) - câblé, non vérifiable ici :**
- `torch`/`transformers`/`sentence_transformers` absents ; `atc_llm.py:102` = `device_map="cuda"` en dur ; Mistral-7B via réseau HF.
- **KB OACI ni présente ni buildée** : `KB_DIR` pointe vers `/gpfs/scratch/...` (cluster) ; `Retriever()` lève `FileNotFoundError` en local ; aucun `embeddings.npy`/`docs.json` dans le dépôt.

**Lacunes :** garde sémantique côté LLM et jeu adversarial U5 (`14_evaluate_rag.py`) non couverts par pytest ; `atc_llm.parse_orders`/`ner_extract`/`build_messages` purs mais **non testés** (ROI élevé, isolable) ; heuristique `is_fl` si `v<=450` (`atc_ai.py:114`) ambiguë pour altitudes < 450 ft.

### 5.4 Callsign + Readback (collationnement) - `src/atc_callsign.py`, `src/readback.py`

**Verdict : ✅ fonctionnent et sont réellement intégrés** (32 tests), **mais** couverture limitée au chemin nominal **anglophone en sortie**.

Intégration réelle confirmée : `normalize_callsign` (`atc_ai.py:159`, `atc_llm.py:180/242`), `readback_text` (`atc_app.py:167`, `voice_exchange.py:65` → TTS `atc_app.py:308-310`).

**Lacunes (reproduites en exécution, non testées) :**
- **Readback FR absent** : `normalize_callsign('air france deux')` = `AFRDEUX` ; variantes OACI `tree`/`fife`/`hundred` non gérées côté sortie readback (l'entrée, elle, gère le FR - cf. 5.3).
- **Suppression silencieuse** de tokens non `[a-z0-9]` : `'AFR 12.3'` → `AFR` (nombre perdu), `'air france, one two'` → `AIR12`.
- **Valeurs hors bornes** : `value=-100` → `flight level - zero one` (le `-` prononcé) ; `zfill(3)` inefficace > FL999.
- **Pas de cas `maintain`** (altitude ordonnée == courante → reste `climb`).
- **Tables dupliquées désynchronisées** `AIRLINE` (callsign) vs `CODE2TEL` (readback) : `CSA`/`EZY` normalisés à l'entrée mais absents de `CODE2TEL` → épelés lettre par lettre au readback.
- `spell()` incohérent sur waypoint alphanumérique (`LMG26` → `... golf 2 6`, chiffres bruts).

### 5.5 Graphe de secteur - `src/graph_secteur.py`, `src/secteur_graphe.json`, `02`, `16`

**Verdict : ✅ fonctionne (vérifié).** `ENTRY_W → EXIT_E = 101.0 NM` reproductible (x3 identiques) ; 10 tests passent. Module pur (stdlib), réellement intégré (`atc_ai.py:48`, `atc_llm.py:46`, `atc_sim.py:290`).

**Nuance :** le « 101 NM » provient des distances **arrondies à 1 décimale** figées dans le JSON (`02_airspace_graph.py:46`) ; la vraie longueur euclidienne est **100.99 NM**. Reproductible car figé, mais Dijkstra optimise sur des poids arrondis.

**Lacunes :**
- Générateur `02_airspace_graph.py` **non ré-exécutable** dans `bluesky-env` (`networkx`/`matplotlib` absents) → aucun test ne lie script → JSON.
- **Aucune validation défensive du JSON** : segment vers un `id` inconnu crée un **nœud fantôme** (`adj.setdefault`) ; `dist_nm` manquant → arête de poids 0 ; `topology_text()` lèverait `KeyError` sur JSON malformé.
- Secteur **fictif** codé en dur (7 fixes cartésiens, pas de vraies balises OACI/lat-lon) ; ancrage Reims reconstitué a posteriori dans `atc_sim`.

### 5.6 Runtime BlueSky (simulation temps réel) - `src/atc_sim.py`, `src/bluesky_runtime.py`, `03`

**Verdict : ⚠️ partiel - la sim s'exécute VRAIMENT en local/CPU, mais un repli de sécurité est cassé (B2) et la boucle temps réel n'est pas testée.**

**Prouvé ici :** `bluesky-simulator 1.1.1` installé, `import bluesky` OK sans GPU/réseau, import **paresseux** (confirmé par `test_import_atc_sim_ne_charge_pas_bluesky`). **Sim réelle exécutée** (A320, HDG 90→270, ALT 10000→5559 ft/180 s). **Moteur CD BlueSky opérationnel** (2 avions face-à-face → conflit détecté). Intégré à l'app (`atc_app.py:44`). 36 tests (géométrie + connecteur) verts.

**Lacunes :**
- **Bug B2** (repli CD inatteignable, `atc_sim.py:404`). → ✅ **corrigé** (flag `self._cd_on`).
- **Aucun test automatisé** de la boucle temps réel (`_run`, `_drain_queue`, `_apply`, `_update_snapshot`, `_enrich`) ni de `_analyze_cd` : seule preuve = self-test manuel de `bluesky_runtime.py`, non intégré à pytest.
- **CI aveugle sur la sim** (pas de BlueSky en CI).
- **`except: pass` silencieux** partout (`:188`, `:199`, `:283`, `:297`, `:366`, `:411`) → erreurs BlueSky avalées sans trace.
- Fragilités runtime observées : `RTree could not be loaded`, `Failed to load BADA` (repli OpenAP) ; contournements `checkInside`/`kwikdist` « qui plantent avec numpy 2.x ».
- Météo/turbulence/zones : API câblées, **effet réel non exécuté/vérifié**.

### 5.7 Moteur d'exercice / notation - `src/atc_exercise.py`

**Verdict : ✅ maths justes, désormais couvert par des tests ; B4 corrigé, B1 reclassé (comportement documenté).**

**Vérifié en exécutant le code :** `grade()` (seuils A≥90…E) OK ; `make_conflict_pair()` sur 2000 tirages → distance au CPA pire = **0.10 NM** (conflit géométrique garanti) ; `_score_unlocked()` reproduit **exactement** le barème documenté (`S_sep = max(0, 50 − 25·N_LoS − 0.5·T_LoS)`, `S_conf = 20·résolus/prédits`, `S_zone`, `S_radio`). Câblé (`atc_app.py:55,165-166`).

**État après correctifs :**
- ✅ **Tests ajoutés** (`tests/test_atc_exercise.py`, 32 cas) : paliers `grade()`, convergence géométrique de `make_conflict_pair()`, et le barème `_score_unlocked` (y compris la sémantique « résolu avant la perte de séparation »).
- ✅ **B4 corrigé** : les `except: pass` de `_run`/`_save` loggent désormais l'erreur (`_log.exception`).
- ⚪ **B1 reclassé - non-bug** : compter comme « non résolu » un conflit prédit devenu LoS est le barème **documenté** (S_conf = résolus *avant* la perte de séparation) ; un test le fige comme comportement voulu.
- ⚠️ **`S_radio` mal nommé** : compte les lignes *acceptées par BlueSky* (`len(lines)`), pas la qualité phraséologique - une clairance dangereuse mais bien formée est comptée « acceptée » (docstring `:23` trompeur).
- ⚠️ Concurrence non testée (double `stop()`, `note_command` après stop) ; **boucle potentiellement sans fin** si le 1er snapshot échoue (`_elapsed_unlocked` reste 0) ; conflits parasites du trafic de remplissage non contrôlés.

### 5.8 Serveur web + API (FastAPI) - `src/atc_app.py` (LOCAL), `src/server.py` (ROMEO)

**Verdict : ⚠️ l'app LOCALE fonctionne (démontré end-to-end sans GPU), mais zéro test d'API et service ROMEO non vérifiable ici.**

**Démarrage sans GPU (VÉRIFIÉ) :** `AI.mode()='local'`, `SIM.start()` charge BlueSky, `/api/nav` → 26 waypoints / 8 aéroports / secteur Reims. **Pipeline complet démontré** : scénario local → TAP203/SAS204 à FL300 ; `POST /api/command "TAP203 descend flight level one zero zero"` → `ALT TAP203 10000` ; **indicatif inconnu rejeté** ; **garde-fou sémantique** rejette un « descend » vers un niveau supérieur ; `/api/voice` → 503 en local (STT/TTS délégués au navigateur). **25 endpoints + WebSocket** recensés ; **correspondance `api.ts` ↔ backend totale**, aucune route orpheline.

**Lacunes :**
- ❌ **Aucun test d'API** (`httpx`/`TestClient` pas même installés) : `process_instruction`, `_check_alt_coherence`, filtre « indicatif inconnu », `_build_scn`, `WSManager.broadcast`, `lifespan`, montage StaticFiles - non couverts.
- ❌ **Bug B6** (repli `src/web` fantôme). → ✅ **corrigé** (repli supprimé + avertissement loggé).
- ⚠️ `server.py`/`pipeline_e2e.py`/`15_pipeline_demo.py` non lançables ici (torch/GPU/tunnel SSH) - `server.py` importe mais échouerait au 1er appel.
- ⚠️ `_broadcaster` avale toutes les exceptions ; `/api/gui/launch` dépend de PyQt5/6+PyOpenGL ; pas de CORS/auth (127.0.0.1).

### 5.9 Frontend React - `frontend/src/**`

**Verdict : ✅ fonctionne (build + typecheck vérifiés), avec ⚠️ dette de test/lint.**

**Vérifié :** cohérence `api.ts` ↔ endpoints **1:1** (aucune route fantôme) ; boucle temps réel = **WebSocket `/ws`** (pas de polling) avec **reconnexion auto** (1,5 s) et throttle React ~4 Hz ; **push-to-talk touche « V »** correct (gardes `!e.repeat` + « pas dans un INPUT », `preventDefault`, cleanup au démontage) ; `tsc -b --noEmit` → **EXIT 0**.

**Lacunes :**
- ❌ **Aucun test frontend et aucun ESLint** - oubli réel (le back a pytest+ruff, le front n'a que `tsc`+build). Non couverts : parsing WS, garde push-to-talk, encodage WAV (`audio.ts`), maths radar (`radar.ts`).
- ⚠️ **Fuite micro possible** : `keyup` « V » sur `window` ; un relâchement pendant une perte de focus (alt-tab, popup permission) peut ne jamais déclencher `stopTalk` → micro ouvert / état bloqué (pas de garde `blur`/`visibilitychange`).
- ⚠️ **Pas de repli HTTP** si le WS meurt durablement (`/api/state` existe mais n'est pas utilisée) ; `ScriptProcessorNode` déprécié ; backend absent au démarrage → `catch` silencieux (UI vide sans message).

### 5.10 Synthèse vocale pilote (TTS) - `src/tts_atc.py`, `tts_compat.py`, `make_pilot_voices.py`, `voice_exchange.py`

**Verdict : ⚠️ partiel / dépendant du cluster.** Chaîne correctement câblée (readback → XTTS clonage → resample 16 kHz → dégradation VHF → WAV), **mais la synthèse clonée ne fonctionne QUE sur ROMEO/GPU** (`torch` + `coqui-tts` absents de `bluesky-env`, `ModuleNotFoundError` vérifié). En LOCAL, le pilote parle via la **Web Speech API** du navigateur (voix OS générique, sans clonage ni VHF).

**Vérifié :** imports lourds *lazy* (`import tts_atc` réussit) ; partie déterministe (`preprocess_waveform`) exécutée ; wiring app complet (`atc_app.py:308-316`, `atc_ai.py:399-405`, `server.py:133-142`) ; repli navigateur (`audio.ts:21-36`, `useSim.ts:137-138`).

**Lacunes :**
- ❌ **Dégradation silencieuse** en LOCAL (l'utilisateur n'est pas averti qu'il n'entend plus une voix clonée VHF).
- ❌ **Zéro test** (chaîne post-XTTS resample/normalisation/VHF pourtant mockable sans GPU).
- ⚠️ **WER 22-24 % non reproductible** hors cluster (présent seulement dans `rapport_S6-S7` + README, aucun artefact chiffré).
- ⚠️ **Voix de référence absentes du dépôt** : `make_pilot_voices.py` les extrait d'ATCO2 via réseau HF vers `<XDG_DATA_HOME>/voices/` ; sans ça `default_voice() → None`. Les 4 WAV de `audio/` sont de la démo figée, **non utilisée par le code**.
- ⚠️ XTTS forcé sur CPU (bug cuFFT GH200), RTF ~0.82 ; `tts_compat.patch()` = monkey-patch de l'API interne de transformers (cassera silencieusement à une montée de version).

### 5.11 Campagne de validation - `validation/01..05`, `run_all.py`

**Verdict : ⚠️ partiel - fonctionne et reproductible, mais 02/05 dépendent de BlueSky (non relancés ici).**

**Vérifié par exécution (seed 42) :** `01_cpa_analytique` → err max **5.524e-4 NM**, **446 prédictions / 0 désaccord** ; `03_parseur_eval` → 68 phrases, **100 %** ; `04_generateur_eval` → **116/116 contraintes (100 %)**. Comparaison champ-à-champ vs `results.json` commité : **seuls les `duree_s` diffèrent**, tout le reste est bit-identique. **Concordance `results.json` / docs / README : parfaite** (CPA MAE 0.067, RMSE 0.108, F1=1.000, etc.).

**Lacunes :**
- `02_cpa_vs_bluesky` **non relancé** ici (~11 min) : MAE 0.067 / F1=1.000 confirmés par cohérence JSON↔docs, pas re-exécutés (BlueSky est installé → reproductible en local, hors CI).
- **`run_all.py` n'inclut pas `05_performance.py`** (liste = 01..04) : la campagne « complète » exclut la performance.
- **Aucune assertion/seuil** : les scripts écrivent le JSON mais **n'échouent pas** si une métrique se dégrade → régression silencieuse possible (F1 qui chute ne casse aucun test).
- Docstring de `03` périmé (« 67 phrases » vs 68) ; `duree_s` dans le JSON + figures PNG regénérées = diffs git non déterministes.

### 5.12 Infra, reproductibilité & hygiène

**Verdict : ⚠️ partiel - socle vérifiable sain et honnête ; faiblesses côté reproductibilité long terme.**

**Vérifié :** **hygiène git correcte** (le venv `src/bluesky-env` n'est **pas** commité ; `.gitignore` complet - pas d'anti-pattern venv-dans-git) ; **3 scénarios JSON valides** et conformes au consommateur `atc_ai._items_to_aircraft` ; **CI cohérente** avec le périmètre pur testé.

**Lacunes :**
- ❌ **Aucune dépendance épinglée** (`requirements-*.txt` : que des `>=`) ; **aucun lock Python** (seul `frontend/package-lock.json` verrouille). Install neuf non reproductible dans le temps.
- ⚠️ **Pas de `.python-version`** (`requires-python >=3.11` laisse diverger).
- ⚠️ **CI = modules purs uniquement** : bluesky/torch/fastapi/XTTS et les endpoints jamais exercés → un import cassé dans `atc_app.py`/`server.py`/`tts_atc.py` passerait la CI.
- ⚠️ **Scénarios JSON non validés** par schéma ni test (`_list_scenarios` avale les erreurs, `atc_app.py:182`).
- ⚠️ **Scripts ROMEO non portables** (chemins `/gpfs/...`, alias ssh `romeo`, quotas - spécifiques à un compte/cluster).

---

## 6. Angles morts et oublis résiduels (revue critique)

> Deux corrections d'audits intermédiaires, à noter : (1) `graph_secteur.py` (runtime) **est** testé - l'audit « SectorGraph » visait le *générateur* standalone `02_airspace_graph.py` ; (2) le parseur **local** gère bien le **français en entrée** (`atc_ai.py:60-62,75,123-125`) - le défaut « anglophone » ne concerne que la **sortie** readback.

**🔴 Critique**
- **Repli UI mort et trompeur** (Bug B6) - ✅ **fait** : bloc `WEB_LEGACY` retiré, avertissement loggé si `frontend/dist` est absent.
- **Garde-fous sémantiques non testés** - `process_instruction` (filtre « indicatif inconnu ») et `_check_alt_coherence` (cohérence climb/descend) sont **purs** mais sans test → ajouter `tests/test_atc_app_local.py` (`fastapi.TestClient`) en mockant `AIClient`/`SimManager`.
- **`kb_oaci.py` non testé** - `build_documents()` est la **source des embeddings RAG** (bornes/actions injectées au prompt) ; un décalage `LIMITS` ↔ fiches serait invisible.

**🟠 Important**
- **Zéro épinglage de dépendances** → produire un lock (`pip freeze`/`uv.lock`) au moins pour l'env local vérifié.
- **Incohérence de version Python** (badge/pyproject 3.11-3.12, CI 3.12, machine 3.14, pas de `.python-version`) → ajouter `.python-version` (3.12).
- **7 scripts démo hors couverture** (`live_demo`, `live_voice_session`, `pipeline_e2e`, `voice_exchange`, `radar_anim`, `radar_scope`, `radar_replay`) - PoC dépendant de ROMEO/BlueSky, à **documenter explicitement** comme non couverts.
- **`pipeline_e2e.wer` maison** (distance d'édition ad hoc, pas `jiwer`) → le « WER 22-24 % » n'est pas la métrique standard ; à signaler comme non comparable.

**🟡 Mineur**
- `/api/weather/zone` lit `payload["x"]/"y"` en dur → 500 non géré (pas de pydantic sur les `Body(dict)`).
- Aucun CORS/auth (host `127.0.0.1`) - OK en local, à noter avant exposition réseau.
- Scénarios JSON validés par aucun schéma (erreurs avalées).
- `04_ner_extraction.extract()` pur mais 0 test.
- `make_pilot_voices.py`/`atc_data.py` : chemins `/gpfs/scratch/nimarano` en dur, voix `pilot_*.wav` absentes du dépôt.

---

## 7. Plan d'action priorisé

**Lot 1 - Bugs vérifiés - ✅ FAIT (2026-07-01)**
1. ✅ **B2** `atc_sim.py` : détection CD par flag `self._cd_on` (positionné dans `_enable_cd`) → repli géométrique de nouveau atteignable ; `_analyze_cd` en méthode d'instance.
2. ✅ **B4** `atc_exercise.py` : `except: pass` de `_run`/`_save` remplacés par `_log.exception(...)`.
3. ✅ **B3/B5** ASR : `atc_asr.py` accepte `preprocessor_config.json` **et** `processor_config.json` ; `server.py` pointe par défaut sur l'adaptateur commité (override `ATC_ADAPTER`).
4. ✅ **B6** `atc_app.py` : repli mort `src/web` supprimé + avertissement loggé si `frontend/dist` absent.
5. ⚪ **B1** : reclassé non-bug (comportement documenté) ; **aucune modification de code**, un test fige le comportement voulu.

**Lot 2 - Oublis de test CI-testables - 🟡 PARTIEL**
6. ✅ `tests/test_atc_exercise.py` (32 cas) : `grade()`, géométrie de `make_conflict_pair()`, barème `_score_unlocked`.
7. ✅ `tests/test_atc_audio.py` (6 cas) : atténuation hors-bande, reproductibilité rng, robustesse signal muet.
8. ⬜ **Reste à faire** : `tests/test_atc_app_local.py` (API via `fastapi.TestClient` ; prérequis : rendre `AIClient()`/`SimManager()` *lazy*), `atc_ai.AIClient` (mock `requests`), `kb_oaci`, `04_ner_extraction`, `atc_llm.parse_orders`, et front (`vitest` + ESLint).

**Lot 3 - Robustesse & reproductibilité - 🟡 PARTIEL**
9. ✅ `.python-version` (3.12) ajouté ; ✅ log sur scénario JSON invalide (`_list_scenarios`) ; ✅ garde `blur`/`visibilitychange` anti-fuite micro (push-to-talk).
10. ⬜ **Reste à faire** : épingler les dépendances (lock `pip freeze`/`uv.lock`) ; schéma pydantic/JSON Schema sur les scénarios et les payloads `Body(dict)` ; seuils/assertions dans les scripts de validation ; artefact reproductible des WER S4 (`evaluation_s4.json`).

---

## 8. Conclusion

**Est-ce que ça fonctionne réellement ? Oui, pour son cœur LOCAL** : radar temps réel, interprétation des clairances (FR/EN), simulation BlueSky, garde-fous de sécurité et collationnement texte sont **exécutés et vérifiés de bout en bout** sur un poste sans GPU, et la campagne de validation est **reproductible à l'identique**. Le projet est techniquement solide et honnête dans ses affirmations mesurables.

**Qu'a-t-on oublié - et qu'a-t-on corrigé ?** L'audit avait relevé (1) des défauts réels dans des chemins non testés et (2) un déséquilibre de couverture. **Le Lot 1 est traité** : le repli de sécurité BlueSky (B2) fonctionne de nouveau, les erreurs silencieuses de l'exercice (B4) sont loggées, le chargement de l'adaptateur ASR (B3/B5) et le repli UI mort (B6) sont corrigés ; le « bug » de notation (B1) s'est révélé être le **barème documenté** (reclassé, non modifié). La notation d'exercice et le prétraitement VHF - jusque-là sans filet - sont maintenant **couverts par 38 tests**. **Reste** (Lot 2/3, non bloquant) : tests d'API/`AIClient`/frontend, épinglage des dépendances, schémas de validation des scénarios.

La chaîne IA lourde (Whisper, Mistral+RAG, XTTS) est **correctement câblée** mais **non vérifiable hors du cluster ROMEO/GPU** ; ses performances annoncées reposent sur les rapports, faute d'artefacts reproductibles commités. C'est une limite de reproductibilité, pas un défaut de conception.

---

<sub>Audit produit le 2026-07-01 par analyse multi-agents (14 agents) + vérification directe par exécution. Chaque verdict est adossé à une preuve (`fichier:ligne` ou commande exécutée). Les briques « non vérifiables ici » le sont faute de GPU/cluster/réseau, et non par constat d'échec.</sub>
