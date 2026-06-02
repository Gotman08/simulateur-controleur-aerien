"""
Chargement + harmonisation des corpus ATC - Semaine 4 (sans copie disque)
=========================================================================
Construit a la volee un DatasetDict {train, val, test} depuis le cache HF, SANS
save_to_disk ni .map (qui reecriraient toute la table audio -> quota disque).
Le filtrage se fait par select() d'indices (lazy) ; la normalisation du texte se
fait a la consommation (07/08/09/10). Le cache de telechargement HF reste l'unique
copie sur disque.

Sources :
  train/val : Jzuluaga/uwb_atcc[train] + Jzuluaga/atcosim_corpus[train]
  test      : Jzuluaga/atco2_corpus_1h[test]   (repli : uwb_atcc[test])
"""
import os

USER = os.environ.get("USER", "nimarano")
WORK = os.environ.get("ATC_WORK", f"/gpfs/scratch/{USER}/atc-whisper-s4")
os.environ.setdefault("HF_HOME", os.path.join(WORK, "hf_cache"))

TRAIN_SOURCES = {
    "uwb_atcc": ["Jzuluaga/uwb_atcc"],
    "atcosim":  ["Jzuluaga/atcosim_corpus"],
}
TEST_SOURCES = {
    "atco2": ["Jzuluaga/atco2_corpus_1h"],
}
TEXT_CANDIDATES = ("text", "transcription", "sentence", "transcript", "labels")


def detect_text_col(colnames):
    for c in TEXT_CANDIDATES:
        if c in colnames:
            return c
    raise ValueError(f"Aucune colonne texte parmi {TEXT_CANDIDATES} dans {colnames}")


def _load_one(ids, split, source, max_n=None):
    from datasets import load_dataset, Audio
    last = None
    for ds_id in ids:
        try:
            ds = load_dataset(ds_id, split=split)
            tcol = detect_text_col(ds.column_names)
            if tcol != "text":
                ds = ds.rename_column(tcol, "text")
            ds = ds.cast_column("audio", Audio(sampling_rate=16000))
            keep = ("audio", "text", "duration")
            ds = ds.remove_columns([c for c in ds.column_names if c not in keep])
            if max_n:
                ds = ds.select(range(min(max_n, len(ds))))
            ds = ds.add_column("source", [source] * len(ds))
            print(f"[OK] {source:14s} <- {ds_id} [{split}] : {len(ds)} extraits")
            return ds
        except Exception as e:
            last = e
            print(f"[..] {source:14s} {ds_id} [{split}] echec ({type(e).__name__}: {str(e)[:80]})")
    raise RuntimeError(f"Impossible de charger {source} parmi {ids} : {last}")


def _filter_by_indices(ds, min_s=0.4, max_s=30.0):
    """Filtre (texte vide / duree hors bornes) via select() -> aucune reecriture disque."""
    txts = ds["text"]
    durs = ds["duration"] if "duration" in ds.column_names else [None] * len(ds)
    keep = []
    for i, (t, d) in enumerate(zip(txts, durs)):
        if not (t and str(t).strip()):
            continue
        if d is not None and not (min_s <= float(d) <= max_s):
            continue
        keep.append(i)
    print(f"       filtrage : {len(ds)} -> {len(keep)} extraits")
    return ds.select(keep)


def load_splits(max_per_source=None, val_size=0.05, seed=42, min_s=0.4, max_s=30.0):
    """Renvoie un DatasetDict {train, val, test} (lazy, sans copie disque)."""
    from datasets import DatasetDict, concatenate_datasets
    train_parts = []
    for name, ids in TRAIN_SOURCES.items():
        ds = _filter_by_indices(_load_one(ids, "train", name, max_per_source), min_s, max_s)
        train_parts.append(ds)
    train_all = concatenate_datasets(train_parts)

    try:
        test_ds = _load_one(TEST_SOURCES["atco2"], "test", "atco2", max_per_source)
    except Exception:
        print("[!] ATCO2 indisponible -> repli sur UWB-ATCC[test]")
        test_ds = _load_one(TRAIN_SOURCES["uwb_atcc"], "test", "uwb_atcc_test", max_per_source)
    test_ds = _filter_by_indices(test_ds, min_s, max_s)

    sp = train_all.train_test_split(test_size=val_size, seed=seed)
    return DatasetDict(train=sp["train"], val=sp["test"], test=test_ds)
