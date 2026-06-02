"""
Preuve - Semaine 4 (T3/T4/T5) : fine-tuning LoRA de Whisper pour l'ATC
======================================================================
Adapte openai/whisper-small a la phraseologie ATC + bruit VHF, par PEFT/LoRA.

Points cles (caveat input_features de la S2/S9) :
  - L'encodeur Whisper consomme des spectrogrammes (input_features), pas des
    input_ids. On utilise donc un DataCollator dedie qui pad SEPAREMENT les
    input_features (feature_extractor) et les labels (tokenizer).
  - LoRA cible les couches d'ATTENTION (q_proj, v_proj) encodeur+decodeur ;
    on n'altere pas les embeddings d'entree.
  - Pre-traitement S2 applique a l'extraction de features : augmentation
    aleatoire (train) + bande passante VHF (toujours).
  - Modele petit + GPU 96 Go => pas de gradient checkpointing par defaut
    (evite le piege PEFT+GC sur enable_input_require_grads).

Modes :
  --overfit            : sur-apprentissage sur un mini-set (porte de validation T3)
  --max-steps N        : run court (T4)
  (defaut)             : entrainement complet (T5)

A lancer sur un noeud armgpu. Sortie : <outputs>/<run>/adapter (+ processor).
"""
import os
import sys
import json
import argparse
from dataclasses import dataclass
from typing import Any, Dict, List, Union

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("HF_HOME", os.path.join(WORK, "hf_cache"))

import numpy as np
import torch
import multiprocessing as _mp

# Les workers DataLoader doivent utiliser 'spawn' : avec 'fork' (defaut Linux),
# forker apres l'init CUDA + le decodeur audio torchcodec (threads) -> deadlock
# (GPU a 0 %, job bloque). 'spawn' = process propres. Necessite une transform
# picklable (classe WhisperTransform, et non une closure).
try:
    _mp.set_start_method("spawn", force=True)
except RuntimeError:
    pass

from atc_audio import preprocess_waveform, FS
from atc_asr import get_normalizer, compute_wer


# ---------------------------------------------------------------------------
@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    """Collator Whisper : pad input_features et labels SEPAREMENT (caveat S2)."""
    processor: Any
    decoder_start_token_id: int

    def __call__(self, features: List[Dict[str, Union[List[int], np.ndarray]]]) -> Dict[str, torch.Tensor]:
        input_features = [{"input_features": f["input_features"]} for f in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")
        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")
        labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
        # retire le token BOS s'il a ete ajoute (il sera re-prepend par le modele)
        if (labels[:, 0] == self.decoder_start_token_id).all().cpu().item():
            labels = labels[:, 1:]
        batch["labels"] = labels
        return batch


class WhisperTransform:
    """Transforme a la volee : pre-traitement S2 -> log-mel input_features + labels.
    Classe (et non closure) pour etre picklable -> compatible workers 'spawn'."""

    def __init__(self, processor, normalizer, training: bool):
        self.fe = processor.feature_extractor
        self.tok = processor.tokenizer
        self.normalizer = normalizer
        self.training = training

    def __call__(self, batch):
        feats, labels = [], []
        for a, txt in zip(batch["audio"], batch["text"]):
            x = np.asarray(a["array"], dtype=np.float32)
            rng = np.random.default_rng() if self.training else None
            x = preprocess_waveform(x, training=self.training, rng=rng)
            feats.append(self.fe(x, sampling_rate=FS).input_features[0])
            labels.append(self.tok(self.normalizer(txt)).input_ids)
        return {"input_features": feats, "labels": labels}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(WORK, "data_proc"))
    ap.add_argument("--model", default="openai/whisper-small")
    ap.add_argument("--run-name", default="lora_small")
    ap.add_argument("--outputs", default=os.path.join(WORK, "outputs"))
    ap.add_argument("--lora-r", type=int, default=32)
    ap.add_argument("--lora-alpha", type=int, default=64)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--train-bs", type=int, default=48)     # GH200 96 Go : large batch
    ap.add_argument("--eval-bs", type=int, default=24)
    ap.add_argument("--grad-accum", type=int, default=1)
    ap.add_argument("--num-epochs", type=float, default=3.0)
    ap.add_argument("--max-steps", type=int, default=-1)
    ap.add_argument("--warmup", type=int, default=50)
    ap.add_argument("--eval-steps", type=int, default=250)
    ap.add_argument("--save-steps", type=int, default=250)
    ap.add_argument("--logging-steps", type=int, default=25)
    ap.add_argument("--num-workers", type=int, default=16)   # goulot = decode+mel CPU
    ap.add_argument("--eval-subset", type=int, default=400,  help="cap val pour eval rapide")
    ap.add_argument("--gen-max-len", type=int, default=100)
    ap.add_argument("--grad-checkpointing", action="store_true")
    ap.add_argument("--overfit", action="store_true", help="sur-apprend un mini-set (T3)")
    ap.add_argument("--overfit-n", type=int, default=16)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    import atc_data
    from transformers import (WhisperProcessor, WhisperForConditionalGeneration,
                              Seq2SeqTrainer, Seq2SeqTrainingArguments)
    from peft import LoraConfig, get_peft_model

    assert torch.cuda.is_available(), "GPU requis (noeud armgpu)"
    normalizer = get_normalizer()
    processor = WhisperProcessor.from_pretrained(args.model, language="en", task="transcribe")

    # --- donnees (construites a la volee depuis le cache HF, sans copie disque) ---
    dd = atc_data.load_splits()
    if args.overfit:
        small = dd["train"].select(range(min(args.overfit_n, len(dd["train"]))))
        train_ds = small.with_transform(WhisperTransform(processor, normalizer, False))  # memorisation
        eval_ds = small.with_transform(WhisperTransform(processor, normalizer, False))
        if args.max_steps < 0:
            args.max_steps = 200
        args.eval_steps = args.save_steps = 50
        args.warmup = 10
        args.train_bs = min(args.train_bs, args.overfit_n)
        print(f"[T3] mode OVER-FIT : {len(small)} extraits, max_steps={args.max_steps}")
    else:
        val = dd["val"]
        if args.eval_subset and len(val) > args.eval_subset:
            val = val.select(range(args.eval_subset))   # eval rapide pendant l'entrainement
        train_ds = dd["train"].with_transform(WhisperTransform(processor, normalizer, True))
        eval_ds = val.with_transform(WhisperTransform(processor, normalizer, False))
        print(f"[*] train={len(dd['train'])}  val(eval)={len(val)}/{len(dd['val'])}")

    # --- modele + LoRA -------------------------------------------------------
    # fp32 : l'entrainement utilise bf16 via autocast (bf16=True) ; l'eval (generate)
    # tourne en fp32 -> evite le conflit dtype input_features(float)/poids(bf16).
    model = WhisperForConditionalGeneration.from_pretrained(args.model)
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []
    model.config.use_cache = False
    model.generation_config.language = "en"
    model.generation_config.task = "transcribe"
    model.generation_config.forced_decoder_ids = None
    if args.grad_checkpointing:
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()   # indispensable pour PEFT + GC

    lora = LoraConfig(r=args.lora_r, lora_alpha=args.lora_alpha,
                      lora_dropout=args.lora_dropout,
                      target_modules=["q_proj", "v_proj"], bias="none")
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    collator = DataCollatorSpeechSeq2SeqWithPadding(
        processor=processor, decoder_start_token_id=model.config.decoder_start_token_id)

    # --- metrique WER --------------------------------------------------------
    def compute_metrics(pred):
        pred_ids = pred.predictions
        label_ids = pred.label_ids
        label_ids = np.where(label_ids == -100, processor.tokenizer.pad_token_id, label_ids)
        pred_str = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        label_str = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)
        pred_str = [normalizer(s) for s in pred_str]
        label_str = [normalizer(s) for s in label_str]
        return {"wer": 100.0 * compute_wer(label_str, pred_str)}

    run_dir = os.path.join(args.outputs, args.run_name)
    targs = Seq2SeqTrainingArguments(
        output_dir=run_dir,
        per_device_train_batch_size=args.train_bs,
        per_device_eval_batch_size=args.eval_bs,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        warmup_steps=args.warmup,
        num_train_epochs=args.num_epochs,
        max_steps=args.max_steps,
        bf16=True,
        gradient_checkpointing=args.grad_checkpointing,
        predict_with_generate=True,
        generation_max_length=args.gen_max_len,
        eval_strategy="steps",
        eval_steps=args.eval_steps,
        save_strategy="steps",
        save_steps=args.save_steps,
        save_total_limit=2,
        logging_steps=args.logging_steps,
        report_to=["tensorboard"],
        load_best_model_at_end=True,
        metric_for_best_model="wer",
        greater_is_better=False,
        remove_unused_columns=False,          # requis avec with_transform
        label_names=["labels"],               # requis pour les modeles PEFT
        dataloader_num_workers=args.num_workers,
        dataloader_persistent_workers=(args.num_workers > 0),
        dataloader_prefetch_factor=(4 if args.num_workers > 0 else None),
        dataloader_pin_memory=True,
        seed=args.seed,
    )

    trainer = Seq2SeqTrainer(
        model=model, args=targs,
        train_dataset=train_ds, eval_dataset=eval_ds,
        data_collator=collator, compute_metrics=compute_metrics,
        processing_class=processor,
    )

    print("[*] debut de l'entrainement...")
    trainer.train()
    metrics = trainer.evaluate()
    print(f"[*] eval finale : WER = {metrics.get('eval_wer', float('nan')):.2f} %")

    # --- sauvegarde adapter + processor -------------------------------------
    adapter_dir = os.path.join(run_dir, "adapter")
    trainer.save_model(adapter_dir)            # adapter LoRA (PeftModel)
    processor.save_pretrained(adapter_dir)
    with open(os.path.join(run_dir, "train_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"run": args.run_name, "model": args.model,
                   "overfit": args.overfit, "eval_wer": metrics.get("eval_wer"),
                   "lora_r": args.lora_r, "lr": args.lr}, f, indent=2)
    print(f"[OK] adapter sauvegarde : {adapter_dir}")
    tag = "T3 over-fit" if args.overfit else "entrainement"
    print(f"\n[{tag}] termine. WER eval = {metrics.get('eval_wer', float('nan')):.2f} %")


if __name__ == "__main__":
    main()
