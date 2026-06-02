"""
Preuve - Semaine 5 (U1) : construction de l'index vectoriel de la KB phraseo
============================================================================
Embeddings (bge-small) des fiches de regles (kb_oaci.build_documents) et
sauvegarde de l'index : embeddings.npy + docs.json. Recherche = cosinus numpy
(KB petite -> pas de FAISS). Le cache du modele d'embeddings est sur l'espace
projet (HF_HOME).

A lancer sur un noeud armgpu (env aarch64). Sortie : <WORK>/kb/{embeddings.npy, docs.json}
"""
import os
import json

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("HF_HOME", "/gpfs/projet/r250127/hf_cache")   # cache LLM/embeddings = projet

import numpy as np
import kb_oaci

EMB_ID = os.environ.get("ATC_EMB", "BAAI/bge-small-en-v1.5")
KB_DIR = os.path.join(WORK, "kb")


def main():
    docs = kb_oaci.build_documents()
    print(f"[*] {len(docs)} fiches | LIMITS={kb_oaci.LIMITS} | waypoints={kb_oaci.WAYPOINTS}")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMB_ID)
    texts = [d["text"] for d in docs]
    emb = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True).astype("float32")

    os.makedirs(KB_DIR, exist_ok=True)
    np.save(os.path.join(KB_DIR, "embeddings.npy"), emb)
    with open(os.path.join(KB_DIR, "docs.json"), "w", encoding="utf-8") as f:
        json.dump({"emb_model": EMB_ID, "dim": int(emb.shape[1]),
                   "query_instruction": "Represent this sentence for searching relevant passages:",
                   "docs": docs}, f, ensure_ascii=False, indent=2)

    print(f"[U1] {len(docs)} fiches embeddees, dim={emb.shape[1]} -> {KB_DIR}")
    for d in docs:
        print(f"  - [{str(d['action']):6s}] {d['title']}")
    print("[U1] KB construite.")


if __name__ == "__main__":
    main()
