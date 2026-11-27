# Campagne NVIDIA-NemotronLabs-VoiceChat-11B sur ROMEO

Évaluation du modèle **bout-en-bout parole-à-parole full-duplex**
[`nvidia/NVIDIA-NemotronLabs-VoiceChat-11B`](https://huggingface.co/nvidia/NVIDIA-NemotronLabs-VoiceChat-11B)
sur la tâche ATC du projet, en comparaison **appariée** avec la chaîne en
cascade Whisper-LoRA → Mistral-7B → XTTS déjà mesurée sur le même cluster.

## Pourquoi ce modèle

L'architecture du projet est une **cascade** de trois services (STT, LLM, TTS)
au contrat OpenAI-compatible. VoiceChat propose l'alternative exactement
opposée : un modèle unique (encodeur Fast Conformer + dorsale Nemotron Nano v2
9B hybride Mamba/Transformer + décodeur TTS + **canal séparé d'appel d'outils**)
qui écoute et parle en continu, avec une latence de prise de parole annoncée à
~450 ms. Le canal d'appel d'outils permet de produire l'ordre structuré
(l'équivalent du JSON d'ordres du LLM de la cascade) *pendant* que le canal
audio prononce le collationnement pilote : c'est la seule façon de tester ce
modèle sur la tâche du projet sans dénaturer son fonctionnement.

Limites annoncées par NVIDIA et directement pertinentes ici : le modèle
« n'est pas adapté aux environnements bruités ou fortement réverbérants », la
précision des **arguments** d'appel d'outil est mesurée à 44,2 % sur
Full-Duplex-Bench v3 (sélection de l'outil : 82,5 %), et il est publié
« pour la recherche uniquement ». La condition radio du banc (passe-bande VHF
300-3400 Hz + bruit SNR 12 dB) est donc volontairement adverse.

## Contraintes ROMEO rencontrées (et contournement)

| Contrainte | Constat | Contournement retenu |
|---|---|---|
| Quotas GPFS | `home`, `scratch` et `projet` sont **tous** à 17,5 Go pour 15 Go de quota souple, délai de grâce **expiré** → toute écriture est refusée ; plafond dur 20 Go | **Rien n'est écrit sur GPFS et rien n'est supprimé.** Tout vit sur le disque RAM du nœud (`/dev/shm`, 239 Go) |
| Taille du checkpoint | 44,4 Go (un seul `model.safetensors`) → ne tient dans aucun des trois espaces | Téléchargement direct dans `/dev/shm` (xet, 16 connexions : **42 Go en ~2 min**) |
| Architecture | Nœuds GPU **aarch64** (Grace + H100 / GH200 120 Go) ; aucune roue précompilée pour `causal-conv1d` / `mamba-ssm` | Compilation depuis les sources sur le nœud (nvcc 12.6, `MAX_JOBS=32`) |
| Résolution pip | L'installation de `mamba-ssm` remplace **torch 2.10 par torch 2.13** (PyPI) et casse l'ABI des noyaux compilés (`undefined symbol: ...materialize_cow_storage...`) | Réinstallation de torch 2.10.0+cu128 puis reconstruction avec `--no-deps` ; fichier de contraintes pour toutes les dépendances NeMo |
| Caches d'exécution | Triton compile ses noyaux au **premier appel** et écrit dans `$HOME/.triton` → `OSError [Errno 122] Disk quota exceeded` sur *chaque* stimulus (matplotlib, lhotse, `.nv` idem) | `HOME` lui-même redéfini sur `/dev/shm` après l'activation conda, plus `TRITON_CACHE_DIR`, `TORCHINDUCTOR_CACHE_DIR`, `NUMBA_CACHE_DIR`, `XDG_CACHE_HOME`, `MPLCONFIGDIR`, `HF_HOME` |
| Décodage audio | `torchaudio.load` de la 2.10 délègue à `torchcodec` : aucune roue 0.10 en aarch64 (0.11+ seulement) et FFmpeg absent de l'environnement | E/S audio faites directement en `soundfile` + `scipy` dans `voicechat_infer.py` (strictement équivalent à `load_wav_16k_mono`) |
| Transfert des fichiers | Impossible de passer par GPFS | `sbcast` depuis `/tmp` du nœud de login vers `/dev/shm` du nœud de calcul ; résultats rapatriés en base64 par la sortie standard de `srun --overlap` (`pull_results.sh`) |

## Protocole

Stimuli **identiques bit à bit** à ceux du banc `e2e_bench` (vérifié par
empreinte MD5), pour une comparaison appariée case par case :

| Condition | Source | Référence cascade |
|---|---|---|
| `sapi_radio` | voix SAPI + canal radio (VHF 300-3400 Hz, bruit SNR 12 dB, graine 7) | 76 % (`e2e_bench_romeo.json`) |
| `sapi_propre` | voix SAPI sans dégradation | — (isole l'effet du canal) |
| `humain_micro` | locuteur humain (nicolas), micro brut | 80 % (`human_e2e.json`) |
| `humain_radio` | locuteur humain + même canal radio | 72 % (`human_e2e.json`) |

**Silence final obligatoire (0,25 s avant / 6 s après).** VoiceChat est
full-duplex *synchrone à la trame* : sa boucle de génération est
`for t in range(1, T)` où `T` est le nombre de trames de l'**entrée**. Sans
silence après la clairance, le modèle ne dispose d'aucune trame pour
prononcer son collationnement ni pour terminer son appel d'outil — nos
stimuli d'origine (3,9 s de parole, 0 s de silence) rendaient la tâche
littéralement impossible. Les échantillons officiels de NVIDIA portent 3,9 s
à 4,7 s de silence final ; on retient 6 s, ce qui correspond aussi à la
réalité opérationnelle (le contrôleur relâche l'alternat, la fréquence reste
ouverte pendant que le pilote collationne). **Le signal de parole reste bit à
bit identique à celui reçu par la cascade** : seul du silence numérique est
ajouté autour.

25 clairances × 4 conditions = **100 stimuli**, deux modes chacun :

* `s2s` — une passe, le modèle répond à la radio (audio 22,05 kHz + texte) ;
* `fc` — deux passes (protocole officiel NVIDIA) : détection de l'appel
  d'outil, injection de la réponse d'API, puis décodage audio.

L'invite système ATC reprend **les règles de conversion de
`src/atc_llm.SYSTEM`** (mêmes codes OACI, mêmes bornes, même contrat de
sortie), en ASCII strict comme l'exige la carte modèle. L'outil déclaré,
`set_flight_order(callsign, action, value, waypoint)`, est le miroir exact du
JSON d'ordres attendu de la cascade.

Le scoring est **local** et passe par le code de production du dépôt
(`atc_llm.postprocess_orders` : normalisation d'indicatif, graphe secteur,
bornes de sécurité S2), afin que seule l'étape de compréhension change.

## Résultats (19 août 2026, GH200 120 Go, 100 stimuli)

Fichier complet : `bench/results/voicechat_romeo.json`.

### Calibration de l'invite (préalable indispensable)

| Invite | Longueur | Résultat |
|---|---|---|
| défaut NVIDIA | 248 c. | répond en assistant (« I am NVIDIA Voice Chat… »), hors sujet |
| ATC courte sans exemple | 214 c. | parle, mais invente l'indicatif (« Bravo Papa ») |
| **ATC courte avec exemple** | **468 c.** | **collationnement correct, propre et radio → invite retenue** |
| ATC + outils, gabarit officiel | 2 910 c. | **muet**, et 262 s au lieu de 31 s |
| ATC + outils, gabarit compact | 1 189 c. | pose une question, aucun appel d'outil, 86 s |
| ATC + outil minimal écrit à la main | 378 c. | paraphrase, aucun appel d'outil |

Les tokens d'invite système consomment des **trames de génération** : plus
l'invite est longue, moins il reste de trames pour répondre — au point que
l'invite à outils rend le modèle muet. C'est le résultat le plus structurant
de la campagne.

### Compréhension des clairances

Critère : le collationnement contient l'**action**, la **valeur** et
l'**indicatif** attendus (après `norm_radio`, validé 25/25 sur les
collationnements canoniques du dépôt).

| Condition | Collationnement complet | Instruction seule (action + valeur) | WER collat. | Latence médiane |
|---|---|---|---|---|
| `sapi_radio` | **9/25 = 36 %** [20 ; 55] | 17/25 = 68 % | 0,85 | 30,9 s |
| `sapi_propre` | 9/25 = 36 % [20 ; 55] | 18/25 = 72 % | 1,03 | 30,8 s |
| `humain_micro` | 12/25 = 48 % [30 ; 67] | 18/25 = 72 % | 0,97 | 37,0 s |
| `humain_radio` | 5/25 = 20 % [9 ; 39] | 13/25 = 52 % | 1,92 | 37,3 s |

**Aucun appel d'outil sur les 100 stimuli** ; 1 réponse muette sur 100.

### Comparaison appariée avec la cascade (McNemar exact, correction de Holm)

| Comparaison | VoiceChat | Cascade | n01 / n10 | p (Holm) |
|---|---|---|---|---|
| `sapi_radio` vs cascade ROMEO | 9/25 | 19/25 | 0 / 10 | **0,006** |
| `sapi_radio` vs cascade locale | 9/25 | 19/25 | 0 / 10 | **0,006** |
| `humain_micro` vs cascade | 12/25 | 20/25 | 0 / 8 | **0,008** |
| `humain_radio` vs cascade | 5/25 | 18/25 | 0 / 13 | **0,001** |

`n01 = 0` partout : **VoiceChat n'a réussi aucun cas que la cascade rate**.
Sa performance est un sous-ensemble strict de celle de la chaîne existante.

### Mode d'échec dominant : l'indicatif

31 cas sur 100 ont l'instruction correcte mais l'indicatif faux. Exemples
(condition `sapi_radio`) :

| Attendu | Collationnement produit |
|---|---|
| `HDG EZY21 100` | « Y two hundred one fly heading one hundred, air France Y two hundred one » |
| `HDG BAW57 310` | « Beware five seven turn left heading three hundred and ten » |
| `ALT CSA1DZ 24000` | « Climb flight level two four zero, Delta Zulu » |
| `ALT BAW57 8000` | « Descend to flight level eighty, C-A-W-U five thousand seven hundred » |
| `HDG DLH88 180` | « Lutana eight heading one hundred and eighty zero » |

Le modèle « naturalise » aussi les nombres (`FL320` → « three hundred and
twenty zero », `DLH88` → « eight hundred and eighty »), ce qui rompt la
phraséologie OACI chiffre par chiffre.

### Parole produite (sous-échantillon audio, n = 3)

La voix de synthèse du modèle est **excellente** : le juge STT fixe
(faster-whisper small, protocole `tts_bench`) la retranscrit quasi
parfaitement.

| Moteur | WER aller-retour |
|---|---|
| **VoiceChat-11B** (n = 3) | **0,048** [0,00 ; 0,14] |
| SAPI (référence banc) | 0,160 |
| Kokoro-82M (4 voix) | 0,182 - 0,260 |
| XTTS voix clonées ROMEO | 0,649 - 0,920 |

⚠ Deux réserves : n = 3 seulement, et le chiffre 0,048 suppose une correction
de **format** appliquée au juge (Whisper écrit « 1-2-3-4 » là où le modèle dit
« one two three four » ; sans cette fusion des chiffres tiretés le WER affiche
0,71 alors que la transcription est mot pour mot correcte). Les moteurs de
référence ci-dessus ont été mesurés sans cette correction : la comparaison est
donc indicative, pas homogène.

### Coût

Chargement du modèle : 166-180 s (checkpoint 44,4 Go, fp32 → 44,5 Go de VRAM ;
le passage en bf16 tombe à 22,3 Go mais casse le décodeur TTS, dtypes mixtes).
Génération : **RTF ≈ 3** (32 s pour 10,8 s d'audio), *décodage audio compris* -
celui-ci est quasi gratuit (32,7 s avec audio contre 32,2 s sans). Les 253 s
observées au premier essai venaient bien de l'invite à outils, pas du codec.
À comparer aux 8,4 s de latence totale médiane de la cascade sur le même
cluster (2,5 s en local).

Ces chiffres sont ceux du **chemin de référence NeMo hors ligne**, pas du
moteur vLLM temps réel annoncé par NVIDIA (~450 ms de prise de parole) :
ils mesurent la faisabilité d'une évaluation, pas la latence déployable.

## Fichiers

| Fichier | Rôle |
|---|---|
| `job_probe.slurm`, `job_probe2.slurm` | sondages de faisabilité (toolchain, quotas, disque nœud, débit HF) |
| `job_setup.slurm` | job d'allocation : environnement + checkpoint sur `/dev/shm`, puis reste vivant |
| `prepare_stimuli.py` | reconstruit les 4 conditions avec le code exact du banc, produit `manifest.json` + archive |
| `voicechat_infer.py` | inférence côté cluster (invite système ATC, outils, mesures de latence) |
| `run_campaign.sh` | étapes `smoke` / `pilote` / `complet` sur le nœud |
| `../voicechat_bench.py` | scoring local + statistiques appariées → `bench/results/voicechat_romeo.json` |

## Reproduire

```bash
# 1. stimuli (poste local, venv du banc)
bench/bench-env/Scripts/python.exe bench/voicechat/prepare_stimuli.py

# 2. allocation + environnement + checkpoint (ROMEO)
tr -d '\r' < bench/voicechat/job_setup.slurm | ssh romeo sbatch

# 3. transfert vers le disque RAM du nœud
scp bench/results/voicechat_stimuli/stimuli.tar.gz bench/voicechat/voicechat_infer.py romeo:/tmp/
ssh romeo 'sbcast -j <jobid> -f /tmp/stimuli.tar.gz /dev/shm/vc/stimuli.tar.gz'

# 4. campagne
ssh romeo 'srun --jobid=<jobid> --overlap bash /dev/shm/vc/run_campaign.sh complet'

# 5. scoring local
bench/bench-env/Scripts/python.exe bench/voicechat_bench.py
```

Après la campagne : `ssh romeo "scancel --name=vc-setup"` pour libérer le nœud.
