"""
Preuve - Semaine 2 : pré-traitement du signal radio VHF
=======================================================
Chaîne retenue (cf. rapport S2) :
  1. augmentations aléatoires (gain, bruit additif)
  2. filtre passe-bande de Butterworth 300-3400 Hz  <-- bande passante d'une radio aéro

Ce script :
  - définit le filtre,
  - trace sa réponse en fréquence (diagramme de Bode),
  - l'applique à un signal de parole synthétique bruité,
  - trace les spectrogrammes avant / après filtrage.

Exécution :  python 01_audio_preprocessing.py
Sorties   :  fig_butterworth_bode.png, fig_spectrogramme_avant_apres.png
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import butter, sosfilt, sosfreqz, spectrogram

FS = 16000          # fréquence d'échantillonnage (Hz) - standard Whisper
LOWCUT, HIGHCUT = 300.0, 3400.0   # bande passante radio VHF aéronautique
ORDER = 6


def vhf_bandpass(lowcut=LOWCUT, highcut=HIGHCUT, fs=FS, order=ORDER):
    """Filtre passe-bande de Butterworth (sortie en sections du 2nd ordre)."""
    nyq = 0.5 * fs
    sos = butter(order, [lowcut / nyq, highcut / nyq], btype="band", output="sos")
    return sos


def augment(signal, rng, snr_db=12.0):
    """Augmentation aléatoire : gain léger + bruit blanc additif à un SNR donné."""
    gain = rng.uniform(0.8, 1.2)
    sig = signal * gain
    p_sig = np.mean(sig ** 2)
    p_noise = p_sig / (10 ** (snr_db / 10))
    noise = rng.normal(0.0, np.sqrt(p_noise), size=sig.shape)
    return sig + noise


def synth_speech(duration=2.5, fs=FS, seed=0):
    """Signal de parole synthétique : porteuses formantiques modulées."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, duration, int(duration * fs), endpoint=False)
    formants = [350, 900, 2500, 3800]      # 3800 Hz = hors bande -> doit être atténué
    sig = np.zeros_like(t)
    for f0 in formants:
        env = 0.5 * (1 + np.sin(2 * np.pi * rng.uniform(2, 5) * t))
        sig += env * np.sin(2 * np.pi * f0 * t)
    sig += 0.15 * np.sin(2 * np.pi * 60 * t)   # ronflement basse fréquence (hors bande)
    return t, sig / np.max(np.abs(sig))


def plot_bode(sos, fs=FS, path="fig_butterworth_bode.png"):
    w, h = sosfreqz(sos, worN=4096, fs=fs)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(w, 20 * np.log10(np.maximum(np.abs(h), 1e-6)), lw=2, color="#1f4ed8")
    ax.axvline(LOWCUT, color="#d97706", ls="--", lw=1.3, label=f"{int(LOWCUT)} Hz")
    ax.axvline(HIGHCUT, color="#d97706", ls="--", lw=1.3, label=f"{int(HIGHCUT)} Hz")
    ax.axhline(-3, color="grey", ls=":", lw=1, label="-3 dB")
    ax.set_xlim(20, fs / 2)
    ax.set_ylim(-80, 5)
    ax.set_xscale("log")
    ax.set_xlabel("Fréquence (Hz)")
    ax.set_ylabel("Gain (dB)")
    ax.set_title(f"Filtre passe-bande de Butterworth (ordre {ORDER}) - bande VHF 300-3400 Hz")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="lower center", ncol=3, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"[OK] {path}")


def plot_spectrograms(raw, filt, fs=FS, path="fig_spectrogramme_avant_apres.png"):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, data, title in zip(axes, [raw, filt], ["Avant (brut + bruit)", "Après filtrage VHF"]):
        f, tt, Sxx = spectrogram(data, fs=fs, nperseg=512, noverlap=384)
        ax.pcolormesh(tt, f, 10 * np.log10(Sxx + 1e-10), shading="gouraud", cmap="magma")
        ax.axhline(LOWCUT, color="cyan", ls="--", lw=0.8)
        ax.axhline(HIGHCUT, color="cyan", ls="--", lw=0.8)
        ax.set_title(title)
        ax.set_xlabel("Temps (s)")
    axes[0].set_ylabel("Fréquence (Hz)")
    fig.suptitle("Effet du pré-traitement sur un signal de parole bruité", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"[OK] {path}")


def main():
    rng = np.random.default_rng(42)
    sos = vhf_bandpass()
    t, clean = synth_speech(seed=7)
    noisy = augment(clean, rng, snr_db=10.0)
    filtered = sosfilt(sos, noisy)

    plot_bode(sos)
    plot_spectrograms(noisy, filtered)

    # mesure simple : énergie hors-bande supprimée
    def band_energy(x, lo, hi):
        X = np.fft.rfft(x)
        fr = np.fft.rfftfreq(len(x), 1 / FS)
        mask = (fr >= lo) & (fr <= hi)
        return np.sum(np.abs(X[mask]) ** 2)

    tot = band_energy(noisy, 0, FS / 2)
    oob_before = band_energy(noisy, 0, LOWCUT) + band_energy(noisy, HIGHCUT, FS / 2)
    oob_after = band_energy(filtered, 0, LOWCUT) + band_energy(filtered, HIGHCUT, FS / 2)
    print(f"Énergie hors-bande avant : {100*oob_before/tot:5.1f} %")
    print(f"Énergie hors-bande après : {100*oob_after/tot:5.1f} %")
    print(f"Atténuation hors-bande   : {10*np.log10(oob_after/oob_before):5.1f} dB")


if __name__ == "__main__":
    main()
