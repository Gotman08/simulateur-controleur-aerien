# Amélioration du simulateur — 27 septembre 2026

Base : `origin/main`, commit `9e987e8`. Travaux isolés de la copie locale contenant des rapports et benchmarks non commités. Exécution et construction sur ROMEO dans `/scratch_p/nimarano/atc-review-20260927`.

Plan approuvé par l'utilisateur. Précision reçue ensuite : usage uniquement sur grand écran. La validation visuelle finale cible les postes 1440 × 1000 et 1920 × 1080, sans campagne téléphone.

## Constats vérifiés dans le code

- L'interface React 19 / Vite / Tailwind dispose déjà des cinq panneaux métier et d'un radar Canvas. Flowbite n'est pas installé. Le panneau fixe de 400 px et la barre supérieure ne sont pas adaptés aux petites fenêtres ; plusieurs contrôles reposent sur la souris ou un simple titre.
- `useSim.ts` masque les ruptures WebSocket et ne représente pas `sim_alive`, pourtant fourni par le serveur. Le timer de reconnexion n'est pas explicitement nettoyé. Les panneaux peuvent donc afficher un état ancien sans avertissement.
- `WSManager.broadcast` attend chaque client successivement : un client lent peut bloquer les autres. Plusieurs erreurs sont absorbées sans diagnostic.
- `SimManager.snapshot` copie superficiellement certains champs imbriqués. La file de commandes est entièrement vidée à chaque tick sans budget ; un flux continu peut retarder la simulation.
- Le repli de détection géométrique calcule les trajectoires avec le cap et la vitesse avant enrichissement BlueSky, donc sans tenir compte correctement du vent. Il exclut d'emblée les avions séparés verticalement et peut manquer une convergence verticale.
- La CI minimale ignore les tests FastAPI si cette dépendance est absente. Le frontend n'a pas de tests automatisés.
- BlueSky fournit déjà les mouvements, les routes, le vent, la turbulence et sa détection native de conflits. Toutes ses fonctions ne sont pas exposées dans l'interface. Les zones « orage » sont des zones pédagogiques ; l'export vers la GUI native ouvre une autre simulation, pas un miroir en direct.

## Implémentation proposée, dans l'ordre

1. Établir la référence sur ROMEO : dépendances isolées, suite existante complète, analyse statique et construction frontend. Conserver les journaux et versions.
2. Corriger les défauts de fiabilité : diffusion WebSocket indépendante par client avec limites, diagnostic des erreurs, copie des snapshots, traitement équitable des commandes et calcul géométrique fondé sur le mouvement sol et vertical. Ajouter les tests de régression correspondants.
3. Intégrer réellement Flowbite avec un thème de poste de contrôle sobre : radar sombre, console lisible, typographie et espacements cohérents, peu de décoration. Conserver trafic, instructeur, exercice, débrief, journal et radio. Améliorer clavier, labels, disposition sur grand écran et état hors connexion. Charger les graphiques du débrief à la demande.
4. Enrichir la lecture du simulateur : contrôles des couches radar, données de route et de guidage disponibles, différenciation des vitesses, moteur de conflits et santé réelle du simulateur. Documenter précisément la couverture de BlueSky et les fonctions restant à intégrer.
5. Lancer des campagnes concurrentes sur ROMEO : tests Python, build/tests frontend, simulation BlueSky réelle sur plusieurs densités et graines, et clients WebSocket concurrents/ralentis. Mesurer latence, débit, mémoire et comportement aux entrées invalides, sans attribuer à l'IA des tests faits avec des doublures.
6. Corriger les défaillances reproduites, relancer les contrôles concernés, conserver un rapport reproductible et les scripts de campagne. Créer des issues sur le dépôt du MCP Romeo uniquement pour des limites rencontrées et vérifiées, après recherche des doublons.
7. Préparer un commit et une branche dédiés avec les seuls changements de cette tâche ; revue finale de la différence et publication déléguée selon la compétence `push`.

## Critères de validation

- Les fonctions existantes restent accessibles et les tests de régression passent.
- Une panne ou une reconnexion ne présente pas silencieusement un radar ancien comme actuel.
- Un client lent ne bloque pas les clients sains ; les ressources des connexions sont libérées.
- Des simulations BlueSky réelles produisent des résultats enregistrés ; les limites non vérifiées sont explicites.
- Flowbite est présent dans les dépendances et utilisé dans les composants, sans simple imitation visuelle.
- Les artefacts frontend livrés correspondent aux sources modifiées.

## Accès et limites à clarifier par l'exécution

Les pages Flowbite Blocks refusent actuellement l'accès au lecteur web (HTTP 403). Le navigateur disponible ne contient aucune session ouverte. Les composants officiels Flowbite React et leur documentation sont accessibles ; aucun accès premium n'est présumé. Les anciens environnements et modèles ATC ne sont pas présents aux chemins ROMEO inscrits dans le projet : les tests de simulation et d'interface peuvent être préparés indépendamment, et les tests des vrais fournisseurs STT/LLM/TTS nécessitent un service ou des modèles disponibles.
