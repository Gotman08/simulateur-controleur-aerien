"""
Compat XTTS / transformers 5.x - Semaine 6
==========================================
coqui-tts (XTTS) importe des symboles supprimes dans transformers 5.x (ex.
`isin_mps_friendly`). On les restaure AVANT d'importer TTS, sans toucher a l'env
(qui doit garder transformers 5.9 pour Whisper/Mistral).
"""


def patch():
    try:
        import torch
        import transformers.pytorch_utils as pu
    except Exception:
        return
    if not hasattr(pu, "isin_mps_friendly"):
        def isin_mps_friendly(elements, test_elements):
            return torch.isin(elements, test_elements)
        pu.isin_mps_friendly = isin_mps_friendly
