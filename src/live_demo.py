"""
Demo d'interaction LIVE : les instructions ATC font devier les avions
=====================================================================
4 avions volent droit (cap 090). On envoie des instructions ATC en langage
naturel au pipeline ROMEO (/interpret) ; les commandes TrafScript produites sont
appliquees a BlueSky -> les avions DEVIENT. Rendu radar avant/apres + GIF.

Prouve la chaine complete : instruction -> Mistral+RAG (ROMEO) -> JSON -> BlueSky.
Prerequis : tunnel + serveur actifs. Lancer : bluesky-env/Scripts/python.exe live_demo.py
"""
import os
import numpy as np
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

import bluesky_runtime as bsk
import radar_anim as R                      # rendu radar Reims (draw_static/aircraft/sweep, to_nm)

SERVER = os.environ.get("ATC_SERVER", "http://localhost:8765")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_out")

FLEET = [   # tous cap 090 (vol droit vers l'est), repartis dans le secteur Reims
    ("AFR1234", "A320", 49.55, 3.50, 90, 12000, 250),
    ("BAW57",   "B738", 49.05, 3.70, 90, 20000, 300),
    ("RYR9",    "B738", 48.80, 4.10, 90, 9000,  240),
    ("DLH88",   "A319", 49.35, 4.50, 90, 16000, 270),
]
INSTR = [   # instructions ATC en langage naturel
    "air france one two three four turn left heading three six zero",
    "speedbird five seven turn right heading one eight zero",
    "ryanair niner climb flight level two four zero",
    "lufthansa eight eight descend flight level one zero zero",
]
PHASE1, PHASE2, DT = 5, 18, 20


def interpret(text):
    r = requests.post(f"{SERVER}/interpret", json={"text": text}, timeout=120)
    r.raise_for_status()
    return r.json()


def navdata():
    nav = bsk.bs().navdb
    wpts = []
    if getattr(nav, "wplat", None) is not None:
        wplat, wplon, wpid = np.asarray(nav.wplat), np.asarray(nav.wplon), list(nav.wpid)
        m = (np.abs(wplat - R.CLAT) < 1.0) & (np.abs(wplon - R.CLON) < 1.5)
        seen = set()
        for i in np.where(m)[0]:
            nm = str(wpid[i])
            if len(nm) == 5 and nm.isalpha() and nm not in seen:
                seen.add(nm); wpts.append((*R.to_nm(wplat[i], wplon[i]), nm))
            if len(wpts) >= 24:
                break
    apts = []
    if getattr(nav, "aptlat", None) is not None:
        aptlat, aptlon, aptid = np.asarray(nav.aptlat), np.asarray(nav.aptlon), list(nav.aptid)
        m = (np.abs(aptlat - R.CLAT) < 0.9) & (np.abs(aptlon - R.CLON) < 1.3)
        for i in np.where(m)[0][:8]:
            apts.append((*R.to_nm(aptlat[i], aptlon[i]), str(aptid[i])))
    routes = set()
    P = [(x, y) for x, y, _ in wpts]
    for i, (xi, yi) in enumerate(P):
        d = sorted(range(len(P)), key=lambda j: (P[j][0] - xi) ** 2 + (P[j][1] - yi) ** 2)
        for j in d[1:3]:
            if (P[j][0] - xi) ** 2 + (P[j][1] - yi) ** 2 < 45 ** 2:
                routes.add(tuple(sorted((i, j))))
    return wpts, apts, list(routes), R.sector_polygon()


def snap_frame():
    out = {}
    for s in bsk.state():
        if s["id"] in {c for c, *_ in FLEET}:
            x, y = R.to_nm(s["lat"], s["lon"])
            gs = s.get("tas_kt") or s.get("cas_kt") or 0
            out[s["id"]] = (x, y, s["hdg"], s["alt_ft"], gs)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    wpts, apts, routes, sector = navdata()
    bsk.bs(); bsk.reset()
    for cs, *a in FLEET:
        bsk.create(cs, *a)

    frames = []
    for _ in range(PHASE1):                 # vol droit
        frames.append(snap_frame()); bsk.advance(DT)
    cmd_frame = len(frames)

    print(f"[*] serveur {SERVER} | health {requests.get(SERVER+'/health', timeout=20).json().get('role')}")
    print("=== INSTRUCTIONS ATC -> pipeline -> commandes BlueSky ===")
    for instr in INSTR:                     # interaction LIVE via le pipeline
        res = interpret(instr)
        for line in res["trafscript"]:
            bsk.cmd(line)
        print(f"  \"{instr}\"\n      -> {res['trafscript']}")

    for _ in range(PHASE2):                 # les avions devient
        frames.append(snap_frame()); bsk.advance(DT)

    # deltas de cap/altitude (preuve chiffree)
    print("\n=== DEVIATIONS (cap/altitude avant -> apres) ===")
    for cs in [c for c, *_ in FLEET]:
        b, a = frames[cmd_frame - 1][cs], frames[-1][cs]
        print(f"  {cs}: hdg {b[2]:.0f}->{a[2]:.0f}  | FL {int(round(b[3]/100)):03d}->{int(round(a[3]/100)):03d}")

    # avant / apres
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(20, 10)); fig.patch.set_facecolor(R.BG)
    R.draw_static(a1, wpts, apts, routes, sector); R.draw_aircraft(a1, frames, cmd_frame - 1)
    a1.set_title("AVANT  -  vol droit (cap 090)", color=R.GREEN, fontsize=13)
    R.draw_static(a2, wpts, apts, routes, sector); R.draw_aircraft(a2, frames, len(frames) - 1)
    a2.set_title("APRES  -  deviations commandees par le pipeline", color=R.GREEN, fontsize=13)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "radar_live_beforeafter.png"), dpi=140, facecolor=R.BG)
    plt.close(fig)
    print(f"\n[OK] {os.path.join(OUT, 'radar_live_beforeafter.png')}")

    # GIF balayage
    figA, axA = plt.subplots(figsize=(9, 9)); figA.patch.set_facecolor(R.BG)

    def upd(f):
        axA.clear(); R.draw_static(axA, wpts, apts, routes, sector); R.draw_aircraft(axA, frames, f)
        R.draw_sweep(axA, (f * 26) % 360)
        t = f"CTR REIMS  t={f*DT:03d}s" + ("   [instructions appliquees]" if f >= cmd_frame else "")
        axA.set_title(t, color=R.GREEN, fontsize=11)
        return []

    FuncAnimation(figA, upd, frames=len(frames), interval=200).save(
        os.path.join(OUT, "radar_live.gif"), writer=PillowWriter(fps=6), savefig_kwargs={"facecolor": R.BG})
    print(f"[OK] {os.path.join(OUT, 'radar_live.gif')}")


if __name__ == "__main__":
    main()
