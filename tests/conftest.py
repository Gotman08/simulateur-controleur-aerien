"""
Configuration pytest commune.
======================================================================
- Insere `src/` dans sys.path pour importer les modules plats du projet.
- Fournit un loader pour les modules a prefixe numerique (ex. 03_bluesky_connector.py)
  qui ne sont pas importables par nom de module classique.

Aucun import de bluesky ici : on ne teste QUE les modules purs. L'import de
`atc_sim` tire `bluesky_runtime` mais PAS `bluesky` tant que `bsk.bs()` n'est
pas appele (verifie : bluesky_runtime n'importe bluesky qu'a l'interieur de bs()).
"""
import os
import sys
import importlib.util

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))

# src en tete de sys.path pour que `import atc_callsign`, `import readback`, etc.
# resolvent les modules plats du projet.
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _load_prefixed(filename, modname):
    """Charge un module a prefixe numerique par chemin de fichier."""
    path = os.path.join(_SRC, filename)
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def bsky_conn():
    """Module 03_bluesky_connector.py charge via importlib (prefixe numerique)."""
    return _load_prefixed("03_bluesky_connector.py", "bsky_conn_test")
