"""
Tests du pretraitement audio VHF (src/atc_audio.py) - module pur numpy/scipy.
============================================================================
Verifie la bande passante 300-3400 Hz (attenuation hors-bande), la forme/typage
de sortie, la reproductibilite de l'augmentation (rng seede) et la robustesse au
signal muet. Aucune dependance GPU/cluster/reseau : 100 % CI.
"""
import numpy as np

import atc_audio


def _tone(freq, n=16000, fs=16000):
    t = np.arange(n) / fs
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def test_constantes():
    assert atc_audio.FS == 16000
    assert atc_audio.LOWCUT == 300.0 and atc_audio.HIGHCUT == 3400.0


def test_bandpass_attenue_hors_bande():
    """60 Hz (sous la bande) fortement attenue vs 1000 Hz (dans la bande)."""
    low = atc_audio.preprocess_waveform(_tone(60), training=False)
    mid = atc_audio.preprocess_waveform(_tone(1000), training=False)
    e_low = float(np.mean(low ** 2))
    e_mid = float(np.mean(mid ** 2))
    assert e_mid > e_low * 50.0          # ~ -47 dB hors bande (cf. audit)


def test_sortie_typage_forme_finie():
    x = _tone(1000, n=8000)
    y = atc_audio.preprocess_waveform(x, training=False)
    assert y.dtype == np.float32
    assert y.shape == x.shape
    assert np.all(np.isfinite(y))


def test_pas_de_clipping():
    y = atc_audio.preprocess_waveform(_tone(1000) * 3.0, training=False)
    assert float(np.max(np.abs(y))) <= 1.0 + 1e-6


def test_augmentation_reproductible_avec_rng_seede():
    x = _tone(1000, n=4000)
    y1 = atc_audio.preprocess_waveform(x, training=True, rng=np.random.default_rng(0))
    y2 = atc_audio.preprocess_waveform(x, training=True, rng=np.random.default_rng(0))
    assert np.allclose(y1, y2)


def test_signal_muet_ne_plante_pas():
    y = atc_audio.preprocess_waveform([0.0] * 100, training=True,
                                      rng=np.random.default_rng(1))
    assert np.all(np.isfinite(y))
