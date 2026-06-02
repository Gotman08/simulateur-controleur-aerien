#!/usr/bin/env bash
# =====================================================================
#  Semaines 6&8 (V4) : installation de BlueSky sur le PC local (Windows)
#  venv Python 3.12 dedie + bluesky-simulator. A lancer en Git Bash :
#    bash setup_bluesky_local.sh
# =====================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$HERE/bluesky-env"

echo "[*] creation venv py3.12 : $VENV"
py -3.12 -m venv "$VENV"
PY="$VENV/Scripts/python.exe"

echo "[*] mise a jour pip + installation bluesky-simulator..."
"$PY" -m pip install --upgrade pip
"$PY" -m pip install bluesky-simulator numpy scipy requests soundfile

echo "[*] version BlueSky :"
"$PY" - <<'PYEOF'
import bluesky as bs
print("  bluesky", getattr(bs, "__version__", "?"))
print("  modules:", [m for m in ("init","stack","sim","traf","net") if hasattr(bs, m)])
PYEOF
echo "[OK] BlueSky installe (V4)."
