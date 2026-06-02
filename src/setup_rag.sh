#!/usr/bin/env bash
# =====================================================================
#  Stage IA & Controle Aerien - Semaine 5 (U0) : setup RAG sur ROMEO
#  Reutilise l'env conda de la S4 ; ajoute sentence-transformers + pypdf.
#  Telecharge le LLM (Mistral-7B-Instruct) + l'embedder (bge-small) dans le
#  cache HF de l'ESPACE PROJET (le 7B ne tient pas dans le quota scratch 20 Go).
#  A LANCER sur un noeud armgpu (GPU). Auteur : Nicolas Marano
# =====================================================================
set -euo pipefail

USER_NAME="$(whoami)"
ENV="/gpfs/scratch/${USER_NAME}/atc-whisper-s4/env"     # env S4 reutilise
export HF_HOME="/gpfs/projet/r250127/hf_cache"          # cache LLM sur projet (20 Go)
export PIP_CACHE_DIR="/gpfs/scratch/${USER_NAME}/atc-whisper-s4/pip_cache"
export TRANSFORMERS_VERBOSITY=error
export HF_HUB_DISABLE_PROGRESS_BARS=1
LLM_ID="${ATC_LLM:-mistralai/Mistral-7B-Instruct-v0.3}"
EMB_ID="${ATC_EMB:-BAAI/bge-small-en-v1.5}"

echo "[*] noeud=$(hostname) arch=$(uname -m)"
echo "[*] HF_HOME=$HF_HOME | LLM=$LLM_ID | EMB=$EMB_ID"
mkdir -p "$HF_HOME"

source "$HOME/miniforge3/etc/profile.d/conda.sh"
conda activate "$ENV"

echo "[*] Installation sentence-transformers + pypdf..."
python -m pip install -q "sentence-transformers>=3.0" pypdf

echo "[*] Versions :"
python - <<'PY'
import torch, transformers, sentence_transformers
print("  torch", torch.__version__, "| cuda", torch.cuda.is_available(),
      "|", (torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no-gpu"))
print("  transformers", transformers.__version__, "| sentence-transformers", sentence_transformers.__version__)
PY

echo "[*] Embedder (bge-small) : telechargement + smoke..."
python - <<'PY'
import os
from sentence_transformers import SentenceTransformer
m = SentenceTransformer(os.environ.get("ATC_EMB", "BAAI/bge-small-en-v1.5"))
v = m.encode(["climb to flight level three five zero", "turn right heading two seven zero"],
             normalize_embeddings=True)
print("  embeddings shape:", v.shape)
print("  [U0] embedder OK")
PY

echo "[*] LLM (Mistral) : sonde de gating (tokenizer) puis poids + smoke..."
python - <<'PY'
import os, sys, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
mid = os.environ.get("ATC_LLM", "mistralai/Mistral-7B-Instruct-v0.3")
try:
    tok = AutoTokenizer.from_pretrained(mid)          # petit : sonde de gating
except Exception as e:
    print("  [GATING/ERREUR] tokenizer:", type(e).__name__, str(e)[:180])
    print("  -> Modele probablement 'gated'. Accepter la licence sur huggingface.co/" + mid)
    print("     puis exporter HF_TOKEN (ou choisir un LLM ouvert via ATC_LLM=...).")
    sys.exit(2)
model = AutoModelForCausalLM.from_pretrained(mid, torch_dtype=torch.bfloat16, device_map="cuda")
msgs = [{"role": "user", "content": "Reply with exactly the word: READY"}]
enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                              return_dict=True).to("cuda")   # transformers 5.x : dict, pas tenseur
out = model.generate(**enc, max_new_tokens=8, do_sample=False)
print("  LLM ->", tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True).strip())
print("  [U0] LLM OK")
PY

echo "[OK] Setup RAG termine (U0)."
