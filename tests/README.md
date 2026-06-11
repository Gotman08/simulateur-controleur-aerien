# Tests unitaires

Lancer depuis la racine du projet :

```
src\bluesky-env\Scripts\python.exe -m pytest -q
```

Couvre les modules purs (sans BlueSky) : atc_callsign, readback, 03_bluesky_connector,
graph_secteur, atc_ai (repli local) et les helpers geometriques de atc_sim.
