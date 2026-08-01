"""
Capture de l'environnement logiciel exact -> bench/results/versions.json
========================================================================
Source du tableau de reproductibilite de l'article (tab_versions).
Execution :  bench\\bench-env\\Scripts\\python.exe bench\\capture_versions.py
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "versions.json")

try:
    import torch
    _lib = os.path.join(os.path.dirname(torch.__file__), "lib")
    if os.name == "nt" and os.path.isdir(_lib):
        os.add_dll_directory(_lib)
except ImportError:
    torch = None


def main():
    v = {"Python (bench)": sys.version.split()[0],
         "OS": f"{platform.system()} {platform.release()}"}
    mods = ["torch", "transformers", "peft", "datasets", "faster_whisper",
            "ctranslate2", "llama_cpp", "kokoro_onnx", "onnxruntime", "jiwer",
            "numpy", "scipy", "soundfile", "fastapi", "requests"]
    for m in mods:
        try:
            mod = __import__(m)
            v[m] = getattr(mod, "__version__", "?")
        except Exception:
            pass
    if torch is not None and torch.cuda.is_available():
        v["GPU (local)"] = torch.cuda.get_device_name(0)
        v["CUDA (torch)"] = torch.version.cuda
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=driver_version",
                              "--format=csv,noheader"], capture_output=True,
                             text=True, timeout=10)
        v["Pilote NVIDIA"] = out.stdout.strip()
    except Exception:
        pass
    # venv application (BlueSky)
    app_py = os.path.join(os.path.dirname(HERE), "src", "bluesky-env",
                          "Scripts", "python.exe")
    if os.path.exists(app_py):
        try:
            out = subprocess.run(
                [app_py, "-c",
                 "import sys, bluesky, numpy; import importlib.metadata as im; "
                 "print(sys.version.split()[0]); "
                 "print(im.version('bluesky-simulator')); print(numpy.__version__)"],
                capture_output=True, text=True, timeout=120)
            lines = out.stdout.split()
            if len(lines) >= 3:
                v["Python (app)"] = lines[0]
                v["bluesky-simulator"] = lines[1]
                v["numpy (app)"] = lines[2]
        except Exception:
            pass
    # modeles GGUF utilises (tailles en Go, provenance)
    mdl = os.path.join(HERE, "models")
    if os.path.isdir(mdl):
        ggufs = sorted(f for f in os.listdir(mdl) if f.endswith(".gguf"))
        v["Modeles GGUF (Q4_K_M)"] = ", ".join(
            f"{g.replace('.gguf', '')} ({os.path.getsize(os.path.join(mdl, g)) / 1e9:.2f} Go)"
            for g in ggufs)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(v, f, indent=1, ensure_ascii=False)
    print(f"[OK] versions -> {OUT}")
    for k, val in v.items():
        print(f"  {k}: {val}")


if __name__ == "__main__":
    main()
