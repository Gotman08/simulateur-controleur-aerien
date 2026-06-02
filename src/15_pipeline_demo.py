"""
Preuve - Semaine 5 (U6) : demonstration du pipeline complet
===========================================================
Chaine bout-en-bout d'une brique vocale a la commande simulateur :
   audio -> Whisper fine-tune (S4) -> interpret() RAG+Mistral (S5)
         -> JSON {callsign, action, value} -> json_to_trafscript (03) -> BlueSky

A lancer sur un noeud armgpu (GPU).
  python 15_pipeline_demo.py                 # sur des extraits ATCO2 tenus a l'ecart
  python 15_pipeline_demo.py --wav extrait.wav
"""
import os
import json
import argparse

os.environ.setdefault("HF_HOME", "/gpfs/projet/r250127/hf_cache")

import atc_asr
import atc_llm


def show_chain(idx, ref, stt_text, res):
    print(f"\n=== [{idx}] PIPELINE ===")
    if ref is not None:
        print(f"  reference   : {ref}")
    print(f"  1) Whisper  : {stt_text}")
    print(f"  2) JSON RAG : {json.dumps(res['orders'], ensure_ascii=False)}")
    print(f"  3) BlueSky (TrafScript) :")
    if res["valid"]:
        for v in res["valid"]:
            print(f"        {v['trafscript']}")
    else:
        print("        (aucun ordre exploitable)")
    if res["rejected"]:
        print(f"     rejets securite : {[rj['erreur'] for rj in res['rejected']]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--adapter", default=os.path.join(atc_llm.WORK, "outputs", "lora_small", "adapter"))
    ap.add_argument("--wav", default=None)
    args = ap.parse_args()

    import torch
    r = atc_llm.Retriever()
    proc, wmodel = atc_asr.build_inference_model("openai/whisper-small", adapter_path=args.adapter)

    if args.wav:
        import librosa
        wav, _ = librosa.load(args.wav, sr=atc_asr.FS, mono=True)
        stt = atc_asr.transcribe_arrays(wmodel, proc, [wav], bandpass=True)[0]
        del wmodel
        torch.cuda.empty_cache()
        res = atc_llm.interpret(stt, r)
        show_chain(1, None, stt, res)
        print("\n[U6] pipeline (fichier) termine.")
        return

    import atc_data
    ds = atc_data.load_splits()["test"].select(range(args.n))
    arrays = [ex["array"] for ex in ds["audio"]]
    normalizer = atc_asr.get_normalizer()
    refs = [normalizer(t) for t in ds["text"]]
    stts = atc_asr.transcribe_arrays(wmodel, proc, arrays, bandpass=True)
    del wmodel
    torch.cuda.empty_cache()

    n_cmd = 0
    for i, (ref, stt) in enumerate(zip(refs, stts), 1):
        res = atc_llm.interpret(stt, r)
        n_cmd += len(res["valid"])
        show_chain(i, ref, stt, res)
    print(f"\n[U6] {args.n} extraits -> {n_cmd} commandes BlueSky generees. Pipeline complet OK.")


if __name__ == "__main__":
    main()
