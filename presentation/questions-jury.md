# Questions du jury et réponses préparées

Soutenance de stage M1 CHPS, Nicolas Marano.
Jury : Christophe Jaillet et Jean-Charles Boisson. Rapport relu par Luiz Angelo Steffenel.

---

## Mode d'emploi

Chaque question est suivie de la réponse à dire, en deux à cinq phrases, et du renvoi
au rapport. Quand la question est un piège, le piège est nommé explicitement.

Trois règles qui valent pour toutes les réponses ci-dessous.

1. **Donner le chiffre avec son terme de comparaison.** Jamais « 28,5 % » tout seul,
   toujours « 28,5 % contre 71,9 % avant adaptation ».
2. **Ne jamais défendre un chiffre que vous n'avez pas mesuré.** La formule à avoir
   prête : « je ne l'ai pas mesuré, donc je ne peux pas vous répondre avec un chiffre ».
   C'est exactement la posture que défend le rapport, et le jury le sait puisqu'il l'a lu.
3. **Un désaccord n'est pas une attaque.** Si un membre du jury conteste un choix,
   commencez par reformuler son objection avant d'y répondre. Cela vous fait gagner
   cinq secondes de réflexion et cela montre que vous écoutez.

---

## 0. Les douze questions qui tombent presque à coup sûr

Si vous ne préparez que douze réponses, ce sont celles-là.

**Q0.1. Qu'avez-vous fait vous-même dans ce projet ?**

> Les modèles et les corpus viennent de la communauté : Whisper, Mistral, Qwen, XTTS,
> Kokoro, les trois corpus ATCO2, UWB-ATCC et ATCOSIM, et le simulateur BlueSky.
> Personne n'entraîne un modèle de reconnaissance vocale depuis zéro en dix semaines,
> et ce n'était pas le sujet. Ce qui est de moi : le canal VHF simulé, le graphe de
> secteur et son validateur, les neuf fiches de phraséologie, l'adaptateur LoRA de
> 14 Mo qui est le seul artefact de modèle du projet à être de moi, la couche de
> validation déterministe, le connecteur vers le simulateur, le moteur d'exercices et
> son barème, l'application web complète, et tout le banc de mesure avec ses corpus
> annotés. Autrement dit : les briques d'IA viennent de la communauté, l'architecture
> de sûreté et l'appareil de preuve sont le travail du stage.

*Renvoi : rapport §3.5, tableau des outils ; diapositive 8.*

**Q0.2. Quel est le résultat dont vous êtes le plus fier ?**

> Un seul chiffre : sur les 1 871 ordres proposés par les six systèmes évalués, la
> couche de validation en a rejeté 810, soit 43 %, et parmi les 1 075 lignes qui sont
> passées, aucune ne viole une borne physique, aucune ne porte une action inconnue,
> aucune ne vise un point qui n'existe pas. Y compris avec Llama-3.2-1B, qui est à
> 3,4 % d'exactitude et qui a vu 636 de ses 1 391 propositions rejetées. Cela veut dire
> que la sûreté du système ne dépend pas de la qualité du modèle.

*Renvoi : rapport §5.4, paragraphe « Sécurité mesurée ».*

**Q0.3. En quoi est-ce du calcul haute performance ?**

> Sur trois plans. Le volet apprentissage a tourné sur un nœud NVIDIA GH200 de ROMEO,
> une architecture ARM avec 96 Go de mémoire unifiée, sous SLURM, avec un quota de 20 Go
> par partition qui a directement redessiné mon pipeline de données. Le volet inférence
> pose un problème de placement et de latence : trois modèles à servir, une contrainte de
> boucle interactive, et l'arbitrage entre pleine précision sur le cluster et
> quantification 4 bits en local, que j'ai chiffré à 1,7 point d'exactitude. Et le volet
> mesure est un problème de performance pur : facteurs temps réel, p95 de latence,
> montée en charge du simulateur mesurée jusqu'à 200 aéronefs.

*Renvoi : rapport §1.1, §4.1, §5.4.*

**Q0.4. Un WER de 28,5 %, ce n'est pas énorme pour un domaine critique ?**

> Si, et je l'écris tel quel dans les limites. C'est élevé. Deux choses à mettre en face.
> D'abord ce n'est pas un chiffre absolu mais un chiffre relatif à un test volontairement
> sévère : ATCO2 est un corpus de fréquences opérationnelles réelles que le modèle n'a
> jamais vu à l'entraînement, et le même modèle sans adaptation est à 71,9 %. Ensuite, et
> c'est le point important, ce n'est pas la reconnaissance vocale qui rend le système
> utilisable malgré ce taux, c'est la validation déterministe : elle convertit la plupart
> des erreurs de transcription en rejets explicites plutôt qu'en manœuvres fausses. Un
> rejet coûte à l'élève une répétition ; une manœuvre fausse lui coûte un apprentissage
> faux.

*Renvoi : rapport §5.3 et §6.2.*

**Q0.5. Pourquoi ne pas avoir affiné le modèle de langage, comme vous avez affiné Whisper ?**

> Trois raisons, et j'avais l'article qui fait cela sous les yeux, Sharifi, Zongo et Wei.
> D'abord il n'existe pas de corpus public appariant des clairances et les commandes
> exécutables correspondantes à l'échelle qu'il aurait fallu ; il aurait fallu le
> construire, et ce chantier seul dépassait dix semaines. Ensuite le coût d'itération
> était incompatible avec un quota de 20 Go. Enfin, et c'est la raison de fond : je
> refusais de faire reposer la sécurité sur des poids appris, qui ne sont pas auditables.
> On ne peut pas relire un modèle pour vérifier qu'il n'autorisera jamais 99 000 pieds ;
> on peut relire trois lignes de code qui le vérifient.

*Renvoi : rapport §2.3.*

**Q0.6. Vos mesures sont faites sur un portable, pas sur le cluster. Est-ce sérieux ?**

> C'est une conséquence subie, pas un choix : ROMEO est devenu totalement indisponible
> pour une maintenance de sécurité au moment exact où je lançais les benchmarks. Et
> j'ai justement mesuré ce que cette substitution coûte. Sur les 25 clairances de bout
> en bout, la campagne locale et la campagne cluster donnent le même 19 sur 25, la même
> attribution des échecs, et en ouvrant les deux fichiers, exactement les mêmes six cas
> en échec, les cas 4, 8, 10, 12, 13 et 24. Deux piles logicielles différentes, deux
> matériels différents, un modèle en pleine précision d'un côté et quantifié sur 4 bits
> de l'autre, et le résultat fonctionnel est identique. La différence est ailleurs :
> 2,6 s de latence en local contre 9,0 s à travers le tunnel vers le cluster.

*Renvoi : rapport §4.4 et §5.6, tableau de bout en bout.*

**Q0.7. Est-ce que votre système est utilisable en formation aujourd'hui ?**

> Non, et je le dis en toutes lettres dans le rapport. Il est démontré qu'un élève peut
> parler aux avions et qu'ils répondent correctement dans 76 à 80 % des cas, pour 2,6 s
> de latence. Il n'est démontré nulle part qu'un élève entraîné avec cet outil progresse,
> ni qu'il progresse autant qu'avec un pseudo-pilote humain. Cette validation-là demande
> de vrais élèves contrôleurs et un protocole de sciences de l'éducation, ce qui sortait
> entièrement du périmètre de dix semaines. C'est la limite la plus importante du travail,
> et c'est la seule validation qui compterait vraiment pour l'usage visé.

*Renvoi : rapport §6.3.*

**Q0.8. Quelle est la partie la plus fragile de votre système ?**

> L'étage de reconnaissance vocale, sans hésiter. La moitié des échecs de bout en bout
> vient d'une transcription déviée, et j'ai un défaut parfaitement caractérisé : les
> indicatifs alphanumériques épelés. « csa one delta zulu » est transcrit parfaitement,
> avec un WER nul, et c'est le modèle de langage qui le réassemble en CSAD12Z au lieu de
> CSA1DZ. Le défaut est indépendant du locuteur et du canal, il apparaît à l'identique
> avec la voix de synthèse et avec la mienne. C'est ma première perspective, et elle ne
> demande aucun nouvel apprentissage : une normalisation déterministe des indicatifs
> épelés, en amont du modèle.

*Renvoi : rapport §5.6 et annexe, lignes 10 et 24.*

**Q0.9. Vous avez trouvé un bug dans votre propre garde de sécurité. Racontez.**

> C'est l'épisode qui m'a le plus appris. En semaine 8, une clairance « descend flight
> level one » est tronquée par la transcription, le modèle comble le vide et hallucine un
> niveau supérieur au niveau courant : l'avion serait monté sur un ordre de descente.
> J'ajoute une garde qui compare le verbe au sens du changement de niveau, je rejoue le
> cas sur le cluster, il est bloqué, je pense avoir fermé la porte. Un mois plus tard, la
> revue adversariale me détrompe : ma garde comparait des chaînes de caractères, 32000.0
> d'un côté et 32000 de l'autre. En cas de désaccord de forme, l'ordre annoncé comme
> bloqué à l'utilisateur pouvait quand même être exécuté. C'est le pire des cas : une
> fausse assurance. J'en tire deux règles : une garde doit être vérifiée en cherchant
> soi-même à la contourner, parce qu'elle n'a aucune raison de se signaler comme
> défaillante, et l'annonce d'un blocage doit être dérivée de l'action réellement
> appliquée, jamais calculée en parallèle.

*Renvoi : rapport §4.3 ; diapositive 22.*

**Q0.10. Si c'était à refaire, que changeriez-vous ?**

> Trois choses concrètes. Je construirais le banc de mesure en semaine 2, pas en juillet :
> tous mes chiffres intermédiaires auraient été comparables entre eux, et je n'aurais pas
> traîné pendant tout le stage un chiffre XTTS de 22 à 24 % obtenu par une métrique maison
> que le banc final a démenti à 65-92 %. Je normaliserais les indicatifs de manière
> déterministe dès le départ. Et je mesurerais chaque modèle à travers sa pile de
> déploiement réelle dès le premier jour, parce que l'épisode Mistral m'a montré qu'un
> chiffre exact peut décrire un système faux : 21 % ou 82 % pour le même modèle, la même
> quantification et la même consigne, selon un détail du moteur de service.

*Renvoi : rapport §4.2, §5.5, §6.3.*

**Q0.11. Quel est le rapport entre ce stage et la formation CHPS ?**

> La formation m'a donné trois choses que j'ai utilisées quotidiennement. Le travail sur
> machine partagée avec ordonnanceur, qui est le mode de vie normal d'un calculateur et
> qui change la façon dont on organise ses essais, puisqu'un essai raté coûte le temps de
> calcul plus le temps de file. Le raisonnement sur la mémoire et le placement des
> données, qui est exactement ce que le quota de 20 Go m'a forcé à faire. Et la culture
> de la mesure : facteurs temps réel, centiles, montée en charge, ce sont les instruments
> du calcul haute performance appliqués ici à une chaîne d'IA.

**Q0.12. En une phrase, qu'avez-vous démontré ?**

> Qu'on peut parler à des avions simulés et qu'ils répondent correctement dans 76 à 80 %
> des cas en 2,6 secondes, et surtout qu'on peut garantir qu'aucun ordre absurde
> n'atteindra le simulateur, quelle que soit la qualité du modèle qui l'a proposé, parce
> que la garantie est portée par quelques centaines de lignes de code auditables et non
> par des poids appris.

---

## 1. Cadre du stage, sujet, périmètre

**Q1.1. Quel était exactement le sujet de la convention ?**

> « Développement d'un simulateur d'entraînement par IA pour contrôleurs aériens », avec
> la mention PoC, preuve de concept. Trois activités y étaient détaillées : apprendre à
> l'IA le vocabulaire du contrôleur aérien, créer une interface vocale avec simulation
> des détériorations audio des transmissions radio, et programmer un environnement
> multi-agents avec pilotes, tour de contrôle, tuteur et évaluateur. Les trois se
> retrouvent dans le livrable : la base de phraséologie et l'adaptation de Whisper pour
> la première, la chaîne vocale et le canal VHF pour la deuxième, l'application avec ses
> pilotes IA, son poste instructeur et son mode exercice noté pour la troisième.

**Q1.2. Vous dites avoir dépassé le PoC demandé. N'est-ce pas de la surenchère ?**

> Le livrable dépasse effectivement le périmètre initial, mais pas par ambition
> décorative : il fallait un environnement complet pour pouvoir éprouver le dialogue
> vocal. Un dialogue ne se teste pas dans le vide. Pour que l'avion ait un ordre à
> exécuter et un état à collationner, il faut du trafic, un secteur, un radar. Je le dis
> explicitement dans le rapport : le radar, les exercices et le simulateur ne sont que
> l'infrastructure de test, tout le projet se joue dans l'échange radio entre l'élève et
> l'avion.

**Q1.3. Combien de temps avez-vous réellement travaillé ?**

> 406 heures effectives entre le 13 avril et le 31 juillet 2026, la convention prévoyant
> une interruption du 4 au 31 mai. Côté projet, cela structure dix semaines de travail,
> S1 à S10, plus deux phases d'industrialisation en juin et juillet.

**Q1.4. Le travail est-il individuel ?**

> Oui. Conception, développement, campagnes de validation et rédaction, dans le cadre du
> suivi de mon tuteur. Les corpus, modèles et outils tiers sont crédités en bibliographie
> et récapitulés dans un tableau dédié en section 3.5.

**Q1.5. Y a-t-il un lien avec une école de contrôleurs, l'ENAC, la DSNA ?**

> Non, aucun. C'est un travail de laboratoire, pas un projet commandité par un organisme
> de formation. Cela explique d'ailleurs directement la limite pédagogique : je n'ai eu
> accès à aucun élève contrôleur pour éprouver la valeur d'entraînement du système.

**Q1.6. Ce projet est-il une suite d'un travail existant au LICIIS ?**

> Le sujet m'a été proposé par mon tuteur ; le code, l'architecture et les campagnes de
> mesure ont été construits pendant le stage. Ce qui préexistait, ce sont les ressources
> publiques que j'inventorie en section 3.5 : le cluster, les corpus, les modèles ouverts
> et BlueSky.

---

## 2. Le métier et le problème à résoudre

**Q2.1. Qu'est-ce qu'un collationnement, et pourquoi est-ce central ?**

> C'est la répétition littérale de l'instruction par le pilote. Ce n'est pas une formule
> de politesse : c'est le mécanisme de sécurité central de la radiotéléphonie, celui qui
> permet au contrôleur d'entendre immédiatement si son ordre a été mal compris. Et c'est
> très exactement ce que mon système doit produire, la moitié « retour » de la boucle
> vocale.

**Q2.2. Pourquoi la phraséologie est-elle plus facile ou plus difficile qu'une langue ordinaire ?**

> Les deux à la fois, et c'est ce qui rend le problème intéressant. Plus facile parce que
> c'est une langue volontairement appauvrie : vocabulaire fermé, ordre des mots normalisé,
> prononciation des chiffres imposée, ce qui donne un espace de sortie petit et vérifiable.
> Plus difficile parce que les modèles de fondation n'en ont vu presque aucun exemple, et
> parce qu'elle est impitoyable sur la forme : « climb » et « descend » ne diffèrent que
> par un mot et l'inversion est une faute grave.

**Q2.3. Les avions se parlent-ils entre eux dans votre système ?**

> Non, et cela vaut aussi pour la réalité : les pilotes ne se donnent pas d'instructions
> entre eux. Dans mon système, chaque avion ne parle qu'à l'élève, et seulement pour
> collationner. En revanche l'effet « tout le monde entend tout le monde » d'une vraie
> fréquence partagée n'est pas reproduit, et c'est une limite pédagogique réelle que je
> reconnais : sur une vraie fréquence, l'élève construit sa conscience de la situation en
> écoutant aussi les échanges des autres.

**Q2.4. Qu'est-ce qu'un pseudo-pilote, et pourquoi vouloir le remplacer ?**

> C'est l'opérateur humain qui, en salle de simulation, joue tous les pilotes : il
> prononce les collationnements et exécute chaque instruction. Ce facteur humain domine
> le coût d'exploitation des simulateurs de formation, puisqu'il faut au moins un
> opérateur qualifié en permanence pour un élève. C'est ce qui limite mécaniquement le
> nombre d'heures d'entraînement disponibles.

**Q2.5. Pourquoi le QNH est-il traité à part dans vos fiches ?**

> Parce que c'est un calage altimétrique, c'est-à-dire une information météorologique, et
> pas un ordre de trajectoire. Un système qui l'exécuterait commettrait une faute. J'ai
> donc une fiche dédiée dont le seul contenu est : cet énoncé ne produit aucun ordre. Le
> transfert de fréquence a la même. Sur mes neuf fiches, quatre décrivent des actions et
> cinq décrivent la prononciation, les indicatifs, ce qu'il faut ignorer et la règle de
> prudence. La moitié de ma base de connaissances sert à apprendre au modèle quand ne pas
> agir.

---

## 3. Bibliographie et état de l'art

**Q3.1. Comment avez-vous constitué votre bibliographie ?**

> En semaines 1 et 2, selon quatre critères que j'énonce explicitement en tête du chapitre.
> Priorité aux travaux s'appuyant sur des données radio réelles plutôt que de laboratoire.
> Reproductibilité, donc corpus publics, poids ouverts, code disponible. Compatibilité avec
> mes contraintes matérielles : cluster aarch64, quota de 20 Go, dix semaines, exécution
> locale possible. Et actualité, 2022 à 2026, parce que le domaine évolue très vite.
> Chaque choix retenu est ensuite confronté à ses alternatives, puis validé a posteriori
> par une mesure.

**Q3.2. Pourquoi si peu de références, seize au total ?**

> Parce que j'ai cité ce qui a décidé quelque chose, pas ce qui aurait fait volume.
> Chacune des seize références est rattachée à une décision précise du projet, et je le
> montre : Zhang et Mott m'interdisent d'injecter l'état brut du trafic, AirTrafficGen me
> donne la représentation en graphe, Sharifi me sert de voie explicitement écartée, Su et
> Haq me donnent le front-end de canal et une mise en garde d'implémentation. Une
> bibliographie de quarante titres dont trente n'ont rien changé au code aurait été moins
> honnête, pas plus rigoureuse.

**Q3.3. Un article vous a-t-il servi de contre-exemple ?**

> Oui, deux. Zhang et Mott, qui montrent que les modèles de langage achoppent sur les
> longues séquences de données numériques : cela m'a proscrit d'injecter positions,
> vitesses et caps dans la consigne, et cela m'a été confirmé par ma propre mesure, où le
> modèle échoue précisément sur les contraintes d'espacement, 2 sur 9, et de cap, 6 sur 18.
> Et Sharifi, Zongo et Wei, qui affinent des modèles de langage pour la déconfliction de
> drones : j'ai sérieusement étudié cette voie puis je l'ai écartée, pour des raisons que
> j'assume et que je détaille.

**Q3.4. Vous citez des prépublications arXiv. Est-ce acceptable ?**

> Je le signale systématiquement. La règle que j'annonce en tête de bibliographie est
> que chaque travail est cité dans sa version de référence : si une version évaluée par les
> pairs existe, c'est elle qui figure, avec son DOI. Les prépublications ne sont conservées
> qu'à défaut, et elles sont marquées en gras comme telles. C'est le cas d'AirTrafficGen,
> de Su et Haq, et des rapports techniques Mistral et Qwen. Pour van Doorn, je cite le
> mémoire et la version conférence ICRAT qui, elle, a été relue.

**Q3.5. Pourquoi ATCO2, UWB-ATCC et ATCOSIM plutôt que d'autres données ?**

> J'ai examiné puis écarté trois familles. La collecte directe sur LiveATC donne du volume
> mais sans transcriptions, avec un statut juridique incertain, et faire transcrire à la
> main était hors de portée. Les corpus propriétaires des prestataires de navigation sont
> meilleurs mais inaccessibles et surtout non reproductibles par un tiers, ce qui
> interdirait à quiconque de refaire mes mesures. Les données synthétiques sont disponibles
> sans limite mais introduisent un écart sim-to-real précisément là où je cherche de la
> robustesse : un modèle entraîné sur des voix de synthèse propres apprend à reconnaître
> des voix de synthèse propres. Restait le triplet ATCO2, qui est le seul ensemble de
> corpus réels, transcrits et publics du domaine.

**Q3.6. Pourquoi réserver ATCO2 au test plutôt que de l'utiliser à l'entraînement ?**

> Parce que c'est l'audio le plus difficile du lot, capté sur des fréquences
> opérationnelles réelles, et que je voulais mesurer la généralisation et non la
> mémorisation. Ce choix est sévère envers moi-même : il me fait publier 28,5 % au lieu du
> 6,68 % que j'obtiens en validation sur le domaine d'entraînement. L'écart entre ces deux
> nombres quantifie exactement le fossé de généralisation que le protocole était conçu pour
> révéler. Un protocole moins exigeant m'aurait laissé annoncer 6,7 % et croire le problème
> résolu.

**Q3.7. Que reprochez-vous à l'état de l'art ?**

> Rien qui relève du reproche, mais deux constats. Le domaine publie beaucoup de WER et
> très peu d'architectures de sûreté : on trouve facilement comment améliorer une
> transcription, beaucoup moins ce qu'on fait de la transcription une fois qu'elle est
> fausse. Et les travaux sur les modèles de langage en aéronautique restent
> majoritairement au stade de la prépublication, ce qui impose de les lire avec prudence.
> C'est d'ailleurs pour cela que j'ai systématiquement doublé les arguments d'article par
> une mesure de mon propre banc.

---

## 4. Reconnaissance vocale, Whisper, LoRA, canal VHF

**Q4.1. Qu'est-ce que LoRA, expliqué simplement ?**

> Au lieu de réécrire le livre, on l'annote dans la marge. Les 244 millions de paramètres
> de Whisper sont gelés, aucun n'est modifié, et j'insère à côté de certaines matrices de
> poids un petit terme correctif obtenu en multipliant deux matrices très fines. Comme ces
> deux matrices sont beaucoup plus fines que l'originale, leur rang vaut ici 32, elles ne
> représentent qu'une fraction infime des paramètres tout en pouvant corriger le
> comportement dans la direction voulue. Résultat : toute l'adaptation au contrôle aérien
> tient dans 14 mégaoctets et 144 tenseurs, versionnables dans le dépôt git à côté du code.

**Q4.2. Pourquoi r = 32 et α = 64 ?**

> Le rang 32 donne une capacité d'adaptation suffisante pour un corpus de cette taille
> sans surparamétrer. Le facteur d'échelle à 64 donne un rapport alpha sur r égal à 2,
> qui est la valeur usuelle et stable. Je n'ai pas conduit de balayage systématique de ces
> deux hyperparamètres, et je préfère le dire : le budget de calcul et le quota disque ne
> le permettaient pas. Ce que je peux montrer, c'est que la configuration retenue converge
> en trois époques sans surapprentissage et produit le gain mesuré.

**Q4.3. Pourquoi q_proj et v_proj, et pas toutes les couches ?**

> Ce sont les projections d'attention, celles qui décident à chaque instant quelles parties
> du signal comptent le plus pour produire le mot suivant. C'est le placement le plus
> couramment retenu pour l'adaptation de Whisper au domaine ATC, notamment chez Su et Haq
> et chez van Doorn. Les insérer dans l'encodeur et dans le décodeur permet d'agir à la
> fois sur l'écoute du signal radio et sur la production du vocabulaire aéronautique.

**Q4.4. Pourquoi whisper-small et pas medium ou large ?**

> Compromis qualité contre coût. Le small à 244 millions de paramètres tient largement
> sur le GH200 pour l'entraînement, et son facteur temps réel mesuré est de 0,017 sur un
> GPU d'ordinateur portable, ce qui laisse une marge très confortable pour une boucle
> interactive. Les tailles supérieures auraient allongé chaque itération d'entraînement
> sans lever le goulot d'étranglement réel, qui est la quantité et la qualité des données
> du domaine. La mesure confirme le raisonnement : mon small adapté bat très largement des
> modèles génériques plus gros.

*Piège possible : « donc vous n'avez pas testé large ». Réponse : non, et je ne prétends
pas que small soit optimal ; je montre que 14 Mo d'adaptation valent mieux que plusieurs
centaines de mégaoctets de capacité générique, ce qui est un résultat différent.*

**Q4.5. Le filtre VHF, comment est-il fait et pourquoi ?**

> Un passe-bande de Butterworth d'ordre 6 entre 300 et 3 400 Hz, qui est la bande d'une
> radio aéronautique. Le gain est plat dans la bande utile et chute très vite de part et
> d'autre. L'important n'est pas le filtre lui-même mais le fait qu'il soit appliqué des
> deux côtés de la chaîne et aux deux moments : à l'entraînement du modèle de
> reconnaissance, à l'inférence, et à la voix de synthèse des pilotes. Cette cohérence de
> domaine, du corpus d'entraînement jusqu'aux oreilles de l'utilisateur, est l'une des
> rares décisions du projet que je n'ai jamais eu à remettre en cause.

**Q4.6. Filtrer, n'est-ce pas détruire de l'information ?**

> Oui, et c'est exactement ce que montre la mesure, mais dans les deux sens. Le passe-bande
> améliore le modèle adapté, de 29,7 à 28,5 % sur ATCO2 et de 101,2 à 91,9 % pour le
> générique sur UWB, et il dégrade les modèles tiny et base, qui n'ont jamais entendu de
> radio et à qui l'on retire de l'information. Filtrer aide le modèle qui a appris dans ce
> filtre et pénalise celui qui ne l'a pas appris. C'est la validation empirique de la
> cohérence de domaine, et elle n'allait pas de soi.

**Q4.7. Comment un WER peut-il dépasser 100 % ?**

> Parce que le WER compte le nombre minimal de corrections pour retrouver la référence,
> substitutions, omissions et insertions, rapporté au nombre de mots de la référence. Un
> système qui invente beaucoup de mots accumule plus d'insertions que la référence ne
> compte de mots. C'est ce qui arrive à tiny et base sur UWB-ATCC, où ils hallucinent sur
> un domaine qu'ils ne connaissent pas : 123 % et 111 %.

**Q4.8. Vous donnez 28,5 % et aussi 32,9 %. Lequel est le bon ?**

> Les deux, ce ne sont pas la même moyenne, et je l'explique explicitement pour éviter que
> les chiffres paraissent se contredire. Le WER corpus additionne toutes les erreurs et
> tous les mots de référence avant de faire le rapport ; c'est 28,5 %. Le WER moyen par
> extrait calcule un WER par enregistrement puis en prend la moyenne, ce qui pèse chaque
> extrait également quelle que soit sa durée. C'est cette seconde quantité qui se prête au
> traitement apparié extrait par extrait, donc c'est elle que je passe au bootstrap :
> l'écart est de 45,2 points, avec un intervalle de confiance à 95 % de moins 51,1 à moins
> 39,6, qui exclut zéro très largement.

**Q4.9. Vous avez deux valeurs de RTF pour le cluster, 0,04 et 0,55. Laquelle retenez-vous ?**

> 0,55, et je dis pourquoi. 0,04 est l'appel direct au modèle sur le GH200, une mesure
> ponctuelle de la semaine 8 avec n égal à 3. 0,55 est ce que mesure le banc versionné,
> c'est-à-dire la même transcription à travers la façade HTTP et le tunnel SSH. L'écart
> n'est pas dans le modèle mais dans le transport. Le second chiffre décrit le système tel
> qu'il est réellement utilisé, donc c'est celui que je retiens. C'est la même logique que
> pour Mistral : un modèle s'évalue à travers sa pile de déploiement réelle.

**Q4.10. Le gain de la LoRA est-il statistiquement établi ?**

> Oui, par bootstrap apparié sur le WER moyen par extrait, avec 10 000 rééchantillonnages
> et une graine fixée. L'intervalle de confiance à 95 % de l'écart va de moins 51,1 à
> moins 39,6 points : il exclut zéro très largement. Et le gain est retrouvé
> indépendamment trois mois plus tard, sur un autre matériel, un autre moteur d'inférence
> et un autre échantillon : 74,3 vers 29,2 % en semaine 4, 71,9 vers 28,5 % en juillet.

**Q4.11. Combien de temps a duré l'entraînement de la LoRA ?**

> Trois époques sur UWB-ATCC et ATCOSIM avec un lot de 48, sur le nœud GH200. Le point
> notable n'est pas la durée mais ce qu'il a fallu contourner pour y arriver : un
> inter-blocage du chargeur de données, un conflit de formats numériques bf16 et fp32 à la
> génération, un quota disque dépassé par la duplication de la table audio, et des
> gradients non propagés. Les quatre sont documentés dans le tableau des problèmes avec
> leur cause racine et leur preuve de résolution.

**Q4.12. Auriez-vous pu utiliser une API commerciale de transcription ?**

> Techniquement oui, et le résultat aurait peut-être été meilleur. Mais trois points
> étaient rédhibitoires pour un simulateur de formation : cela interdit l'adaptation au
> domaine, cela impose une dépendance réseau permanente au poste de formation, et cela
> fait sortir les données de l'établissement. Le système doit pouvoir fonctionner hors
> ligne.

---

## 5. Interprétation, modèle de langage, ancrage, gardes

**Q5.1. Qu'est-ce que l'ancrage, ou RAG, en une phrase ?**

> C'est l'examen à livre ouvert : au lieu d'apprendre le manuel au modèle, on le lui met
> devant les yeux au moment où il répond. Je tiens à côté du modèle une base de neuf
> fiches, je sélectionne les pertinentes à chaque clairance et je les recopie dans la
> consigne.

**Q5.2. Comment sélectionnez-vous les fiches ?**

> Par embeddings, avec le modèle bge-small-en-v1.5 : chaque phrase devient une liste de
> nombres construite de telle sorte que deux phrases de sens proche donnent deux listes
> proches, et je mesure la similarité cosinus. Le calcul est en NumPy pur. Sur une base de
> neuf documents, un index spécialisé comme FAISS aurait ajouté une dépendance lourde sans
> le moindre bénéfice mesurable. C'est un cas où il fallait résister à la tentation
> d'employer l'outil de la littérature.

*Piège possible : « neuf documents, ce n'est pas du RAG ». Réponse : c'est exactement le
mécanisme du RAG, sélection puis injection dans la consigne ; ce qui change avec l'échelle,
c'est la structure d'index, pas le principe, et je le dis.*

**Q5.3. Neuf fiches, n'est-ce pas ridiculement peu ?**

> C'est peu, et c'est délibéré. Le jeu d'actions est fermé, quatre valeurs : HDG, ALT, SPD
> et ADDWPT. Quatre fiches décrivent ces actions, cinq décrivent la prononciation des
> nombres, les indicatifs, le QNH, le transfert de fréquence et la règle de prudence
> générale. Ajouter des fiches sans élargir le jeu d'actions n'aurait rien apporté. Et
> l'ensemble pèse environ 2,5 kilooctets, ce qui laisse toute la place à la clairance dans
> la fenêtre de contexte.

**Q5.4. Pourquoi ne pas avoir utilisé le Doc 4444 directement ?**

> Parce qu'il est protégé par le droit d'auteur, ce qui m'interdit de l'ingérer et de le
> citer verbatim dans une base de connaissances versionnée publiquement. C'est une
> contrainte juridique qui a eu une conséquence technique directe : j'ai dû rédiger une
> base originale de neuf fiches synthétisant les règles avec mes propres mots, en y
> intégrant les bornes déjà codées de mon connecteur. Je cite le Doc 4444 comme source
> normative, je ne le reproduis nulle part.

**Q5.5. Que valide exactement votre couche déterministe ?**

> Trois filtres successifs, puis deux gardes applicatives. D'abord une coercition stricte
> de type, qui rejette les booléens, les valeurs non numériques, les infinis et les chaînes
> déguisées en nombres. Ensuite les bornes physiques : cap de 0 à 360 degrés, altitude de
> 0 à 45 000 pieds, vitesse de 0 à 350 nœuds, et l'appartenance de l'action au jeu autorisé.
> Puis l'existence du point de cheminement dans le graphe de secteur. Les deux gardes
> applicatives sont l'indicatif absent du radar, qui produit un silence radio et non une
> erreur, et l'incohérence entre le verbe et le sens du changement de niveau.

**Q5.6. Le silence radio plutôt qu'un message d'erreur, pourquoi ?**

> Parce que c'est le comportement réaliste : sur une vraie fréquence, un avion qui n'existe
> pas ne répond pas. Un message d'erreur apprendrait à l'élève à compter sur un retour que
> la réalité ne lui donnera jamais.

**Q5.7. Vos gardes ne font-elles pas double emploi avec le modèle ?**

> Non, et c'est tout l'argument. Le modèle est probabiliste : il propose une interprétation
> plausible. Le code est déterministe : il vérifie une propriété. Les deux ne font pas la
> même chose. La preuve chiffrée est que sur 1 871 ordres proposés, 810 sont rejetés, dont
> 636 pour le seul Llama-1B, et que la garantie finale ne dépend d'aucun taux de qualité de
> modèle.

**Q5.8. Pourquoi Mistral-7B plutôt que Qwen2.5-1.5B, qui est presque aussi bon et trois fois plus rapide ?**

> C'est la question la plus juste qu'on puisse me poser sur ce tableau, et je la pose
> moi-même dans le rapport. L'écart de 6,9 points entre les deux n'est pas
> statistiquement significatif : McNemar donne n01 égal à 16, n10 égal à 8, p égal à 0,152.
> Je ne peux donc pas démontrer sur 116 cas que le modèle de sept milliards interprète
> mieux que celui de un milliard et demi. Ce que je peux dire, c'est que Mistral produit
> 100 % de JSON strictement valide contre 96,6 %, et surtout qu'il est le seul des deux à
> battre l'analyseur à règles hors grammaire, 77,1 % contre 68,8 %, c'est-à-dire sur le
> seul terrain qui justifie d'employer un modèle de langage. Sur un corpus plus grand, la
> question mériterait d'être rouverte.

**Q5.9. Votre parseur à règles fait 87,9 %, mieux que le LLM à 81,9 %. Pourquoi garder le LLM ?**

> Piège classique, et la réponse est dans les tests appariés. Les six points d'écart ne
> sont pas significatifs : n01 égal à 19, n10 égal à 12, p égal à 0,281. Sur 116 cas, six
> points, c'est du bruit d'échantillonnage. La vraie différence est structurelle : le
> parseur est parfait dans sa grammaire fermée, 100 %, et s'effondre dès qu'on en sort,
> 70,8 %. Le modèle est légèrement moins bon dedans, 85,3 %, et meilleur dehors, 77,1 %.
> Sur la strate des paraphrases, le parseur tombe à 36 % quand Mistral atteint 91 %.
> Aucun des deux ne domine partout, et c'est pour cela que je garde les deux : le parseur
> comme référence et comme oracle de test, le modèle en production.

**Q5.10. Pourquoi Qwen2.5-3B est-il pire que Qwen2.5-1.5B ?**

> C'est le résultat le plus contre-intuitif du banc, 24,1 % contre 75,0 % pour un modèle
> deux fois plus petit. J'ai testé deux hypothèses. La première, qu'il ignore le message
> système comme Mistral : écartée, j'ai vérifié directement qu'il l'honore. La seconde,
> un fichier de poids défectueux : pour la trancher, avant de publier un résultat aussi
> sévère contre un modèle très diffusé, j'ai ré-évalué une seconde quantification produite
> indépendamment par un autre contributeur. Elle donne 23,3 %, statistiquement
> indiscernable de la première, McNemar à p égal à 1,0. Ce qu'il fait, c'est violer le
> schéma : champ callsign omis, clés JSON sans guillemets. C'est le modèle qui est inadapté
> à la tâche contrainte, pas le fichier.

**Q5.11. Pourquoi la température à 0 ?**

> Pour supprimer tout tirage aléatoire dans le choix des mots, ce qui rend chaque mesure
> exactement reproductible. Dans une tâche de production structurée sous contrainte, la
> créativité n'a aucune valeur : je veux le même JSON pour la même clairance, toujours.

**Q5.12. Qu'est-ce que l'exactitude stricte, et n'est-elle pas trop sévère ?**

> Un cas est réussi si et seulement si l'ensemble des ordres produits est exactement celui
> attendu. Un ordre correct accompagné d'un ordre superflu compte comme un échec, au même
> titre qu'une erreur franche. C'est volontairement impitoyable, parce que dans un
> simulateur d'entraînement un ordre en trop est aussi dommageable qu'un ordre faux. Mes
> pourcentages sont donc plus bas que ce qu'une métrique indulgente aurait produit, et je
> le signale pour que personne ne les compare à des chiffres obtenus autrement.

**Q5.13. Comment avez-vous constitué votre corpus de 116 clairances ?**

> Je l'ai annoté à la main avec le TrafScript attendu après validation, et je l'ai
> stratifié à dessein. 68 cas relèvent de la grammaire du parseur qui sert de référence,
> et 48 cas étendus couvrent des paraphrases hors grammaire, du bruit de type
> reconnaissance vocale avec hésitations et répétitions, du français parlé, des nombres
> composés, des clairances portant plusieurs ordres, et des cas mixtes associant un ordre
> valide et un ordre invalide dans la même phrase. Au total 24 cas sont des négatifs de
> sécurité : des énoncés qui ne doivent produire aucun ordre.

*Piège possible : « vous avez annoté vous-même, donc juge et partie ». Réponse préparée
en Q14.4.*

**Q5.14. Combien coûte la quantification 4 bits ?**

> 1,7 point d'exactitude. C'est le seul modèle que j'aie servi dans les deux conditions :
> 83,6 % en pleine précision sur ROMEO contre 81,9 % en Q4_K_M en local, et 98,3 % de JSON
> strictement valide contre 100 %. Pour un fichier divisé par quatre et une latence divisée
> par 2,4. C'est un compromis que je referais sans hésiter, et surtout c'est ce qui valide
> l'hypothèse implicite de toute ma campagne locale : les chiffres obtenus sur une carte
> graphique de portable décrivent bien le système déployé sur le cluster.

**Q5.15. Votre système comprend-il le français ?**

> Oui, et cela vient d'un défaut que ma propre campagne a révélé. À la première passe, le
> parseur donnait 92,6 % en global, ce qui paraissait honorable, mais 1 sur 6 seulement
> sur la strate française. La cause : le découpage entre indicatif et instruction
> s'appuyait sur une liste de mots déclencheurs uniquement anglais, si bien qu'une phrase
> entièrement française était ignorée sans aucun message. C'est le pire mode de
> défaillance : pas d'erreur, pas de trace, juste un ordre qui n'arrive jamais. J'ai
> ajouté les verbes français et étendu les grammaires, niveau de vol, cap, vitesse, et le
> résultat est passé à 68 sur 68.

---

## 6. Géométrie, simulateur, exercices

**Q6.1. Comment calculez-vous le CPA ?**

> Par une formule fermée. Deux avions en mouvement rectiligne uniforme voient le carré de
> leur distance décrire une parabole en fonction du temps. Le coefficient dominant est la
> norme au carré de la vitesse relative, strictement positive, donc la parabole est
> strictement convexe et n'a qu'un seul creux. L'instant du rapprochement maximal vaut
> moins le produit scalaire de la position relative initiale par la vitesse relative,
> divisé par la norme au carré de cette vitesse. C'est le minimum global unique, sans
> simulation.

**Q6.2. Comment avez-vous vérifié cette formule ?**

> À trois niveaux et par trois moyens indépendants. Contre une vérité numérique : balayage
> du temps par pas de 0,05 seconde sur un horizon de 300 secondes, appliqué à un million de
> géométries tirées au hasard, cinq graines de 200 000 cas. La décision de conflit coïncide
> dans tous les cas : zéro désaccord sur un million. Contre BlueSky : 200 rencontres
> stabilisées, erreur moyenne de 0,067 NM sur la distance au CPA et 0,71 s sur son instant,
> et surtout une matrice de confusion parfaite, 113 vrais positifs, 87 vrais négatifs,
> aucun faux positif, aucun faux négatif. Et sur le générateur d'exercices : 2 000 tirages
> seedés, garantie de conflit vérifiée à 100 %, distance au CPA maximale de 0,082 NM.

**Q6.3. Que signifie F1 égal à 1,0 ?**

> La précision est la proportion d'alertes qui étaient justifiées, le rappel la proportion
> de conflits réels effectivement signalés, et F1 les combine en un nombre qui ne vaut 1
> que si les deux valent 1. Ici les trois valent exactement 1 : aucun conflit manqué,
> aucune fausse alerte, sur les 113 conflits réels de l'échantillon. Un système qui
> alerterait tout le temps aurait un rappel parfait et une précision déplorable ; un
> système muet ferait l'inverse.

**Q6.4. F1 égal à 1,0, n'est-ce pas suspect ?**

> C'est une question légitime et j'y réponds franchement : ce n'est pas de la détection
> parfaite en trafic réel, c'est un accord parfait avec le simulateur de référence sur le
> protocole défini. Deux conditions le rendent atteignable : les aéronefs de BlueSky sont
> stabilisés, donc l'hypothèse de mouvement rectiligne uniforme est vraie, et l'horizon de
> prédiction est de 120 secondes, ce qui est court. Le résultat valide l'hypothèse
> cinématique sur cet horizon, il ne dit rien de trajectoires en virage ou en évolution.
> Je l'écris tel quel.

**Q6.5. Pourquoi ne pas tenir compte du vent ?**

> L'application transmet bien la vitesse sol et la route, donc le vent est présent dans le
> trafic. Mais la campagne de validation géométrique est menée à vent nul, et je le
> signale dans les limites. C'est une simplification assumée du protocole de validation,
> pas une incapacité du système.

**Q6.6. Pourquoi BlueSky ?**

> C'est le simulateur open source de référence de la recherche en gestion du trafic aérien,
> développé à Delft. J'ai écarté les simulateurs commerciaux fermés pour inaccessibilité,
> les plateformes de type Euroscope pour inadaptation au pilotage programmatique, et un
> moteur maison pour coût manifestement hors de portée. BlueSky offre exactement ce dont ma
> boucle a besoin : mode headless sans interface, pilotage par commandes texte en
> TrafScript, modèles de performances avion réalistes, détection de conflits native, et une
> base de code Python inspectable. Ce dernier point s'est révélé indispensable le jour où
> j'ai découvert qu'un de mes tests portait sur un objet mandataire.

**Q6.7. Le simulateur tient-il la charge ?**

> Oui, et il n'est jamais le facteur limitant. Simuler une seconde de trafic coûte 9,5
> millisecondes de calcul avec 5 aéronefs et encore seulement 15 millisecondes avec 200,
> soit 67 fois plus vite que l'horloge. Rapporté aux 2,6 secondes de la boucle vocale, le
> budget de latence est entièrement consommé par les trois étages d'IA.

**Q6.8. Comment garantissez-vous qu'un exercice contient bien un conflit ?**

> Par construction et non par tirage. Je fabrique des paires convergentes dont les
> distances et les vitesses sont choisies pour que les deux appareils arrivent au même
> instant au même point, ce qui rend la distance au CPA théoriquement nulle. Sur 2 000
> tirages seedés, la garantie tient à 100 %, la pire distance observée étant de 0,082 NM,
> très loin en deçà des 5 NM de la norme de séparation.

**Q6.9. Comment est construit le barème de notation ?**

> Sur 100 points, avec la séparation qui en pèse la moitié parce que c'est la mission
> primaire du contrôleur : 50 points, moins 25 par perte de séparation et 0,5 par seconde
> cumulée sous la norme. Puis 20 points d'anticipation, la proportion des conflits prédits
> résolus avant la perte de séparation. 15 points d'évitement de zones. Et 15 points de
> qualité de phraséologie, mesurée par la proportion de clairances acceptées par la chaîne
> d'interprétation. Le barème est documenté dans le dépôt et figé par des tests.

**Q6.10. Ce barème a-t-il été validé par un contrôleur ?**

> Non, et c'est une limite que je ne cherche pas à masquer. C'est une proposition
> raisonnée, calquée sur la hiérarchie des priorités du métier, mais elle n'a été validée
> par aucun instructeur. Elle relève de la même lacune que l'absence de validation
> pédagogique globale.

**Q6.11. Votre secteur n'a que sept points. N'est-ce pas trop simple ?**

> Oui, et c'est écrit dans les limites : secteur unique et fictif, centré sur Reims, sept
> points, sans procédures de départ et d'arrivée normalisées, sans trajectoire
> quadridimensionnelle. Ce n'est pas une limite du principe mais du périmètre. Le graphe
> est une structure de données ; en ajouter des points ne change ni le validateur ni la
> chaîne d'interprétation. Ce qui changerait, c'est le volume de contexte à donner au
> modèle, et c'est précisément le terrain sur lequel Zhang et Mott annoncent la faiblesse
> des modèles de langage.

**Q6.12. Pourquoi la « double pénalité » du barème n'est-elle pas un bug ?**

> Parce que ce sont deux compétences distinctes. Perdre la séparation coûte des points sur
> la compétence séparation ; n'avoir pas anticipé le conflit en coûte sur la compétence
> anticipation. C'est voulu et documenté. C'est un constat qu'on m'avait signalé comme un
> bug et que j'ai reclassé en comportement voulu après vérification, puis figé par un test
> précisément pour que personne, moi compris, ne le corrige plus tard. Savoir dire d'un
> constat qu'il est faux est une compétence aussi utile que savoir en trouver.

---

## 7. Synthèse vocale

**Q7.1. Comment évalue-t-on objectivement une voix de synthèse ?**

> La qualité perçue est subjective et je n'avais ni le temps ni le panel pour une
> évaluation humaine sérieuse. J'ai donc construit une mesure objective et automatisable :
> l'intelligibilité aller-retour. Le texte est synthétisé, puis re-transcrit par un système
> de reconnaissance fixe qui joue le rôle d'auditeur, et je mesure le WER entre le texte de
> départ et le texte retrouvé. Si la voix est claire, l'auditeur retrouve le texte.
> J'insiste sur un point : cette métrique est relative, biaisée par son juge, et seuls les
> écarts entre lignes sont interprétables.

**Q7.2. Vous aviez annoncé 22 à 24 % pour XTTS pendant tout le stage, et vous publiez 65 à 92 %. Que s'est-il passé ?**

> C'est mon résultat négatif le plus net, et je le raconte plutôt que de le lisser. Le
> chiffre de 22 à 24 % venait d'une métrique maison, mesurée en semaine 6 sur trois
> exemples, avant l'existence du banc. Quand j'ai fait passer les mêmes voix clonées dans
> le banc final, avec le même juge et la même normalisation que Kokoro, le verdict a été
> tout autre : entre 64,9 et 92,0 % de WER aller-retour selon la voix, soit trois à quatre
> fois pire que Kokoro. Les deux chiffres ne sont pas comparables, et c'est le second qui
> vaut.

**Q7.3. Pourquoi les voix clonées sont-elles si mauvaises ?**

> Parce que je les ai clonées à partir d'extraits du corpus ATCO2, c'est-à-dire de l'audio
> radio déjà dégradé. Le clonage zero-shot reproduit fidèlement ce qu'on lui donne, y
> compris la dégradation. Les voix clonées sonnent authentiques et sont difficilement
> intelligibles. La conclusion à en tirer n'est pas d'abandonner le clonage, mais de le
> nourrir avec des extraits de référence propres, puis de laisser le canal VHF simulé faire
> son travail en aval, exactement comme il le fait déjà pour Kokoro.

**Q7.4. Combien coûte votre dégradation VHF en intelligibilité ?**

> Rien de mesurable, et c'est le résultat que je cherchais. Kokoro passe de 22,0 % de WER
> avant le canal à 21,4 % après. L'écart est même très légèrement favorable au signal
> filtré, ce qui est du bruit de mesure et non un effet réel. On peut donc avoir le
> réalisme radio sans perte pédagogique.

**Q7.5. Pourquoi ne pas utiliser SAPI, qui est le plus rapide et le plus intelligible ?**

> SAPI est effectivement le meilleur sur ces deux critères, RTF de 0,003 et 16 % de WER,
> et je le garde d'ailleurs comme fournisseur possible. Mais il ne donne pas une voix
> distincte et stable par aéronef, qui était mon cahier des charges : dans un exercice,
> l'élève doit pouvoir associer une voix à un avion, comme sur une vraie fréquence. Kokoro
> offre quatre voix affectées par hachage CRC32, ce qui garantit qu'un même indicatif
> reçoit toujours la même voix sans avoir à mémoriser quoi que ce soit. Et SAPI dépend de
> Windows.

**Q7.6. Pourquoi la synthèse sur le cluster est-elle si lente, 5,5 s ?**

> Parce qu'elle est confinée au processeur. L'encodeur de locuteur de XTTS plante
> systématiquement sur le GPU du GH200, un bug de la bibliothèque de traitement audio dans
> la routine de transformée de Fourier, propre à l'architecture Grace-Hopper, que je ne
> pouvais pas corriger moi-même. J'ai basculé sur CPU, ce qui donne 3,9 s par
> collationnement, soit un facteur temps réel de 0,82, et j'ai assumé et documenté ce
> compromis. C'est pour cela que je n'ai aucune configuration réunissant simultanément les
> voix clonées et le temps réel.

**Q7.7. « Votre spectrogramme ne prouve pas la dégradation de la voix. Il montre comment vous avez filtré les données pour entraîner Whisper. »**

*C'est exact, et c'est la question la plus fine qu'on puisse poser sur cette diapositive.
Ne cherchez pas à la contourner : reconnaissez-la en une phrase, puis servez-vous-en.*

> Vous avez raison, et je vais même plus loin que votre remarque. Cette figure ne montre ni
> la voix de synthèse, ni un extrait de corpus : le signal est une parole *synthétique*
> fabriquée par le script, à graine fixée et bruitée à 10 dB, précisément pour isoler
> l'effet du filtre sans que rien d'autre ne varie. C'est la preuve de la semaine 2 sur le
> pré-traitement, dans `src/01_audio_preprocessing.py`. Autrement dit, ce n'est pas
> une mesure, c'est la démonstration d'un filtre, et je ne lui fais pas dire davantage.
>
> Ce que la figure établit, c'est ce que fait un Butterworth d'ordre 6 entre 300 et
> 3 400 Hz à un signal de parole : au-dessus de 3 400 Hz, il ne reste rien. Et c'est
> pertinent pour la voix de synthèse comme pour l'audio d'entrée, parce que c'est
> littéralement le même filtre, appliqué à trois endroits : à l'entraînement du modèle de
> reconnaissance, à l'inférence, et à la voix des pilotes. Un seul et même traitement, du
> corpus d'entraînement jusqu'aux oreilles de l'élève. C'est ce que j'appelle la cohérence
> de domaine, et c'est l'une des rares décisions du projet que je n'ai jamais eu à remettre
> en cause.

> Si vous voulez la preuve que ce choix est le bon, elle n'est pas dans le spectrogramme,
> elle est dans le tableau des WER. Le passe-bande améliore le modèle adapté, de 29,7 à
> 28,5 % sur ATCO2 et de 101,2 à 91,9 % pour le générique sur UWB, et il dégrade les
> modèles tiny et base, qui n'ont jamais entendu de radio et à qui l'on retire de
> l'information. Filtrer aide le modèle qui a appris dans ce filtre et pénalise celui qui ne
> l'a pas appris. Le spectrogramme illustre le filtre ; c'est la mesure qui le justifie.

> Et côté voix produite, la preuve de dégradation n'est pas visuelle non plus, elle est
> mesurée : l'intelligibilité aller-retour de Kokoro passe de 22,0 % de WER avant le canal
> à 21,4 % après. Autrement dit, la coloration radio ne coûte rien de mesurable en
> intelligibilité. C'est le résultat que je cherchais, et c'est le seul qui prouve quoi que
> ce soit sur la voix de synthèse.

*Si on insiste sur l'illustration elle-même, ne défendez pas l'indéfendable : « sur cette
diapositive, la figure aurait gagné à être produite à partir d'un collationnement Kokoro
réel plutôt que d'un signal de test. C'est une maladresse d'illustration, pas une erreur de
raisonnement : le filtre, ses bornes et son ordre sont exactement les mêmes des deux
côtés. » Puis enchaînez immédiatement sur les deux mesures ci-dessus, qui sont les seules
preuves du dossier.*

*Renvoi : rapport §2.2, figure du spectrogramme et paragraphe « Le canal radio, reproduit
puis appris » ; §5.3 pour la mesure du filtre ; §5.5 pour l'intelligibilité.*

### La formule courte, si vous n'avez que quinze secondes

> Un seul filtre, deux rôles. Côté entrée, il aligne le domaine d'apprentissage sur le
> domaine de production. Côté sortie, il fabrique le réalisme radio. C'est le même
> Butterworth d'ordre 6, aux mêmes bornes, et c'est précisément cette symétrie qui rend la
> mesure honnête.

### Trois mots à ne pas employer sur ce sujet

**« Réversible ».** Un passe-bande n'est pas inversible. Tout ce qui sort de la bande
300-3 400 Hz est détruit, pas atténué, et rien ne le récupère ; le panneau droit du
spectrogramme est noir au-dessus de 3 400 Hz, c'est visible à l'œil. Le mot juste pour
l'idée que vous voulez exprimer est **symétrique** : le même filtre des deux côtés, donc
l'écart de domaine s'annule. Dire « réversible » devant quelqu'un qui a fait du traitement
du signal vous coûtera le crédit de toute la réponse.

**« Le filtre améliore et dégrade la voix ».** Formulé ainsi, c'est un paradoxe, et on vous
demandera de choisir. Le filtre ne fait qu'une chose, toujours la même : il retire ce qui
sort de la bande, ce qui est une perte d'information dans tous les cas. Ce qui change,
c'est à qui on l'applique. La formulation qui tient debout, et elle est dans le rapport :
**filtrer aide le modèle qui a appris dans ce filtre et pénalise celui qui ne l'a pas
appris.** 29,7 vers 28,5 % pour le modèle adapté, contre une dégradation pour tiny et base.

**« J'ai amélioré les données d'entraînement ».** Vous ne les avez pas améliorées, vous les
avez **alignées** sur la condition de production. Sinon la question suivante est
« améliorées en quel sens, puisque vous en avez retiré de l'information ? ».

**Q7.8. « ×3 temps réel, par rapport à quoi ? »**

> Trois fois plus vite que l'horloge : produire une seconde de voix coûte environ un tiers
> de seconde de calcul. Le chiffre exact du banc est un facteur temps réel de 0,336, moyenné
> sur les quatre voix de Kokoro, sur un GPU d'ordinateur portable. Dans la boucle complète,
> la synthèse représente 1,15 seconde sur les 2,6 secondes totales, c'est donc le poste le
> plus coûteux après l'interprétation.

---

## 8. La boucle complète et la contre-épreuve humaine

**Q8.1. Décrivez le protocole de bout en bout.**

> 25 clairances. Chaque énoncé contrôleur est synthétisé avec une voix jamais utilisée
> ailleurs dans le banc, pour éviter toute complaisance, puis passé dans un canal radio
> simulé, bruit à 12 dB de rapport signal sur bruit puis passe-bande VHF. La chaîne
> complète prend ensuite le relais : transcription par mon Whisper adapté, interprétation
> par Mistral-7B, validation déterministe, exécution dans le simulateur, collationnement
> en Kokoro dégradé VHF. Une condition témoin en texte, sur les mêmes clairances mais sans
> l'étage de reconnaissance vocale, isole exactement le coût de la voix.

**Q8.2. Que mesure l'écart de 12 points entre voix et texte ?**

> Le coût résiduel de la reconnaissance vocale : 76 % en voix contre 88 % en texte. C'est
> le prix à payer, aujourd'hui, pour parler plutôt qu'écrire. Sur les six échecs de la
> condition vocale, trois sont attribués à la transcription et trois à l'interprétation,
> zéro au fournisseur.

**Q8.3. 25 essais, c'est très peu.**

> Oui, et c'est pourquoi je donne systématiquement l'intervalle de confiance : 76 % avec
> un intervalle de Wilson de 56,6 à 88,5. La fourchette est large, c'est le prix d'un
> petit échantillon, et je l'affiche pour ne pas suggérer une précision que je n'ai pas.
> Ce que ces 25 cas permettent, en revanche, c'est de la comparaison appariée : comme
> toutes mes conditions portent sur exactement les mêmes clairances, les tests de McNemar
> exploitent l'appariement et sont bien plus informatifs que les moyennes.

**Q8.4. Parlez de la contre-épreuve humaine.**

> La limite évidente du protocole précédent est que le contrôleur y est une voix de
> synthèse. J'ai donc enregistré moi-même les 25 clairances au micro, via la capture du
> navigateur, c'est-à-dire par le chemin exact du push-to-talk, en phraséologie parlée,
> indicatifs en téléphonie et chiffres épelés. Résultat : 20 sur 25, soit 80 %, en
> condition micro, pour 2,3 s de latence, et 18 sur 25, soit 72 %, une fois les prises
> dégradées par le canal radio. Comme les clairances sont exactement les mêmes, la
> comparaison est appariée : McNemar donne p égal à 1,0 dans les deux conditions face à la
> voix de synthèse. Les deux protocoles sont indiscernables, et le remplacement de la voix
> synthétique par un locuteur humain ne dégrade pas la chaîne.

**Q8.5. Un seul locuteur, vous-même. C'est une validation ?**

> C'est une borne, pas une validation, et je l'écris ainsi. Un seul locuteur, en lecture
> et non en parole spontanée, sans la phraséologie fluide et parfois relâchée d'un
> professionnel. Ce que cela lève, c'est le doute sur le caractère artificiel de la voix
> d'entrée. Ce que cela ne lève pas, c'est le doute sur la variabilité inter-locuteurs.
> L'élargissement à plusieurs locuteurs, idéalement des élèves contrôleurs, est ma
> deuxième perspective.

**Q8.6. Quel est le défaut le plus intéressant révélé par cette contre-épreuve ?**

> Deux, et ils ne disent pas la même chose. Le premier : « reduce speed two five zero » a
> été entendu « speed to five zero », ce qui produit un ordre à 50 nœuds. C'est absurde
> pour un avion de ligne, mais parfaitement à l'intérieur de mes bornes physiques, donc
> non filtré. C'est un cas d'école : la validation par bornes ne protège que contre
> l'impossible, pas contre l'implausible. Il faudrait pour cela une garde tenant compte du
> type d'aéronef. Le second : l'indicatif CSA1DZ est parfaitement transcrit, WER nul, et
> mal réassemblé par le modèle en CSAD12Z. Ce défaut se manifeste exactement de la même
> façon avec la voix synthétique, donc il est indépendant du locuteur et ne relève ni de
> la reconnaissance vocale ni du bruit.

**Q8.7. Pourquoi votre voix réussit-elle là où la synthèse échouait ?**

> Sur les indicatifs EZY21 et BAW57, parce qu'un humain qui connaît la phraséologie
> prononce mieux qu'un système de synthèse qui lit des caractères. À l'inverse
> « ryanair » est systématiquement déformé par la transcription de ma voix, entendu
> « win air ». Les erreurs ne sont pas les mêmes, mais leur nombre l'est, ce que confirme
> le p égal à 1,0.

**Q8.8. 2,6 secondes, est-ce utilisable ?**

> C'est compatible avec le rythme d'une fréquence d'entraînement, où un échange intervient
> toutes les dix à trente secondes. Mais c'est nettement supérieur au temps de réaction
> d'un pseudo-pilote humain, qui répond en une seconde environ, et je le compte comme une
> limite. Le risque que je signale est qu'un élève habitué au système s'accoutume à un
> rythme d'échange qui n'est pas celui d'une vraie fréquence, et cette dérive-là, mon banc
> ne sait pas la mesurer.

**Q8.9. Où passent les 2,6 secondes ?**

> 0,36 s de transcription, 1,06 s d'interprétation, 1,15 s de synthèse vocale, avec un p95
> à 3,2 s. La simulation n'y figure pas parce qu'elle est négligeable, 15 millisecondes par
> seconde de trafic. Le budget est donc entièrement consommé par les trois étages d'IA, et
> les deux postes coûteux sont l'interprétation et la synthèse.

**Q8.10. Et sur le cluster, pourquoi 9 secondes ?**

> 2,06 s de transcription, 1,46 s d'interprétation, 5,52 s de synthèse, p95 à 13,6 s.
> L'écart tient à l'aller-retour réseau à travers le tunnel SSH et à la file d'attente
> d'une machine partagée, plus au fait que la synthèse XTTS est confinée au processeur.
> Il ne tient pas aux modèles : le résultat fonctionnel est identique aux mêmes six cas
> près.

---

## 9. Statistiques et méthodologie de mesure

**Q9.1. Pourquoi Wilson plutôt que l'intervalle normal ?**

> Parce que l'intervalle normal est faux sur de petits effectifs et près des bornes : il
> peut donner des bornes négatives ou supérieures à 1. Wilson reste correct sur 25 essais,
> ce qui est exactement mon cas. Pour les moyennes, où Wilson ne s'applique pas, j'emploie
> le bootstrap.

**Q9.2. Qu'est-ce que le bootstrap, en une phrase ?**

> Puisque je ne peux pas refaire l'expérience mille fois, je rejoue mille fois le tirage
> de l'échantillon lui-même, en piochant au hasard avec remise parmi mes résultats
> existants ; la dispersion des valeurs obtenues estime celle qu'aurait donnée une
> répétition réelle. J'emploie 10 000 rééchantillonnages avec une graine fixée.

**Q9.3. Pourquoi McNemar plutôt qu'un test du khi-deux ou un test de Student ?**

> Parce que mes systèmes sont évalués sur exactement les mêmes clairances, et qu'un test
> non apparié gaspille cette information. McNemar regarde uniquement les cas de désaccord :
> ceux où le premier réussit et le second échoue, et inversement. Si les deux comptes sont
> proches, l'écart global n'est probablement qu'un effet du hasard. C'est ce qui me permet
> d'affirmer qu'une différence de six points entre le parseur et Mistral n'est pas
> significative, conclusion que la simple lecture des pourcentages aurait manquée.

**Q9.4. Pourquoi la correction de Holm sur le test full-duplex ?**

> Parce que je fais quatre comparaisons sur les mêmes données, une par condition, et que
> multiplier les tests augmente mécaniquement le risque de trouver un écart significatif
> par hasard. Holm ajuste les seuils en conséquence. Après correction, les quatre p sont
> entre 0,001 et 0,008, donc l'écart tient.

**Q9.5. Pourquoi donner le p95 et pas seulement la moyenne ?**

> Parce que la moyenne dit ce qui se passe d'habitude et le p95 dit ce qui se passe dans
> les mauvais cas. Pour une boucle de dialogue, c'est le second qui détermine le confort
> ressenti : un système à 2,6 s de moyenne mais 8 s de p95 serait pénible à utiliser. Le
> mien reste à 3,2 s.

**Q9.6. Vos chiffres sont-ils reproductibles ?**

> Trois dispositifs. Une ré-exécution intégrale conduite le 3 juillet : toutes les
> métriques sont identiques champ à champ aux fichiers JSON versionnés, seules les durées
> d'exécution différant. Des portes de non-régression portant sur les métriques elles-mêmes
> et non sur la simple absence d'erreur, si bien qu'une chute du F1 fait désormais échouer
> l'exécution. Et le versionnement intégral : scripts, corpus annotés, graines, fichiers de
> résultats et code de génération des figures, avec 209 tests unitaires en intégration
> continue. Aucun chiffre du rapport n'est saisi à la main, tous sont générés depuis les
> fichiers de résultats.

**Q9.7. Pourquoi mesurer à travers le code de production plutôt que sur un banc isolé ?**

> Parce que l'épisode Mistral m'a montré ce que coûte l'inverse. Le même poids, la même
> quantification et la même consigne donnaient 21 % ou 82 % selon un détail
> d'implémentation du moteur de service, situé à trois couches de distance du modèle. Si
> j'avais publié la première mesure, j'aurais conclu de bonne foi, avec des chiffres
> exacts, que Mistral est inapte à la tâche. Un modèle s'évalue à travers sa pile de
> déploiement réelle, jamais isolément. C'est l'un des enseignements majeurs du stage.

**Q9.8. Vous publiez des pourcentages intermédiaires non parfaits. Pourquoi ?**

> Je ne les publie pas comme des résultats, je les traite comme des détecteurs de défauts.
> Le 92,6 % en global cachait 1 sur 6 sur la strate française. Un autre taux intermédiaire
> cachait une expression régulière qui ne reconnaissait pas le code B744, avec un repli
> silencieux sur l'A320. Dans les deux cas, j'ai cherché ce qui se tenait derrière les
> points manquants, corrigé, puis revalidé par la même campagne : 68 sur 68 pour le
> premier, 18 sur 18 pour le second. Une mesure qui ne sert qu'à remplir un tableau est une
> mesure gâchée.

---

## 10. Calcul haute performance, le terrain du jury

**Q10.1. Décrivez le nœud sur lequel vous avez travaillé.**

> Un NVIDIA GH200, dit Grace-Hopper : un processeur d'architecture ARM en aarch64
> étroitement associé à un accélérateur Hopper, avec 96 Go de mémoire unifiée que les deux
> se partagent. C'est excellent pour l'IA, où l'on déplace sans cesse de grandes quantités
> de nombres entre processeur et accélérateur, puisque la mémoire unifiée supprime une
> grande partie de ces copies. C'est aussi suffisamment inhabituel pour que des
> bibliothèques éprouvées ailleurs y révèlent des bugs qui n'existent nulle part ailleurs,
> et j'en donne trois exemples vécus.

**Q10.2. Comment avez-vous exploité les 96 Go de mémoire unifiée ?**

> Directement, par la taille de lot : 48 à l'entraînement, ce qui serait hors de portée
> d'une carte de 8 Go. Et indirectement, en servant les trois modèles, Whisper, Mistral et
> XTTS, dans un unique processus. Ce dernier point est né d'une contrainte, le quota disque
> qui m'interdisait une seconde installation complète de PyTorch, et il a eu un bénéfice
> collatéral que je n'avais pas anticipé : le déploiement sur le cluster s'en est trouvé
> considérablement simplifié.

**Q10.3. Comment le quota de 20 Go a-t-il changé votre code ?**

> Ma première préparation du corpus s'est arrêtée net : les fonctions standard de la
> bibliothèque de données dupliquaient toute la table audio sur le disque. Plutôt que de
> subir la contrainte, j'ai repensé la gestion des données. Je reconstruis le jeu de
> données à la volée depuis le cache Hugging Face, sans jamais matérialiser de copie ; le
> filtrage se fait par sélection paresseuse d'indices, donc sans réécrire les données ; et
> je sépare les caches entre partitions, les corpus et les embeddings sur l'espace
> temporaire, les poids du modèle de langage sur l'espace projet. C'est un exemple direct
> de contrainte d'infrastructure qui redessine le code, et pas seulement sa configuration.

**Q10.4. Racontez l'inter-blocage du chargeur de données.**

> Premier entraînement complet, blocage total : la perte ne progresse plus, l'occupation du
> GPU tombe à 0 %, aucune erreur, aucun message, aucune trace. Le pire des scénarios de
> diagnostic. J'ai suspecté mes données, puis la configuration SLURM, avant d'identifier la
> cause : les processus auxiliaires chargés d'alimenter le GPU démarraient par duplication
> du processus principal, en fork, après l'initialisation de CUDA et du décodeur audio.
> C'est un inter-blocage classique et parfaitement silencieux. Forcer le démarrage par
> création d'un processus neuf, en spawn, a levé le blocage, au prix d'une conséquence en
> cascade : dans ce mode la fonction de transformation doit être sérialisable, ce qui m'a
> obligé à remplacer une fonction anonyme par une classe.

**Q10.5. Pourquoi ne pas avoir parallélisé sur plusieurs nœuds ou plusieurs GPU ?**

> Parce que le problème ne le demandait pas. L'entraînement LoRA porte sur 3,54 millions de
> paramètres entraînables, soit 1,45 % du modèle, sur un corpus modeste, et il tient
> confortablement sur un seul GH200 en trois époques. Ajouter du parallélisme de données
> aurait ajouté de la complexité et du temps de file d'attente pour un gain nul. Le goulot
> d'étranglement réel de ce projet n'a jamais été le calcul d'entraînement : il a été la
> quantité et la qualité des données du domaine, puis la latence d'inférence.

**Q10.6. Où est le vrai problème de performance de votre projet ?**

> À l'inférence, et il est de nature interactive. La contrainte n'est pas le débit mais la
> latence de queue : ce qui rend une boucle de dialogue utilisable ou non, c'est le p95, pas
> la moyenne. Trois modèles à servir, dont deux coûteux, un budget total de quelques
> secondes, et le choix du placement, cluster partagé avec file d'attente et tunnel SSH, ou
> carte locale. C'est exactement l'arbitrage que chiffre mon tableau de bout en bout : 2,6 s
> en local contre 9,0 s à travers le cluster, pour un résultat fonctionnel identique.

**Q10.7. Quel est le coût énergétique ou financier de votre système ?**

> Je ne l'ai pas mesuré, et je ne veux pas donner un chiffre que je n'ai pas. Ce que je
> peux dire, c'est que le point de déploiement retenu tient sur une carte graphique
> d'ordinateur portable de 8 Go, ce qui est l'ordre de grandeur d'un poste de formation
> ordinaire, et que la quantification 4 bits divise la taille du modèle par quatre pour
> 1,7 point d'exactitude. Une mesure de consommation serait une suite naturelle et facile
> à mener.

**Q10.8. Qu'est-ce que la quantification Q4_K_M ?**

> Un format de compression sur environ 4 bits par paramètre, au lieu de 16 ou 32. C'est le
> principe d'une photographie compressée : le fichier devient quatre à huit fois plus
> léger, au prix d'une légère perte de finesse. Dans mon cas, la perte est chiffrée à 1,7
> point d'exactitude, ce qui est exactement le genre d'arbitrage que je voulais mesurer
> plutôt que supposer.

**Q10.9. Comment servez-vous les modèles ?**

> Par llama.cpp pour les modèles de langage, avec déchargement GPU, et par une façade HTTP
> qui expose les trois routes standard de l'API OpenAI : transcriptions, complétions de
> chat, et synthèse vocale. Les trois briques sont donc interchangeables par une simple
> variable d'environnement. C'est cette décision qui a permis de basculer du cluster vers
> la carte locale sans réécrire une ligne quand ROMEO est devenu indisponible.

**Q10.10. Qu'avez-vous appris de SLURM ?**

> Que la médiation par ordonnanceur a une conséquence pratique très concrète sur un stage
> court : chaque essai raté coûte non seulement le temps de calcul, mais aussi le temps
> passé dans la file. Cela change la façon de travailler : on ne teste pas sur le cluster,
> on valide localement puis on soumet. C'est directement à l'origine de ma première règle
> de travail, valider chaque brique isolément avant de l'assembler.

**Q10.11. Le simulateur est-il parallélisé ?**

> Non, et c'est même l'inverse : BlueSky n'est pas conçu pour être appelé depuis plusieurs
> fils d'exécution à la fois, donc il vit dans un fil unique alimenté par une file de
> commandes. C'est une contrainte que j'ai découverte à l'usage et qui a structuré tout le
> serveur. Elle n'est pas gênante, puisqu'il tourne 67 fois plus vite que le temps réel à
> 200 aéronefs.

---

## 11. Architecture, génie logiciel, qualité

**Q11.1. Décrivez l'architecture en trente secondes.**

> Un navigateur avec le radar sur canevas et le push-to-talk. Un serveur FastAPI qui reçoit
> les actions par requêtes REST et pousse l'état du trafic par WebSocket, rafraîchi environ
> huit fois par seconde. Trois services d'IA consommés à travers un contrat OpenAI unique
> et interchangeable. Une couche de validation déterministe entre le modèle et le
> simulateur, que rien ne contourne. Et BlueSky dans un fil unique alimenté par une file de
> commandes.

**Q11.2. Pourquoi le contrat OpenAI plutôt qu'une interface maison ?**

> Pour l'interchangeabilité. Changer de fournisseur, façade auto-hébergée sur ROMEO,
> façade locale du banc, ou service commercial, ne modifie ni le code, ni les gardes, ni
> les tests : on remplace trois adresses dans un fichier de configuration. Et c'est une
> décision d'architecture qui a fini par sauver ma campagne de mesure, ce que je
> n'anticipais pas quand je l'ai prise.

**Q11.3. Pourquoi remonter les pannes en 502 plutôt que de les rattraper ?**

> Parce que je préfère un système qui s'arrête visiblement à un système qui continue en
> silence avec un modèle dégradé. L'architecture initiale à deux modes pouvait basculer
> silencieusement d'un fournisseur à l'autre, ce qui masquait les pannes ; c'est un risque
> que mon propre audit a identifié. Toute panne de fournisseur devient maintenant une
> erreur typée, un code 502, et un événement visible dans le journal de bord de
> l'interface. Ce choix est contre-intuitif pour qui cherche d'abord la robustesse
> apparente, et il est délibéré.

**Q11.4. Combien de tests, et que testent-ils ?**

> 209 tests unitaires en intégration continue sur GitHub. La progression est parlante :
> 110 avant l'audit de juillet, 148 après, 186 après la validation stricte des entrées, 209
> après la revue de production. Ils couvrent la couche de validation, le connecteur vers le
> simulateur, le barème, le parseur, et incluent des tests de non-régression qui figent des
> comportements précis, y compris le comportement du barème que j'ai reclassé en non-bug.

**Q11.5. Comment avez-vous conduit l'audit de juillet ?**

> Sous-système par sous-système, en quatorze relectures spécialisées, chaque verdict devant
> être adossé à une preuve d'exécution et non à une simple lecture. Six défauts numérotés
> en sont sortis, tous traités. Puis une revue de production menée en mode adversarial :
> chaque constat devait d'abord résister à une tentative de réfutation sur le code réel.
> Cela m'a conduit à confirmer 32 constats, mais aussi à en réfuter 10 qui semblaient
> solides, et à en reclasser un en comportement voulu.

**Q11.6. Qu'est-ce que le « code mort de sécurité » que vous avez trouvé ?**

> Mon repli géométrique de détection de conflits, celui qui doit prendre le relais si le
> détecteur natif de BlueSky n'est pas disponible, testait le type de l'objet en
> interrogeant son nom de classe. Or BlueSky n'expose pas directement l'objet mais un
> mandataire, un Proxy, dont le nom de classe n'a jamais été celui attendu. La condition
> n'était donc jamais vraie et le repli ne pouvait pas s'activer. Un filet de sécurité qui
> n'a jamais été déployé une seule fois ne se signale par aucun symptôme : le système
> fonctionnait parfaitement, puisque le détecteur natif marchait. J'ai remplacé
> l'inspection de type par un drapeau positionné à l'activation, avec un test dédié.

**Q11.7. Quelle dette technique assumez-vous ?**

> Une, et je l'écris noir sur blanc plutôt que de laisser un successeur la découvrir par
> accident. XTTS réclame un symbole supprimé de la bibliothèque transformers en version 5,
> alors que Whisper et Mistral m'imposaient de rester dans cette version. Plutôt que de
> rétrograder tout l'environnement, ce qui aurait cassé les deux autres modèles, j'ai
> restauré ce symbole par un correctif appliqué juste avant l'import. Il cassera
> silencieusement à la prochaine montée de version.

---

## 12. Difficultés et incidents

**Q12.1. Quel a été l'incident le plus difficile à diagnostiquer ?**

> L'inter-blocage du chargeur de données, sans hésiter, parce qu'il n'y avait rien à lire :
> pas d'erreur, pas de message, pas de trace, juste un GPU à 0 %. Le deuxième est
> l'effondrement de Mistral à 20,7 %, parce que la cause était à trois couches de distance
> du symptôme et que mes deux premières hypothèses, la quantification puis ma propre
> consigne, étaient toutes deux plausibles et toutes deux fausses.

**Q12.2. Comment avez-vous tranché sur l'affaire Mistral ?**

> En écrivant un test dédié dont le seul rôle était d'inspecter ce que le moteur envoie
> réellement au modèle, octet par octet. Le verdict a été sans appel : le gabarit de
> conversation Mistral-v0.3 embarqué par llama.cpp perd purement et simplement le message
> système. Or c'est là que se trouvent l'ancrage OACI, le schéma JSON et toutes mes règles
> de sécurité. Le modèle recevait la clairance sans aucune instruction sur ce qu'il devait
> en faire. La cause est un détail de convention : le gabarit officiel Mistral n'a pas
> d'emplacement séparé pour le message système et le fusionne dans le premier message
> utilisateur, alors que l'implémentation embarquée le laissait tomber. J'ai reproduit le
> comportement officiel par une option de ma façade : 20,7 % devient 81,9 %, et 0 % de JSON
> valide devient 100 %.

**Q12.3. Comment avez-vous géré la panne de ROMEO ?**

> Sans rien réécrire, et c'est le point. Trois semaines avant, j'avais refondu
> l'architecture en un mode unique OpenAI-compatible pour corriger un défaut de visibilité
> des pannes. Quand ROMEO est devenu totalement indisponible pour une maintenance de
> sécurité, au moment précis où je lançais les benchmarks, il a suffi d'une bascule du
> fichier de configuration vers la façade locale. L'application et le banc sont restés
> pleinement opérationnels. Une décision prise pour des raisons de visibilité s'est trouvée
> validée par un incident de continuité de service qu'elle n'anticipait pas.

**Q12.4. N'êtes-vous pas simplement chanceux ?**

> En partie, oui, et je le dis dans le rapport : je n'en tire aucune gloire particulière.
> Ce que l'épisode illustre, et qui n'est pas de la chance, c'est qu'une architecture
> propre paie sur des dimensions qu'on n'avait pas prévues. Je n'avais pas anticipé la
> panne ; j'avais supprimé un couplage.

**Q12.5. Quels incidents purement Windows avez-vous rencontrés ?**

> Un principal : llama.cpp compilé avec CUDA ne trouvait pas sa bibliothèque dynamique
> parce que les DLL CUDA n'étaient pas dans le chemin de recherche de Windows. La solution
> a été de déclarer explicitement le répertoire des DLL du paquet torch avant le chargement.
> Cela paraît anecdotique, mais c'est exactement le genre de panne située à un niveau où je
> ne pensais pas avoir à regarder, et c'est ce que je retiens de ces dix semaines.

---

## 13. Limites, résultats négatifs, éthique

**Q13.1. Listez vos résultats négatifs.**

> Quatre. Llama-3.2-1B est inutilisable sur cette tâche, 3,4 % d'exactitude, et ce n'est
> pas un réglage à améliorer mais une inadéquation de fond. Qwen2.5-3B viole
> systématiquement le schéma de sortie, et ce comportement a survécu au changement de
> quantification. Les voix clonées XTTS sont trois à quatre fois moins intelligibles que
> Kokoro, ce qui contredit ce que j'ai cru pendant tout le stage. Et le modèle vocal de
> bout en bout que j'ai essayé en août atteint 0 % d'exactitude des ordres dans les quatre
> conditions.

**Q13.2. Le modèle full-duplex, racontez.**

> C'est une piste poursuivie en août, après le terme de la convention, et je la rapporte
> parce que son résultat est négatif. L'architecture que je défends est une cascade : trois
> modèles spécialisés qui se passent le relais, avec du code entre eux. La solution
> concurrente confie toute la boucle à un unique modèle vocal qui écoute et répond sans
> jamais passer par du texte. J'ai servi NVIDIA VoiceChat-11B sur le GH200 et je lui ai
> fait passer les mêmes 25 clairances dans les quatre conditions du banc. Le collationnement
> produit est correct dans 36 % des cas sur voix synthétique et 48 % sur ma voix, ce qui
> n'est pas absurde ; mais l'exactitude des ordres exécutés est de 0 % dans les quatre
> conditions. Le modèle converse, il n'exécute pas. Et surtout, la raison de fond rejoint
> tout le rapport : dans une cascade, on peut insérer une couche de vérification entre la
> compréhension et l'action ; dans un modèle de bout en bout, il n'y a pas d'endroit où la
> mettre.

**Q13.3. Vos mesures, que ne prouvent-elles pas ?**

> Je les énonce explicitement. Les énoncés de la référence de bout en bout sont synthétiques
> et la contre-épreuve humaine repose sur un seul locuteur, moi, en lecture et non en parole
> spontanée. Les corpus réels couvrent ce risque pour l'étage de reconnaissance pris
> isolément, pas pour la boucle complète. L'intelligibilité de la synthèse est une métrique
> relative, biaisée par son juge. Le WER historique de 22 à 24 % de la boucle XTTS utilisait
> une métrique maison non comparable. Et le corpus d'interprétation, quoique stratifié et
> volontairement adversarial, reste de taille modeste avec ses 116 cas.

**Q13.4. Quel est le risque si votre système se trompe en formation ?**

> C'est la question qui structure tout le rapport. Une erreur d'interprétation exécutée
> dans le simulateur fausse silencieusement l'exercice pédagogique : un élève à qui l'on
> ferait monter un avion sur un ordre de descente n'apprendrait pas seulement rien, il
> apprendrait quelque chose de faux. C'est pour cela que la validation déterministe est en
> aval du modèle et non dans le modèle, et c'est pour cela que je préfère un rejet explicite
> à une manœuvre approximative : un rejet coûte à l'élève une répétition, une manœuvre
> fausse lui coûte un apprentissage faux.

**Q13.5. Ce système pourrait-il remplacer un contrôleur ?**

> Non, et ce n'est pas l'objet. Il remplace le pseudo-pilote, c'est-à-dire l'opérateur qui
> joue les avions en salle de simulation, dans un contexte d'entraînement et non
> opérationnel. Rien de ce que j'ai construit ne touche au contrôle réel, et aucun de mes
> résultats ne pourrait le justifier.

**Q13.6. Y a-t-il un enjeu de protection des données ?**

> Les corpus employés sont publics et publiés pour la recherche, et les enregistrements de
> la contre-épreuve humaine sont les miens. Le système est conçu pour fonctionner hors
> ligne, ce qui est l'une des trois raisons pour lesquelles j'ai écarté les services de
> transcription commerciaux : ils auraient fait sortir les données de l'établissement.
> L'application est mono-poste et locale, sans authentification, l'exposition réseau étant
> explicitement hors périmètre.

**Q13.7. Que faudrait-il pour passer en production ?**

> Trois choses au minimum, dans cet ordre. Une validation pédagogique avec de vrais élèves,
> qui est la seule qui compte pour l'usage visé. Une contre-épreuve multi-locuteurs, de
> préférence avec des professionnels en phraséologie spontanée. Et le durcissement du
> déploiement : authentification, multi-poste, exposition réseau, et une garde de
> plausibilité par type d'aéronef pour attraper les cas comme la vitesse à 50 nœuds que mes
> bornes physiques laissent passer.

---

## 14. Questions pièges

Chacune est formulée telle qu'elle risque d'être posée, avec le piège nommé.

**Q14.1. « Votre système marche à 76 %. Un quart des ordres sont donc faux ? »**

*Piège : confondre échec d'exécution exacte et manœuvre erronée.*

> Non, et la distinction est essentielle. 76 %, c'est le taux d'exécutions exactement
> conformes à l'attendu. Les 24 % restants ne sont pas des manœuvres fausses : la plupart
> sont des rejets, c'est-à-dire des ordres que la couche de validation a refusés et qui ne
> sont jamais parvenus au simulateur. Le chiffre qui répond vraiment à votre question est
> ailleurs : sur 1 871 ordres proposés au total, aucun ordre hors bornes n'a atteint le
> simulateur.

**Q14.2. « Vous avez fait tout cela seul en dix semaines ? »**

*Piège : sous-entendu que le périmètre est invraisemblable.*

> Non, et c'est justement l'objet de ma section 3.5. J'ai assemblé un supercalculateur, un
> simulateur de trafic mature, quatre familles de modèles ouverts et trois corpus que
> d'autres ont enregistrés, transcrits et publiés. Ce que j'ai écrit, c'est le canal VHF,
> le graphe et son validateur, les neuf fiches, l'adaptateur de 14 Mo, la couche de
> validation, le moteur d'exercices, l'application et le banc de mesure. Le rapport donne
> l'inventaire complet des deux côtés.

**Q14.3. « Un LLM à 81,9 %, ce n'est pas suffisant pour de l'aéronautique. »**

*Piège : appliquer un seuil de sûreté opérationnelle à un simulateur d'entraînement, et
supposer que la sûreté repose sur le modèle.*

> Deux réponses. D'abord le contexte : c'est un simulateur d'entraînement, pas un système
> opérationnel, et rien de ce que j'ai construit n'a vocation à toucher au contrôle réel.
> Ensuite, et surtout, la sûreté ne repose pas sur ces 81,9 %. Elle repose sur la couche
> déterministe en aval, dont la garantie est indépendante du modèle : je l'ai vérifiée avec
> un modèle à 3,4 % d'exactitude, qui a vu 636 de ses 1 391 propositions rejetées sans
> qu'aucune ne franchisse la barrière.

**Q14.4. « Vous avez annoté vous-même votre corpus de test. N'êtes-vous pas juge et partie ? »**

*Piège : le biais d'annotation, qui est réel.*

> C'est une objection juste, et je ne peux pas la lever complètement : oui, j'ai annoté les
> 116 clairances moi-même, et un corpus annoté par plusieurs personnes avec un accord
> inter-annotateurs serait meilleur. Trois éléments limitent le biais. L'annotation est
> mécanique : le TrafScript attendu se déduit de la clairance par une règle, il n'y a pas
> de jugement subjectif à porter. Le corpus est volontairement adversarial contre mon
> propre système, avec 24 négatifs de sécurité et 48 cas hors grammaire. Et le critère
> retenu est le plus sévère possible, l'exactitude stricte, ce qui joue contre moi et non
> pour moi. Cela dit, c'est bien une limite, et je la range avec les autres.

**Q14.5. « Vos intervalles de confiance se recouvrent tous. Vos comparaisons ne valent donc rien. »**

*Piège : confondre recouvrement d'intervalles et absence de différence.*

> Le recouvrement d'intervalles non appariés ne permet justement pas de conclure, ni dans
> un sens ni dans l'autre, et c'est exactement pourquoi je fais des tests appariés. Mes
> systèmes sont évalués sur les mêmes clairances, donc McNemar exploite l'appariement et
> est bien plus puissant. Il me donne des conclusions dans les deux sens : des écarts
> massivement significatifs, p inférieur à dix puissance moins vingt contre Qwen-3B et
> Llama, un écart significatif contre Qwen-1.5B à p égal 0,017, et des non-différences que
> je publie aussi, p égal 0,281 contre le parseur et 0,152 contre Qwen-1.5B.

**Q14.6. « Vous dites que le parseur à règles est meilleur. Pourquoi tout ce travail sur l'IA, alors ? »**

*Piège : lire le classement global au lieu des strates.*

> Le parseur n'est pas meilleur, il est meilleur ailleurs. Il est parfait dans sa grammaire
> fermée, 100 %, et il s'effondre dès qu'on en sort, 70,8 %, et jusqu'à 36 % sur les
> paraphrases. Le modèle est à 77,1 % hors grammaire et à 91 % sur ces mêmes paraphrases.
> Or hors grammaire, c'est le cas réel : un élève ne parle pas comme une expression
> régulière. Et l'écart global de six points n'est pas significatif, donc le classement
> général ne veut rien dire ici. C'est la complémentarité qui est le résultat, pas le
> classement.

**Q14.7. « Un rapport de stage qui publie autant de résultats négatifs, n'est-ce pas l'aveu d'un échec ? »**

*Piège : assimiler honnêteté et échec.*

> Je le vois exactement à l'inverse, et je l'assume comme un choix. Un rapport qui ne
> présenterait que ce qui fonctionne n'apprendrait rien à celui qui reprendrait le travail.
> Mes résultats négatifs sont documentés avec leurs intervalles de confiance et, pour
> Qwen-3B, avec l'expérience de contrôle qui leur donne leur valeur : sans la seconde
> quantification, mon résultat n'aurait été qu'une accusation contre un fichier. L'objectif
> premier du stage, lui, est atteint et mesuré.

**Q14.8. « 2,6 secondes, c'est deux fois plus lent qu'un humain. À quoi bon ? »**

*Piège : opposer la performance à l'objectif, alors que l'objectif est la disponibilité.*

> C'est exact et je le compte comme une limite. Mais la comparaison utile n'est pas
> « machine contre humain sur la latence », c'est « une heure d'entraînement avec
> pseudo-pilote contre une heure sans ». Le facteur limitant de la formation aujourd'hui,
> c'est qu'il faut un opérateur qualifié en permanence pour un élève. 2,6 secondes est
> compatible avec le rythme d'une fréquence d'entraînement, où un échange intervient toutes
> les dix à trente secondes. Le vrai risque que je signale est ailleurs : qu'un élève
> s'accoutume à un rythme qui n'est pas celui d'une vraie fréquence, et cela, mon banc ne
> sait pas le mesurer.

**Q14.9. « Pourquoi un LLM de 7 milliards de paramètres pour reconnaître quatre commandes ? »**

*Piège : sous-entendu que le problème est trivial et que l'IA est décorative.*

> La question est bonne, et j'ai le chiffre qui y répond : le parseur à règles fait 100 %
> sur la grammaire canonique, effectivement. Le modèle n'est là que pour ce que le parseur
> ne sait pas faire, c'est-à-dire les formulations imprévues, les paraphrases, le français
> parlé, les hésitations de transcription. Sur les paraphrases, le parseur est à 36 % et
> Mistral à 91 %. Et j'ajoute que je ne peux pas démontrer que sept milliards valent mieux
> que un milliard et demi sur mon corpus : p égal 0,152. Je garde Mistral pour le JSON
> strict à 100 % et parce qu'il est le seul à battre les règles hors grammaire.

**Q14.10. « Votre F1 vaut 1,0. C'est trop beau. »**

*Piège : suspicion de surapprentissage ou de circularité.*

> Ce n'est pas de la détection parfaite, c'est un accord parfait avec un simulateur de
> référence sur un protocole que je définis, et je le dis dans ces termes. Il est
> atteignable pour deux raisons précises : les aéronefs de BlueSky sont stabilisés, donc
> l'hypothèse de mouvement rectiligne uniforme est vraie, et l'horizon est de 120 secondes.
> Ce que le résultat valide, c'est l'hypothèse cinématique sur cet horizon. Il ne dit rien
> de trajectoires en virage, et ma vérification contre grille numérique, elle, porte sur un
> million de géométries tirées au hasard, pas sur des cas choisis.

**Q14.11. « Vous n'avez testé qu'un seul secteur, une seule langue, un seul locuteur. »**

*Piège : accumuler les limites pour suggérer que rien n'est démontré.*

> Les trois sont vraies et je les liste moi-même. Ce que je démontre est plus étroit que ce
> que le sujet pourrait laisser croire, et c'est pourquoi je sépare soigneusement ce qui est
> prouvé de ce qui est plausible. Un secteur fictif de sept points, une contre-épreuve à un
> seul locuteur, une validation pédagogique absente. En revanche, l'étage de reconnaissance
> vocale, lui, est évalué sur deux corpus de radio réelle avec des accents variés, donc la
> limite mono-locuteur ne porte que sur la boucle complète.

**Q14.12. « Que se passe-t-il si le modèle produit un ordre valide mais absurde ? »**

*Piège : la faille réelle de mon système, et il vaut mieux la reconnaître avant qu'on ne
la trouve.*

> Il passe, et j'en ai un exemple mesuré. « Reduce speed two five zero » a été entendu
> « speed to five zero », ce qui produit un ordre à 50 nœuds : absurde pour un avion de
> ligne, mais parfaitement à l'intérieur de mes bornes physiques, donc non filtré. C'est un
> cas d'école : la validation par bornes ne protège que contre l'impossible, pas contre
> l'implausible. Il faudrait une garde tenant compte du type d'aéronef et de son domaine de
> vol, et c'est une amélioration précise que le banc a identifiée.

**Q14.13. « Vous citez un article de 2026 pour un stage de 2026. Comment est-ce possible ? »**

*Piège : vérification de la rigueur bibliographique.*

> Deux cas dans ma bibliographie. Su et Haq est une prépublication déposée en 2026, et je
> la signale explicitement comme non évaluée par les pairs à la date de rédaction. Sharifi,
> Zongo et Wei est acceptée à un atelier CVPR 2026 et je le mentionne, avec la
> prépublication associée. Ma règle est annoncée en tête de bibliographie : chaque travail
> est cité dans sa version de référence, et un dépôt sur arXiv atteste d'un dépôt, non
> d'une relecture.

**Q14.14. « Vous avez travaillé sur un cluster mais vos résultats sont sur un portable. Le cluster vous a-t-il servi à quelque chose ? »**

*Piège : sous-entendu que la partie HPC est décorative.*

> Le cluster a servi à ce qui ne pouvait pas se faire ailleurs : l'entraînement de
> l'adaptateur, avec un lot de 48 permis par les 96 Go de mémoire unifiée, et
> l'hébergement des trois modèles en pleine précision dans un unique processus. Toute la
> partie apprentissage vient de là, et c'est aussi de là que viennent les mesures de
> référence en pleine précision qui me permettent de chiffrer le coût de la quantification.
> Les mesures finales sont locales parce que le cluster est tombé, et j'ai justement
> démontré que cette substitution ne change pas le résultat fonctionnel.

**Q14.15. « Quelle est la contribution scientifique, par opposition à l'ingénierie ? »**

*Piège : la question la plus dure du lot.*

> Je serai précis, parce que la question mérite de ne pas être esquivée. Il n'y a pas de
> nouvelle méthode d'apprentissage dans ce travail : la LoRA existe, l'ancrage existe,
> Whisper existe. Ce que j'apporte est de trois ordres. Un protocole d'évaluation
> reproductible et apparié pour une chaîne vocale ATC complète, ce qui est rare : le domaine
> publie beaucoup de WER isolés et très peu de mesures de bout en bout. Un résultat
> comparatif documenté, cascade contre modèle vocal de bout en bout, avec un écart
> significatif dans les quatre conditions. Et un résultat négatif utile sur le clonage
> vocal à partir d'audio radio, qui contredit ce que je croyais moi-même. Le reste est de
> l'ingénierie, et je ne prétends pas le contraire.

---

## 15. Questions personnelles et de posture

**Q15.1. Qu'avez-vous appris qui ne figure pas dans le rapport ?**

> Le rapport le dit en fait, mais c'est le point que je répéterais : je suis arrivé avec
> l'idée qu'un bon modèle fait un bon système, et je repars convaincu du contraire. Les
> épisodes qui m'ont le plus appris sont ceux où le modèle n'était pas en cause. Un gabarit
> de conversation qui fait passer un modèle de 82 à 21 %. Une comparaison de chaînes de
> caractères qui rend une garde contournable tout en affichant qu'elle a bloqué. Un quota
> disque qui reconstruit un pipeline de données entier.

**Q15.2. Qu'est-ce qui vous a le plus frustré ?**

> Deux choses. Le temps de file d'attente : sur dix semaines, chaque essai raté coûte le
> calcul plus l'attente, et cela m'a obligé à changer complètement ma façon de travailler.
> Et le fait de n'avoir jamais pu mettre le système entre les mains d'un élève contrôleur,
> ce qui est la seule validation qui compte vraiment.

**Q15.3. Comment avez-vous organisé votre travail ?**

> Autour de trois règles que je me suis données et que je tiens pour responsables d'une
> bonne part des résultats. Ne jamais assembler deux briques avant d'avoir mesuré chacune
> isolément. Faire passer toutes les campagnes de mesure par le code de production, jamais
> par une reconstitution. Et conduire la revue finale en mode adversarial, chaque constat
> devant résister à une tentative de réfutation sur le code réel.

**Q15.4. Que feriez-vous avec trois mois de plus ?**

> Trois suites, dans cet ordre. La normalisation déterministe des indicatifs épelés en
> amont du modèle : c'est le défaut le mieux caractérisé de tout mon banc, il est
> indépendant du locuteur, et il ne demande aucun nouvel apprentissage. L'élargissement de
> la contre-épreuve à plusieurs locuteurs, idéalement des élèves contrôleurs en phraséologie
> spontanée, ce qui lèverait la principale limite de ma validation. Et l'injection de l'état
> du trafic courant dans la requête, pour donner au modèle une conscience spatiale située,
> en sachant d'avance que c'est le terrain sur lequel Zhang et Mott signalent la faiblesse
> des modèles de langage : il faudrait donc y transporter la même discipline, représentation
> symbolique compacte et calcul laissé au code.

**Q15.5. Ce stage a-t-il changé votre projet professionnel ?**

> Il m'a confirmé un goût : celui de la preuve, plus encore que celui du prototype. Ce qui
> m'a le plus intéressé dans ces dix semaines, ce n'est pas le moment où la boucle a
> fonctionné pour la première fois, c'est le moment où j'ai su démontrer qu'elle
> fonctionnait, et surtout dire dans quelles limites.

**Q15.6. Que retenez-vous de la relecture de votre tuteur ?**

> Deux axes qui ont sensiblement amélioré le document : l'accessibilité du propos, ce qui
> m'a conduit à ajouter une section entière expliquant les notions techniques en langage
> courant et une autre expliquant comment lire les chiffres, et la rigueur de l'appareil
> bibliographique, ce qui m'a fait reprendre chaque référence pour citer la version évaluée
> par les pairs avec son DOI plutôt que la prépublication.

---

## 16. Ce qu'il ne faut jamais dire

- « Ça marche » sans chiffre. Toujours le taux, l'effectif et l'intervalle.
- « C'est mieux » sans test apparié. Vous avez passé tout un chapitre à expliquer pourquoi
  un écart de pourcentage ne vaut rien sans McNemar : ne vous contredisez pas à l'oral.
- « L'IA comprend ». Elle propose une interprétation ; le code vérifie.
- Un chiffre sans son terme de comparaison. 28,5 % ne veut rien dire seul, 71,9 vers 28,5
  veut dire quelque chose.
- « J'ai tout fait tout seul. » C'est faux et le rapport dit le contraire ; la question 0.1
  est votre réponse.
- Une excuse pour une limite. Énoncez-la, elle est dans le rapport, elle vous grandit.
- Inventer un chiffre sous la pression. « Je ne l'ai pas mesuré » est une bonne réponse et
  c'est la posture que défend tout votre travail.
- Répondre avant d'avoir compris la question. Reformulez d'abord.

---

## 17. Les chiffres à connaître par cœur

| Sujet | Chiffre | Terme de comparaison |
|---|---|---|
| Cadre | 406 h, 13 avril au 31 juillet 2026 | 10 semaines de projet, S1 à S10 |
| Machine | GH200, aarch64, 96 Go unifiés | quota 20 Go par partition |
| Adaptateur LoRA | 14 Mo, 144 tenseurs, r = 32 | contre plusieurs Go d'affinage complet |
| WER ATCO2, condition VHF | 28,5 % | contre 71,9 % sans adaptation, gain 60 % relatif |
| WER UWB, condition VHF | 19,2 % | contre 91,9 % sans adaptation |
| WER validation | 6,68 % | contre 28,5 % en test : le fossé de généralisation |
| Gain LoRA, bootstrap apparié | -45,2 points | IC 95 % [-51,1 ; -39,6], exclut zéro |
| Mesure historique S4 | 74,3 vers 29,2 % | 869 extraits, retrouvée à 1 point près en juillet |
| RTF transcription local | 0,017 | 0,55 à travers la façade et le tunnel du cluster |
| Corpus d'interprétation | 116 clairances | 68 dans grammaire, 48 étendues, 24 négatifs |
| Parseur à règles | 87,9 % | 100 % dans grammaire, 70,8 % hors, 36 % sur paraphrases |
| Mistral-7B Q4 | 81,9 % | 85,3 % dedans, 77,1 % dehors, 91 % sur paraphrases |
| Qwen2.5-1.5B | 75,0 % pour 0,32 s | p = 0,152 face à Mistral : non significatif |
| Qwen2.5-3B | 24,1 % | 23,3 % pour la seconde quantification, p = 1,0 |
| Llama-3.2-1B | 3,4 % | 636 rejets sur 1 391 propositions |
| Parseur contre Mistral | p = 0,281 | non significatif : 6 points, c'est du bruit |
| Coût de la quantification | 1,7 point | 83,6 % en bf16 contre 81,9 % en Q4 |
| Sécurité | 1 871 proposés, 810 rejetés (43 %) | 0 ordre hors bornes exécuté sur 1 075 passés |
| Géométrie contre grille | 0 désaccord | sur 10^6 géométries, 5 graines de 200 000 |
| Géométrie contre BlueSky | F1 = 1,0 | 113 vrais positifs, 87 vrais négatifs, 200 rencontres |
| Erreur dCPA contre BlueSky | 0,067 NM | 0,71 s sur l'instant du CPA |
| Conflits garantis | 100 % sur 2 000 tirages | pire dCPA 0,082 NM contre 5 NM de norme |
| Montée en charge | 15 ms de calcul par seconde de trafic à 200 aéronefs | 9,5 ms à 5 aéronefs |
| Kokoro | RTF 0,336, WER 22,0 vers 21,4 % | le canal VHF ne coûte rien de mesurable |
| XTTS cloné | 64,9 à 92,0 % après VHF | trois à quatre fois pire que Kokoro |
| Boucle vocale locale | 19/25 = 76 %, IC [56,6 ; 88,5] | témoin texte 22/25 = 88 % |
| Latence locale | 2,6 s, p95 3,2 s | 0,36 STT / 1,06 LLM / 1,15 TTS |
| Boucle sur ROMEO | 19/25 = 76 % | mêmes six cas en échec : 4, 8, 10, 12, 13, 24 |
| Latence cluster | 9,0 s, p95 13,6 s | l'écart est dans le transport, pas dans les modèles |
| Contre-épreuve humaine | 20/25 = 80 % au micro | 18/25 = 72 % en radio, McNemar p = 1,0 |
| Full-duplex, août | 0 % d'ordres exacts | dans les quatre conditions, p de 0,001 à 0,008 |
| Génération de trafic | 116/116 contraintes et 20/20 descriptions | Mistral 71,8 % et 3/20 |
| Tests | 209 en intégration continue | 110 avant l'audit, 148 après |
| Revue de production | 32 constats confirmés | 10 réfutés, 1 reclassé en non-bug |
| Effet du correctif Mistral | 20,7 vers 81,9 % | JSON strict 0 vers 100 % |

---

## 18. Aide-mémoire des renvois

Les numéros de diapositive ci-dessous sont ceux des **pages du PDF** (43 au total), donc
ceux de `script-oral.md`, et non ceux affichés en bas à droite : le compteur « x/25 »
ignore les pages de section et l'annexe.

| Si la question porte sur... | Renvoi rapport | Page du PDF |
|---|---|---|
| Ce qui est de vous | §3.5, tableau des outils | 8 |
| L'architecture et les gardes | §2.3, §3.2 | 4 |
| Le WER et la LoRA | §2.2, §5.3 | 10, 11 |
| Le choix des corpus | §2.1 | 12 |
| L'ancrage et les fiches | §2.3, tableau des fiches | 14 |
| La comparaison des modèles | §5.4 | 16, 17 |
| Les statistiques | §5.1 | 16 |
| La géométrie et F1 | §5.2 | 23 |
| La synthèse vocale | §5.5 | 25 |
| La boucle complète | §5.6, annexe | 26 |
| La panne de ROMEO | §4.4 | 27 |
| La garde contournable | §4.3 | 22 |
| Les limites | §6 | 29 |
| Les perspectives | §7 | 30 |

Rappel : les diapositives de réserve occupent les pages 33 à 43 du PDF, dans l'ordre
catégories, latence, synthèse vocale, quantification, petit modèle, bout en bout, montée en
charge, conflits garantis, filtre VHF, mode exercice, boucle sur ROMEO.
