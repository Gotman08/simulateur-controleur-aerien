# Texte oral de la soutenance — « Parler aux avions »

Durée mesurée : **22 min 28 s** de parole à un rythme normal (145 mots/minute), hors questions.
Les temps par diapositive sont calculés depuis le texte lui-même, pas estimés.
La colonne « cumul » vous dit où vous devriez en être.

**Pour tenir 20 minutes**, coupez les diapositives 17 (chacun son terrain, 48 s), 18 (le prix du
langage naturel, 56 s) et 23 (le noyau géométrique, 41 s) : ce sont les trois seules
dont le retrait ne casse aucun enchaînement, et vous retombez à **20 min 03 s**.
Ne coupez jamais la 4, la 8 ni la 22 : la 4 porte l'architecture, la 8 répond à
« qu'avez-vous fait, vous ? », et la 22 est votre meilleure preuve d'honnêteté.

Chaque texte est écrit pour être **dit**, pas lu : phrases courtes, un chiffre
à la fois. Ne lisez jamais une diapositive à voix haute, le jury sait lire.

---

## 1 — Titre · 31 s · cumul 0:31

Bonjour. Je vais vous parler d'un stage dont l'objectif tient en une phrase :
permettre à un élève contrôleur aérien de parler à des avions, et que les
avions lui répondent.

L'image derrière ce titre n'est pas une maquette. C'est l'application qui
tourne.

Je précise tout de suite, parce que ça oriente toute la lecture : le sujet de
ce stage n'est ni un modèle d'intelligence artificielle, ni un simulateur de
trafic. C'est un dialogue radio.

---
## 2 — L'élève parle, personne ne répond · 55 s · cumul 1:26

Voici le problème, tel qu'il se pose aujourd'hui dans une salle de simulation.

À gauche : l'élève contrôleur prend le micro et dit « Air France 300, descendez
niveau 180 ». Pour que quelqu'un lui réponde, il faut un opérateur humain
derrière la cloison. On l'appelle un pseudo-pilote. Il joue tous les avions du
secteur, à lui tout seul : il prononce les réponses et il exécute chaque
instruction dans le simulateur.

Un opérateur qualifié, mobilisé en permanence, pour un seul élève. C'est ce qui
limite le nombre d'heures d'entraînement qu'on peut offrir.

À droite, l'objectif : que les avions répondent sans cet opérateur.

Le verrou pédagogique n'est donc ni le radar, ni la physique du vol. C'est
l'absence d'interlocuteur. Ce que j'ai cherché à automatiser, c'est le pilote,
pas le radar.

---
## 3 — La boucle radio, en cinq étapes · 53 s · cumul 2:19

Voici la carte du territoire. Gardez-la en tête, tout le reste s'y raccroche.

L'élève parle. Premier étage : **entendre**, la parole devient du texte, c'est
un modèle de reconnaissance vocale. Deuxième étage : **comprendre**, le texte
devient un ordre structuré, c'est un modèle de langage. Troisième étage :
**vérifier**, et là ce n'est plus un modèle, c'est du code. Quatrième :
**exécuter**, le simulateur fait manœuvrer l'avion. Cinquième : **répondre**,
l'avion collationne dans une voix de synthèse passée en canal radio.

Et la boucle se referme : l'élève entend la réponse et enchaîne.

Les chiffres sous les cases sont les latences moyennes mesurées sur vingt-cinq
clairances parlées. Trois dixièmes de seconde pour entendre, une seconde pour
comprendre, un peu plus d'une seconde pour répondre. **Deux secondes six au
total.**

Retenez surtout la case ambre au milieu, celle qui n'est pas un modèle. C'est
le sujet de la diapositive suivante.

---
## 4 — Le modèle propose, le code vérifie · 79 s · cumul 3:38

Si vous ne deviez retenir qu'une phrase de cette soutenance, ce serait
celle-ci : **le modèle propose, le code vérifie.**

À gauche, le modèle de langage produit un ordre. Il ne l'exécute pas. Il le
propose. Entre lui et le simulateur, il y a un mur, et ce mur est écrit en code
classique, entièrement testé.

Ce mur pose quatre questions à chaque ordre. Le niveau est-il dans les limites
physiques de l'avion ? Le cap est-il entre zéro et trois cent soixante ? Le
point de report existe-t-il vraiment dans le secteur ? Et la dernière, la plus
subtile : est-ce qu'on me demande de descendre vers un niveau plus haut ?

Si un seul test échoue, rien n'est exécuté, le refus est tracé, et l'avion
reste muet.

Le résultat, sur toute la campagne de mesure : les six systèmes évalués ont
proposé mille huit cent soixante et onze ordres. **Huit cent dix ont été
rejetés.** Et pas un seul ordre hors limites n'a atteint le simulateur.

C'est ma réponse par avance à la question « et si l'intelligence artificielle
se trompe ? ». Elle se trompe. C'est prévu.

---
## 5 — *Section : ce qu'il a fallu construire* · 5 s · cumul 3:43

Pour éprouver ce dialogue, il a fallu construire tout ce qui l'entoure.

---
## 6 — Pour éprouver la voix, il a fallu bâtir tout le reste · 67 s · cumul 4:50

Un dialogue ne se teste pas dans le vide. Pour que l'avion ait un ordre à
exécuter et un état à collationner, il faut un trafic, un espace aérien, un
radar.

J'ai donc livré une application d'entraînement complète : un scope radar temps
réel, des conflits programmés pour qu'il y ait quelque chose à résoudre, du
vent, des cellules orageuses, un poste instructeur qui crée des situations à
partir d'une phrase, et une notation en direct avec débriefing.

Un mot sur le coût de ce simulateur, parce qu'il conditionne la suite. Avec
deux cents avions à l'écran, **simuler une seconde de trafic lui coûte quinze
millisecondes de calcul.** À comparer aux deux secondes six de ma boucle
vocale : la simulation n'est jamais le facteur limitant. Tout le budget de
latence est consommé par les trois étages d'intelligence artificielle.

Mais je veux être clair sur la hiérarchie : tout ceci n'est pas le sujet. C'est
la condition d'existence de la mesure.

---
## 7 — Un banc par brique, un fichier par chiffre · 41 s · cumul 5:31

Un mot de méthode, parce qu'il conditionne la valeur de tous les chiffres qui
suivent.

J'ai construit un banc de mesure par brique. Chacun écrit un fichier de
résultats qui contient à la fois le protocole et les mesures. Les figures de
mon rapport et les chiffres de cette soutenance sont **générés** depuis ces
fichiers.

Aucun chiffre n'est saisi à la main. Aucun.

Les protocoles sont à graine fixée, donc rejouables à l'identique. J'ai
d'ailleurs rejoué la campagne un mois plus tard : les métriques sont identiques
champ à champ.

C'est ce qui distingue une démonstration d'une démo.

---
## 8 — Ce que j'ai emprunté, ce que j'ai écrit · 58 s · cumul 6:29

Un mot sur ce que ce projet doit à d'autres, parce que la question se pose
toujours.

À gauche, ce que j'ai emprunté : le supercalculateur, trois corpus de radio
réelle enregistrés et transcrits par d'autres, quatre familles de modèles
ouverts, et le simulateur de trafic. Personne n'entraîne un modèle de
reconnaissance vocale depuis zéro en dix semaines, et ce n'était pas le sujet.

À droite, ce que j'ai écrit : le canal radio, le graphe de secteur et son
validateur, les neuf fiches de phraséologie, l'adaptateur de quatorze
mégaoctets, seul artefact de modèle qui soit de moi, la couche de validation,
le moteur d'exercices, l'application et le banc de mesure.

Les briques d'IA viennent de la communauté. Je les ai choisies, assemblées,
adaptées et surtout **mesurées**. L'architecture de sûreté et l'appareil de
preuve, eux, sont le travail du stage.

---
## 9 — *Section : entendre* · 5 s · cumul 6:34

Premier étage : entendre.

---
## 10 — La machine n'entend pas la radio comme nous · 64 s · cumul 7:38

Voici un extrait réel de mon corpus de test, capté sur une vraie fréquence.

Le pilote dit : « alfa delta holding point zero four, Eurotrans one three
Juliett ».

En haut, ce qu'en fait un modèle de reconnaissance vocale généraliste, très
bon par ailleurs. Il entend le début, puis il transforme l'indicatif
« Eurotrans one three Juliett » en « you are transformed redrew it ». C'est du
charabia. Et surtout, c'est l'indicatif qui est détruit, c'est-à-dire
l'information qui dit à quel avion on parle.

En dessous, le même extrait passé dans le modèle que j'ai adapté au métier. Il
le transcrit exactement.

Pour mesurer cela sur un corpus entier, on utilise le taux d'erreur mots : les
mots faux, plus les mots manquants, plus les mots inventés, divisés par les
mots attendus.

Sur la radio réelle, je passe de soixante-douze pour cent d'erreur à
**vingt-huit et demi**. Sur le second corpus, de quatre-vingt-douze à
**dix-neuf**.

Sept mots sur dix faux, puis moins de trois.

---
## 11 — Adapter un modèle sans le réentraîner · 60 s · cumul 8:38

Comment obtient-on ce gain ? Pas en réentraînant le modèle.

Le modèle de reconnaissance vocale compte deux cent quarante-quatre millions de
paramètres. La méthode naïve consiste à tous les reprendre. Sur un petit corpus
c'est instable, et matériellement c'était impossible : le cluster m'imposait
vingt gigaoctets par partition, et chaque sauvegarde intermédiaire en pèse
plusieurs.

J'ai donc utilisé une technique qui s'appelle LoRA. On **gèle** le modèle
d'origine, on n'y touche pas, et on lui adjoint de petites matrices
correctrices qu'on entraîne seules. Environ un et demi pour cent des
paramètres.

L'image que j'utilise : on ne réécrit pas le dictionnaire, on ajoute le lexique
du métier.

Résultat concret : toute l'adaptation au contrôle aérien tient dans un fichier
de **quatorze mégaoctets**, que je versionne dans le dépôt à côté du code.

Ce choix n'est pas une mode. Il est imposé par les moyens réels.

---
## 12 — Deux corpus de radio réelle · 36 s · cumul 9:14

Un chiffre isolé ne prouve rien, donc deux précautions.

D'abord, le gain est mesuré sur deux corpus de radio authentique, avec des
accents et des qualités audio différentes. Je ne les moyenne pas : ce sont deux
mesures, pas une.

Ensuite, je l'ai confirmé par un test statistique apparié, extrait par extrait.
L'écart est de quarante-cinq points, avec un intervalle de confiance qui va de
moins cinquante et un à moins quarante. Cet intervalle ne touche jamais zéro :
ce n'est pas un effet du hasard de l'échantillon.

---
## 13 — *Section : comprendre* · 5 s · cumul 9:19

Deuxième étage : comprendre.

---
## 14 — On ne lui demande pas de savoir · 62 s · cumul 10:21

Le texte est écrit, il faut maintenant en tirer un ordre.

À gauche, ce que donne un modèle de langage laissé seul. Vous lui dites
« direct Golf Alpha ». Il vous répond avec assurance, et il vous envoie l'avion
vers un point qui n'existe pas dans le secteur. C'est le comportement typique :
il improvise, et il improvise bien.

J'ai choisi l'inverse. Au lieu d'apprendre la phraséologie au modèle, **je lui
mets le manuel sous les yeux au moment où il répond.** Neuf fiches de règles que
j'ai rédigées pour ce projet, plus la description du secteur, recopiées dans sa
consigne à chaque requête.

À droite, ce qui sort : pas une phrase, un bordereau. Un indicatif, un ordre,
un paramètre.

La conséquence est celle qui m'intéresse : le modèle ne récite pas sa mémoire,
il lit des documents que je lui fournis. **C'est ce qui rend sa sortie
vérifiable.**

---
## 15 — La même donnée informe le modèle, et le contredit · 43 s · cumul 11:04

Un mot sur le secteur, parce qu'il joue un rôle double et que c'est l'idée dont
je suis le plus satisfait.

Voici l'espace aérien réduit à un graphe : sept points, six segments, une norme
de séparation de cinq milles marins. Trois lignes de texte.

Ce graphe, je le donne au modèle comme contexte : voilà les points qui
existent.

Et le même graphe sert ensuite de validateur : quand le modèle propose un point
de report, on vérifie qu'il est bien dans cette liste. S'il n'y est pas,
l'ordre est refusé.

La même structure de données renseigne le modèle, puis sert à le contredire.

---
## 16 — Le résultat qui dérange · 54 s · cumul 11:58

J'arrive au résultat que je préfère annoncer moi-même, avant qu'on me le
demande.

J'ai comparé mon modèle de langage à un module à base de règles, une centaine
de lignes de code, sans aucune intelligence artificielle. Sur cent seize
clairances que j'ai annotées à la main.

Les règles : quatre-vingt-huit pour cent. Le modèle de sept milliards de
paramètres : quatre-vingt-deux.

Et surtout, le test apparié de McNemar donne une valeur p de zéro virgule
vingt-huit. Traduction : **sur l'ensemble du corpus, les deux systèmes sont
statistiquement indiscernables.**

Je pèse mes mots. Indiscernables. Pas « le modèle est meilleur ». Pas non plus
« les règles sont meilleures ». Six points d'écart sur cent seize cas, c'est du
bruit d'échantillonnage.

Alors pourquoi garder un modèle de langage ? Diapositive suivante.

---
## 17 — Chacun son terrain · 48 s · cumul 12:46

Parce que la moyenne cachait la vraie information.

Regardez par strate. Sur la phraséologie standard, celle du manuel, les règles
sont à cent pour cent. Imbattables, et c'est logique : c'est exactement ce
qu'elles décrivent.

Sortez de cette grammaire — une paraphrase, une hésitation, du français, un
indicatif mal découpé — et les règles tombent à soixante et onze pour cent,
tandis que le modèle tient à **soixante-dix-sept**.

C'est précisément l'écart qu'il était chargé de combler.

Il n'y a donc pas de vainqueur, il y a une complémentarité : chaque brique
couvre le régime de langage où l'autre échoue. Je garde les deux dans le dépôt,
les règles comme référence de test, le modèle en production.

---
## 18 — Le prix du langage naturel · 56 s · cumul 13:42

Cette souplesse a un prix, et je préfère le chiffrer moi-même.

Le module à base de règles répond en quarante-cinq microsecondes : autant dire
instantanément. Le modèle de langage, en huit dixièmes de seconde. Et il occupe
quatre gigaoctets et demi de mémoire, contre rien.

Le chiffre qui compte n'est pas le rapport entre les deux, parce qu'ils ne sont
pas de même nature : d'un côté un appel de fonction en mémoire, de l'autre une
requête à un serveur d'inférence. Le chiffre qui compte, c'est la part dans la
boucle : **une seconde zéro six sur deux secondes six, soit quarante et un
pour cent du budget.** C'est le deuxième poste, juste derrière la synthèse
vocale.

Donc on ne paie ce prix que là où le modèle apporte quelque chose : les
formulations imprévues.

> *Si on vous demande le rapport exact* : environ dix-huit mille, mais précisez
> aussitôt qu'il compare une fonction locale à un appel réseau, et qu'il ne
> mesure donc pas que le modèle.

---
## 19 — *Section : les épreuves* · 5 s · cumul 13:47

Trois épreuves, maintenant. Ce sont elles qui m'ont le plus appris.

---
## 20 — L'enquête : le gabarit qui effaçait la consigne · 81 s · cumul 15:08

Le dix juillet, premier passage de mon banc. Mistral, le modèle sur lequel
repose toute la chaîne, s'effondre à vingt pour cent, avec **zéro pour cent**
de sortie correctement formée.

Un modèle qui ne produit plus jamais de sortie valide n'est pas un modèle un
peu moins bon. C'est un modèle qui ne reçoit pas la consigne.

Premier suspect : la compression du modèle. Écarté. Deuxième suspect : mon
propre texte de consigne. Écarté aussi.

Pour trancher, j'ai écrit un test dont le seul rôle était d'inspecter ce qui
part réellement vers le modèle. Et le verdict était ailleurs.

Le gabarit de conversation embarqué par le moteur de service **jetait purement
et simplement le message système**. C'est-à-dire mes fiches de phraséologie, mon
schéma de sortie et mes règles de sécurité. Le modèle recevait la clairance,
sans aucune instruction sur ce qu'il devait en faire.

Un correctif de conformité au gabarit officiel, et les vingt pour cent
redeviennent quatre-vingt-deux.

La leçon, je la formule ainsi : **un modèle ne s'évalue qu'à travers sa pile de
déploiement réelle.** Si j'avais publié la première mesure, j'aurais conclu de
bonne foi, avec des chiffres exacts, que ce modèle est inapte.

---
## 21 — Trois cas, trois verdicts · 58 s · cumul 16:06

Deuxième épreuve. Voyons la garde travailler, sur trois cas réels.

Premier cas : « Air France 1234, montez niveau 180 ». Le modèle propose une
montée au niveau 180. Tout est cohérent. Accepté.

Deuxième cas, et c'est un incident authentique : la reconnaissance vocale a
mal entendu, le modèle propose une **descente** vers le niveau 400, alors que
l'avion est au niveau 180. Cet ordre est parfaitement valide sur le plan
syntaxique. L'altitude est dans les limites physiques. Rien ne le distingue
d'une clairance légitime — sauf qu'on descend vers le haut. Refusé.

Troisième cas : un point de report qui n'est pas dans le secteur. Refusé.

Dans les deux refus : rien n'est exécuté, le refus est tracé, l'avion reste
muet. À l'élève de reformuler.

La garde n'est pas une intention d'architecture. Elle est visible, et elle est
testable.

---
## 22 — Ma garde était contournable · 78 s · cumul 17:24

Troisième épreuve, et c'est celle dont je suis le moins fier, donc celle que je
tiens le plus à raconter.

La garde du deuxième cas, je l'ai écrite en semaine 8, je l'ai testée, je l'ai
vue bloquer l'incident. J'étais convaincu d'avoir fermé la porte.

Un mois plus tard, en relisant mon code de manière adversariale — c'est-à-dire
en cherchant activement à le casser — je découvre une brèche.

Mon filtrage comparait deux **chaînes de caractères** : la valeur produite par
le modèle, « 32000.0 », et la valeur exécutée, « 32000 ». Ces deux chaînes ne
sont pas égales, bien qu'elles désignent le même nombre. Conséquence : dans ce
cas, l'ordre était annoncé comme bloqué à l'utilisateur, et exécuté quand même.

Le pire des cas possibles : une fausse assurance.

J'en tire deux règles. La première : une garde de sécurité n'existe vraiment
que si quelqu'un a essayé de la casser, parce qu'elle ne se signalera jamais
d'elle-même — elle a l'air de fonctionner, elle affiche un blocage. La seconde,
plus générale : **l'annonce d'un blocage doit être dérivée de l'action
réellement appliquée**, jamais d'un calcul parallèle.

---
## 23 — Le noyau géométrique, lui, se prouve · 41 s · cumul 18:05

Tout n'est pas probabiliste dans ce système, et je veux montrer la partie sur
laquelle je peux donner une garantie.

La détection de conflit repose sur une formule fermée. Je l'ai confrontée à
deux vérités calculées indépendamment.

Contre une recherche numérique exhaustive, d'abord : un million de géométries
tirées au hasard, **zéro désaccord**, erreur maximale cinq centièmes de mille
marin.

Contre le simulateur de référence ensuite, sur deux cents rencontres : aucun
conflit manqué, aucune fausse alerte.

Une précision d'honnêteté : cela veut dire un accord parfait avec le simulateur
sur ce protocole. Pas une détection parfaite en trafic réel.

---
## 24 — *Section : répondre et boucler* · 5 s · cumul 18:10

Dernier étage : répondre.

---
## 25 — On dégrade la voix volontairement · 41 s · cumul 18:51

L'avion doit répondre, et il doit répondre de manière réaliste.

Je prends donc la voix de synthèse, et je la **dégrade** volontairement : je ne
garde que la bande 300 à 3400 hertz, celle d'une vraie radio aéronautique.

Le point important est que j'applique le **même filtre des deux côtés** : sur
l'audio d'entraînement de mon modèle de reconnaissance, et sur la voix produite
pour l'élève. C'est ce qui rend la mesure honnête, et c'est aussi pédagogique :
un élève doit apprendre à écouter une mauvaise radio.

Et cette dégradation ne coûte presque rien en intelligibilité : je l'ai mesuré.

---
## 26 — La boucle complète · 53 s · cumul 19:44

Voici la réponse à la question posée au début.

Vingt-cinq clairances parlées, la chaîne entière, de la voix jusqu'au
collationnement : **soixante-seize pour cent** exécutées correctement.

Le témoin, les mêmes phrases tapées au clavier sans reconnaissance vocale :
quatre-vingt-huit. L'écart de douze points, c'est le coût résiduel de la voix.

Et parce que faire lire mes phrases par une voix de synthèse est un protocole
trop confortable, je les ai enregistrées moi-même au micro, avec mon accent :
**quatre-vingts pour cent**. Le test apparié dit que c'est indiscernable de la
référence.

Je dis tout de suite les limites, avant qu'on me les oppose : vingt-cinq cas
par condition, des intervalles de confiance larges et qui se recouvrent, et un
seul locuteur humain — moi.

Ce n'est pas une validation opérationnelle. C'est une mesure de faisabilité, et
elle est positive.

---
## 27 — Le supercalculateur tombe, la campagne continue · 54 s · cumul 20:38

Un dernier épisode, parce qu'il dit quelque chose sur l'architecture.

Le cluster m'a coûté cher en ingénierie : un quota de vingt gigaoctets, une
architecture de processeur inhabituelle, un bug de bibliothèque sur la synthèse
vocale que je n'ai pas pu corriger.

Trois semaines avant la fin, j'avais refondu l'application pour que les trois
modèles soient joignables par un contrat d'interface unique — trois adresses
dans un fichier de configuration. Je faisais ça pour rendre les pannes
visibles.

Et puis, au moment précis où je lançais mes campagnes de mesure, le
supercalculateur est devenu totalement indisponible.

Je n'ai rien eu à réécrire. Une ligne de configuration, et tout est reparti sur
une carte graphique d'ordinateur portable.

Une décision prise pour une raison a été validée par un incident qu'elle
n'anticipait pas.

---
## 28 — *Section : bilan* · 5 s · cumul 20:43

---
## 29 — Périmètre assumé · 41 s · cumul 21:24

Avant de conclure, ce que ce travail **n'est pas**.

Un seul locuteur humain, vingt-cinq phrases : aucune évaluation par de vrais
contrôleurs. Vingt-cinq cas par condition, donc des intervalles de confiance de
l'ordre de quinze points en bout de chaîne. Cent seize clairances annotées, un
secteur fictif à sept points, une seule langue. Et une seule machine : les
latences que je vous ai données ne se transposent pas telles quelles.

C'est un banc d'essai, pas une validation opérationnelle.

Je le dis parce que l'énoncer moi-même, chiffré, fait partie de la
démonstration de rigueur — et parce que c'est vrai.

---
## 30 — Ce qu'il faut retenir · 52 s · cumul 22:16

Cinq étages, cinq résultats.

Entendre : de soixante-douze à vingt-huit pour cent d'erreur mots, par
quatorze mégaoctets d'adaptation.

Comprendre : quatre-vingt-deux pour cent, statistiquement indiscernable d'un
module à base de règles.

Vérifier : zéro sortie de modèle non vérifiée. C'est le résultat qui compte.

Exécuter : zéro désaccord sur un million de géométries de conflit.

Répondre : la boucle complète tourne, à soixante-seize pour cent de réussite,
en deux secondes six.

Et la phrase du milieu, celle que je voudrais que vous reteniez : **le modèle
propose, le code vérifie.**

Les suites que je vois : plusieurs locuteurs et plusieurs accents, la
phraséologie française et des secteurs multiples, et surtout une évaluation par
de vrais élèves contrôleurs — la seule qui compte vraiment pour l'usage visé.

---
## 31 — Merci · 12 s · cumul 22:28

Merci de votre attention. Le code, les corpus annotés, les protocoles et les
résultats bruts sont tous dans le dépôt.

Je suis à votre disposition pour vos questions.

---

# Questions probables et où aller

Les numéros ci-dessous sont ceux des **pages du PDF** (43 au total), pas ceux affichés
en bas à droite : le compteur « x/25 » ignore les pages de section et l'annexe.

| Question | Diapositive de réserve | Réponse courte |
|---|---|---|
| Qu'avez-vous fait vous-même là-dedans ? | **8** | Les modèles et les corpus viennent de la communauté. L'adaptateur de 14 Mo, la couche de validation, le graphe de secteur, le moteur d'exercices, l'application et le banc de mesure sont à moi. |
| Pourquoi pas un plus petit modèle ? | **37** | L'écart avec Qwen 1.5B n'est pas significatif (p = 0,15). Je garde Mistral pour le JSON strict à 100 % et parce qu'il est le seul à battre les règles hors grammaire. |
| Pourquoi pas un modèle vocal de bout en bout ? | **38** | Testé en août : 0 % d'ordres exacts dans les quatre conditions. Et surtout, dans un modèle de bout en bout il n'y a pas d'endroit où mettre la vérification. |
| Que coûte la compression du modèle ? | **36** | 1,7 point d'exactitude, pour un fichier divisé par quatre. |
| Vos voix clonées, ça donne quoi ? | **35** | Mauvais : 65 à 92 % de WER aller-retour contre 18 à 25 % pour Kokoro. Le clonage part d'extraits radio déjà dégradés et reproduit la dégradation. C'est un résultat négatif que je publie. |
| L'élève entend-il les autres avions ? | *aucune* | Non. Chaque avion ne parle qu'à l'élève, et seulement pour collationner. L'effet « tout le monde entend tout le monde » d'une vraie fréquence n'est pas reproduit : c'est une limite pédagogique réelle et une suite naturelle. |
| Un WER de 28 %, ce n'est pas énorme ? | *aucune* | Si. C'est élevé pour un domaine critique, je l'écris dans le rapport. Ce qui rend le système utilisable, ce n'est pas le taux, c'est la validation déterministe : elle convertit la plupart des erreurs en refus explicites plutôt qu'en manœuvres fausses. |
| Le détail par catégorie de clairance ? | **33** | Carte de chaleur complète, dix-huit strates. |
| Combien de temps prend une clairance ? | **34** | Latence et débit par modèle. |
| Le simulateur tient-il la charge ? | **39** | À 200 aéronefs, simuler 1 seconde de trafic coûte 15 ms de calcul, soit 67 fois plus vite que l'horloge. La voix reste le facteur limitant, pas le trafic. |

**Si une question vous prend au dépourvu**, la formule honnête est toujours la
meilleure : « je ne l'ai pas mesuré, donc je ne peux pas vous répondre avec un
chiffre ». C'est exactement la posture que défend tout le rapport.
