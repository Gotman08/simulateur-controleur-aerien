# Tests unitaires

Lancer depuis la racine du projet :

```
src\bluesky-env\Scripts\python.exe -m pytest -q
```

Couvre les modules purs (sans BlueSky ni reseau) : atc_callsign, readback,
03_bluesky_connector, graph_secteur, atc_ai (parseur a regles de reference),
les helpers geometriques de atc_sim, la notation d'exercice (atc_exercise),
le pretraitement VHF (atc_audio), l'attribution des voix (voices) et le client
API OpenAI-compatible (ai_client, reseau entierement mocke).
