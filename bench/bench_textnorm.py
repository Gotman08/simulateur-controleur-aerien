"""
Normalisation texte radio pour les metriques ALLER-RETOUR (TTS/E2E)
===================================================================
Le protocole WER historique du projet (BasicTextNormalizer) ne convertit pas
les nombres : une hypothese STT en chiffres (« 100 ») face a une reference en
phraseologie (« one zero zero ») gonfle artificiellement le WER aller-retour.

norm_radio() applique une normalisation SEMANTIQUE symetrique (reference ET
hypothese) : EnglishTextNormalizer de Whisper (nombres epeles -> chiffres,
casse, ponctuation) + « niner » -> nine en amont + recollage des lettres
epelees isolees (« a f r 1234 » -> « afr 1234 »).

Ce module ne remplace PAS le protocole WER du STT (stt_bench), qui reste
celui du projet pour comparabilite historique : il sert uniquement aux
metriques d'intelligibilite (tts_bench) et d'attribution d'echec (e2e_bench).
"""
from __future__ import annotations

import re

from transformers.models.whisper.english_normalizer import EnglishTextNormalizer

_EN = EnglishTextNormalizer({})


def norm_radio(text):
    t = re.sub(r"\bniner\b", "nine", str(text or ""), flags=re.I)
    t = _EN(t)
    # « a f r 1234 » -> « afr 1234 » (lettres epelees recollees)
    while re.search(r"\b([a-z]) ([a-z])\b", t):
        t = re.sub(r"\b([a-z]) ([a-z])\b", r"\1\2", t)
    return t


if __name__ == "__main__":
    for s in ["climb flight level one zero zero, air france one two three four",
              "heading zero niner zero", "A F R one two three four climb F L three two zero",
              "AFR1234 climb FL320"]:
        print(f"{s!r} -> {norm_radio(s)!r}")
