"""
Pre-traitement audio VHF partage - Semaine 4
============================================
Reprend la chaine validee en Semaine 2 (cf. 01_audio_preprocessing.py) :
augmentation aleatoire (gain + bruit additif) PUIS filtre passe-bande de
Butterworth 300-3400 Hz (bande passante d'une radio aero).

Les deux fonctions de base (vhf_bandpass, augment) sont reprises a l'identique
de la S2 ; on n'importe pas directement 01_audio_preprocessing.py pour eviter
sa dependance matplotlib et son nom de module non importable (commence par "01_").

Utilise par 06 (preparation), 07 (baseline) et 08 (fine-tuning).
"""
import numpy as np
from scipy.signal import butter, sosfilt

FS = 16000                          # frequence d'echantillonnage Whisper
LOWCUT, HIGHCUT = 300.0, 3400.0     # bande passante radio VHF aeronautique
ORDER = 6


def vhf_bandpass(lowcut=LOWCUT, highcut=HIGHCUT, fs=FS, order=ORDER):
    """Filtre passe-bande de Butterworth (sections du 2nd ordre). [repris S2]"""
    nyq = 0.5 * fs
    return butter(order, [lowcut / nyq, highcut / nyq], btype="band", output="sos")


def augment(signal, rng, snr_db=12.0):
    """Gain leger aleatoire + bruit blanc additif a un SNR donne. [repris S2]"""
    gain = rng.uniform(0.8, 1.2)
    sig = signal * gain
    p_sig = np.mean(sig ** 2) + 1e-12
    p_noise = p_sig / (10 ** (snr_db / 10))
    noise = rng.normal(0.0, np.sqrt(p_noise), size=sig.shape)
    return sig + noise


# SOS calcule une seule fois (le filtre ne depend pas du signal)
_SOS = vhf_bandpass()


def preprocess_waveform(x, training=False, rng=None, snr_range=(5.0, 20.0)):
    """
    Applique la chaine S2 a une forme d'onde 16 kHz mono (np.float32 dans [-1, 1]).

    training=True  : augmentation aleatoire (SNR tire dans snr_range) PUIS bande passante.
    training=False : bande passante seule (cohérence domaine VHF en éval).
    """
    x = np.asarray(x, dtype=np.float32)
    if training:
        if rng is None:
            rng = np.random.default_rng()
        snr_db = float(rng.uniform(*snr_range))
        x = augment(x, rng, snr_db=snr_db)
    x = sosfilt(_SOS, x).astype(np.float32)
    # renormalisation douce pour eviter tout clipping apres filtrage/augmentation
    peak = np.max(np.abs(x)) + 1e-9
    if peak > 1.0:
        x = x / peak
    return x
