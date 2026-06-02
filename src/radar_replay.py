"""
Radar de demonstration (S9/S10) - rejoue un scenario multi-avions dans BlueSky
==============================================================================
Cree plusieurs avions, applique des commandes TrafScript (format produit par le
pipeline LLM+RAG : HDG/ALT/SPD), avance la simulation et enregistre les
trajectoires, puis rend une vue RADAR (top-down) en image + animation GIF.

Sert d'artefact de demonstration (a defaut d'enregistrement ecran de la GUI).
Lancer : bluesky-env/Scripts/python.exe radar_replay.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

import bluesky_runtime as bsk

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_out")

# flotte initiale : (callsign, type, lat, lon, hdg, alt_ft, spd_kt)
FLEET = [
    ("AFR1234", "A320", 48.05, 1.55, 90, 15000, 250),
    ("BAW57",   "B738", 48.35, 2.45, 250, 20000, 300),
    ("DLH88",   "A319", 47.70, 2.55, 330, 12000, 240),
    ("RYR9",    "B738", 48.00, 1.45, 70, 18000, 280),
]
# commandes (t_sec, ligne TrafScript) - telles que le pipeline les genere
CMDS = [
    (0, "HDG AFR1234 270"), (0, "ALT AFR1234 10000"),
    (0, "HDG BAW57 200"),   (0, "SPD BAW57 250"),
    (0, "ALT DLH88 24000"), (0, "HDG DLH88 90"),
    (180, "HDG RYR9 180"),  (180, "ALT RYR9 10000"),
]
TOTAL, DT = 600, 20


def main():
    os.makedirs(OUT, exist_ok=True)
    bsk.bs(); bsk.reset()
    for cs, *a in FLEET:
        bsk.create(cs, *a)

    tracks = {cs: [] for cs, *_ in FLEET}
    applied, t = set(), 0
    while t <= TOTAL:
        for k, (tc, line) in enumerate(CMDS):
            if tc <= t and k not in applied:
                bsk.cmd(line); applied.add(k)
        for s in bsk.state():
            if s["id"] in tracks:
                tracks[s["id"]].append((s["lon"], s["lat"], s["hdg"], s["alt_ft"]))
        bsk.advance(DT); t += DT

    nf = min(len(v) for v in tracks.values())
    print(f"[*] {len(FLEET)} avions, {nf} positions enregistrees sur ~{TOTAL}s")

    # --- image radar (tracks complets) -------------------------------------
    fig, ax = plt.subplots(figsize=(8, 8))
    colors = plt.cm.tab10.colors
    for i, (cs, pts) in enumerate(tracks.items()):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ax.plot(xs, ys, "-", lw=1.6, color=colors[i], label=cs)
        ax.plot(xs[-1], ys[-1], "o", color=colors[i])
        ax.annotate(f"{cs}  FL{int(pts[-1][3]/100):03d}", (xs[-1], ys[-1]),
                    fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    ax.set_title("Radar - scenario BlueSky pilote par le pipeline (trajectoires)")
    ax.legend(loc="upper right", fontsize=9); ax.grid(alpha=0.3); ax.set_aspect("equal", "datalim")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "radar_s10.png"), dpi=150)
    print(f"[OK] {os.path.join(OUT, 'radar_s10.png')}")

    # --- animation GIF ------------------------------------------------------
    figA, axA = plt.subplots(figsize=(7, 7))
    allx = [p[0] for v in tracks.values() for p in v]
    ally = [p[1] for v in tracks.values() for p in v]
    axA.set_xlim(min(allx) - 0.05, max(allx) + 0.05); axA.set_ylim(min(ally) - 0.05, max(ally) + 0.05)
    axA.set_title("Radar BlueSky (replay)"); axA.grid(alpha=0.3)
    lines = {cs: axA.plot([], [], "-", lw=1.4, color=colors[i])[0] for i, (cs, _) in enumerate(tracks.items())}
    dots = {cs: axA.plot([], [], "o", color=colors[i])[0] for i, (cs, _) in enumerate(tracks.items())}

    def upd(f):
        for cs, pts in tracks.items():
            xs = [p[0] for p in pts[:f + 1]]; ys = [p[1] for p in pts[:f + 1]]
            lines[cs].set_data(xs, ys); dots[cs].set_data(xs[-1:], ys[-1:])
        axA.set_xlabel(f"t = {f*DT}s")
        return list(lines.values()) + list(dots.values())

    anim = FuncAnimation(figA, upd, frames=nf, interval=200, blit=True)
    gif = os.path.join(OUT, "radar_s10.gif")
    anim.save(gif, writer=PillowWriter(fps=5))
    print(f"[OK] {gif}")
    print("[S9/S10] radar de demonstration genere.")


if __name__ == "__main__":
    main()
