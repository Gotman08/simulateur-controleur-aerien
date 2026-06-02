"""
Vacation de controle - boucle VOIX complete, instructions en continu
====================================================================
Plusieurs instructions ATC *parlees* (synthese voix clonee + VHF sur ROMEO)
arrivent au fil du temps ; pour chacune :
   /tts -> audio -> /asr (re-transcription) -> /interpret -> TrafScript -> BlueSky.
Les avions devient progressivement. Rendu : GIF radar (balayage) + journal de
session (PARLE / ASR / WER / commande) + audios sess_*.wav.

Prerequis : tunnel + serveur actifs. Lancer : bluesky-env/Scripts/python.exe live_voice_session.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

import bluesky_runtime as bsk
import radar_anim as R
import pipeline_e2e as P        # tts(), asr(), interpret(), wer()
import live_demo as Ld          # navdata()

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_out")

FLEET = [   # tous cap 090 dans le secteur Reims
    ("AFR1234", "A320", 49.55, 3.50, 90, 13000, 250),
    ("BAW57",   "B738", 49.05, 3.70, 90, 20000, 300),
    ("RYR9",    "B738", 48.80, 4.10, 90, 10000, 240),
    ("DLH88",   "A319", 49.35, 4.50, 90, 16000, 270),
]
# (frame d'emission, instruction parlee, voix de reference)
SESSION = [
    (2,  "air france one two three four descend flight level one zero zero", "pilot_1.wav"),
    (5,  "speedbird five seven turn right heading one eight zero", "pilot_1.wav"),
    (8,  "ryanair niner climb flight level two four zero", "pilot_1.wav"),
    (11, "lufthansa eight eight turn left heading three six zero", "pilot_1.wav"),
]
NFRAMES, DT = 18, 20


def snap_frame(cs_set):
    out = {}
    for s in bsk.state():
        if s["id"] in cs_set:
            x, y = R.to_nm(s["lat"], s["lon"])
            gs = s.get("tas_kt") or s.get("cas_kt") or 0
            out[s["id"]] = (x, y, s["hdg"], s["alt_ft"], gs)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    wpts, apts, routes, sector = Ld.navdata()
    cs_set = {c for c, *_ in FLEET}
    bsk.bs(); bsk.reset()
    for cs, *a in FLEET:
        bsk.create(cs, *a)

    sched = {f: (txt, v) for f, txt, v in SESSION}
    frames, banner, log = [], [""] * (NFRAMES + 4), []
    print(f"[*] serveur {P.SERVER} (asr/llm) + {P.TTS_SERVER} (tts)")
    print("=== VACATION DE CONTROLE (boucle voix complete) ===")
    for f in range(NFRAMES):
        if f in sched:
            txt, voice = sched[f]
            wav = P.tts(txt, voice, vhf=True)                 # voix clonee + VHF (ROMEO)
            with open(os.path.join(OUT, f"sess_{f:02d}.wav"), "wb") as fh:
                fh.write(wav)
            stt = P.asr(wav)                                  # re-transcription (boucle)
            res = P.interpret(stt)                            # interpretation ancree
            for line in res["trafscript"]:
                bsk.cmd(line)
            w = P.wer(txt, stt)
            log.append((f, txt, stt, w, res["trafscript"]))
            lab = " ; ".join(res["trafscript"]) or "(aucun ordre)"
            for k in range(f, min(f + 3, NFRAMES + 3)):
                banner[k] = lab
            print(f"  t={f*DT:03d}s PARLE: \"{txt}\"")
            print(f"           ASR : \"{stt}\"  (WER {w*100:.0f}%)")
            print(f"           CMD : {res['trafscript']}")
        frames.append(snap_frame(cs_set))
        bsk.advance(DT)

    print("\n=== DEVIATIONS finales (cap / FL) ===")
    for cs in cs_set:
        b, a = frames[1][cs], frames[-1][cs]
        print(f"  {cs}: hdg {b[2]:.0f}->{a[2]:.0f} | FL {int(round(b[3]/100)):03d}->{int(round(a[3]/100)):03d}")
    if log:
        print(f"\n  WER moyen re-transcription : {100*sum(x[3] for x in log)/len(log):.0f} %")

    # GIF balayage avec bandeau d'instruction
    figA, axA = plt.subplots(figsize=(9.5, 9.5)); figA.patch.set_facecolor(R.BG)

    def upd(f):
        axA.clear(); R.draw_static(axA, wpts, apts, routes, sector)
        R.draw_aircraft(axA, frames, f); R.draw_sweep(axA, (f * 26) % 360)
        axA.set_title(f"CTR REIMS  -  vacation  t={f*DT:03d}s", color=R.GREEN, fontsize=11)
        if banner[f]:
            axA.text(0, -R.RANGE_NM * 1.06, f">> {banner[f]}", color="#ffae42",
                     fontsize=10, ha="center", va="top", fontfamily="monospace")
        return []

    FuncAnimation(figA, upd, frames=len(frames), interval=220).save(
        os.path.join(OUT, "radar_session.gif"), writer=PillowWriter(fps=5),
        savefig_kwargs={"facecolor": R.BG})
    print(f"\n[OK] {os.path.join(OUT, 'radar_session.gif')}  + audios sess_*.wav")


if __name__ == "__main__":
    main()
