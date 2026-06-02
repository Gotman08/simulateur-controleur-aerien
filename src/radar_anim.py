"""
Radar anime (balayage) - secteur Reims/URCA - a partir de BlueSky
=================================================================
Scope ATC realiste centre sur Reims (URCA), avec :
- navaids reels (bs.navdb) + reseau de routes (plus proches voisins) + contour de secteur,
- avions (donnees du simulateur) : blips + vecteur vitesse + bloc de donnees + echos,
- balayage radar tournant (afterglow) ; replay temps reel du scenario.

Sorties : demo_out/radar_reims.png (statique) + demo_out/radar_reims.gif (anime)
Lancer : bluesky-env/Scripts/python.exe radar_anim.py
"""
import os
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

import bluesky_runtime as bsk

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_out")
CLAT, CLON = 49.25, 4.05          # Reims / URCA
RANGE_NM = 70
COSLAT = math.cos(math.radians(CLAT))
GREEN, DIM, BG = "#33ff66", "#1d6b33", "#04140a"

FLEET = [
    ("AFR1234", "A320", 49.70, 3.10, 120, 13000, 250),
    ("BAW57",   "B738", 48.75, 4.90, 70,  23000, 300),
    ("DLH88",   "A319", 49.85, 4.30, 200, 16000, 270),
    ("RYR9",    "B738", 48.70, 3.60, 30,  9000,  240),
    ("EZY21",   "A320", 49.30, 5.10, 250, 19000, 280),
    ("KLM45",   "E190", 48.95, 3.20, 90,  8000,  220),
]
CMDS = ["HDG AFR1234 140", "ALT AFR1234 7000", "HDG BAW57 90", "ALT DLH88 10000",
        "HDG RYR9 60", "SPD EZY21 250", "ALT KLM45 5000", "HDG KLM45 70"]
NFRAMES, DT, SWEEP_STEP = 40, 15, 26      # 40 images, 15 s/sim, 26 deg/image


def to_nm(lat, lon):
    return (lon - CLON) * 60.0 * COSLAT, (lat - CLAT) * 60.0


def sector_polygon(radius=55):
    pts = []
    for deg in (20, 75, 140, 200, 260, 320):
        a = math.radians(90 - deg)
        pts.append((radius * math.cos(a), radius * 0.85 * math.sin(a)))
    return pts + [pts[0]]


def build():
    bsk.bs(); bsk.reset()
    for cs, *a in FLEET:
        bsk.create(cs, *a)
    for c in CMDS:
        bsk.cmd(c)
    frames = []                       # liste de {cs: (x,y,hdg,alt,gs)}
    for _ in range(NFRAMES):
        snap = {}
        for s in bsk.state():
            if s["id"] in {c for c, *_ in FLEET}:
                x, y = to_nm(s["lat"], s["lon"])
                gs = s.get("tas_kt") or s.get("cas_kt") or 0
                snap[s["id"]] = (x, y, s["hdg"], s["alt_ft"], gs)
        frames.append(snap)
        bsk.advance(DT)

    nav = bsk.bs().navdb
    wpts = []
    if getattr(nav, "wplat", None) is not None:
        wplat, wplon, wpid = np.asarray(nav.wplat), np.asarray(nav.wplon), list(nav.wpid)
        m = (np.abs(wplat - CLAT) < 1.0) & (np.abs(wplon - CLON) < 1.5)
        seen = set()
        for i in np.where(m)[0]:
            nm = str(wpid[i])
            if len(nm) == 5 and nm.isalpha() and nm not in seen:
                seen.add(nm); wpts.append((*to_nm(wplat[i], wplon[i]), nm))
            if len(wpts) >= 26:
                break
    apts = []
    if getattr(nav, "aptlat", None) is not None:
        aptlat, aptlon, aptid = np.asarray(nav.aptlat), np.asarray(nav.aptlon), list(nav.aptid)
        m = (np.abs(aptlat - CLAT) < 0.9) & (np.abs(aptlon - CLON) < 1.3)
        for i in np.where(m)[0][:8]:
            apts.append((*to_nm(aptlat[i], aptlon[i]), str(aptid[i])))
    # routes = 2 plus proches voisins (reseau type airways)
    routes = set()
    P = [(x, y) for x, y, _ in wpts]
    for i, (xi, yi) in enumerate(P):
        d = sorted(range(len(P)), key=lambda j: (P[j][0] - xi) ** 2 + (P[j][1] - yi) ** 2)
        for j in d[1:3]:
            if (P[j][0] - xi) ** 2 + (P[j][1] - yi) ** 2 < 45 ** 2:
                routes.add(tuple(sorted((i, j))))
    return frames, wpts, apts, list(routes), sector_polygon()


def draw_static(ax, wpts, apts, routes, sector):
    ax.set_facecolor(BG)
    for r in range(20, RANGE_NM + 1, 20):
        ax.add_patch(plt.Circle((0, 0), r, fill=False, ec=DIM, lw=0.8))
        ax.text(0, r, f"{r}", color=DIM, fontsize=7, ha="center", va="bottom")
    for deg in range(0, 360, 30):
        a = math.radians(90 - deg)
        ax.plot([(RANGE_NM - 3) * math.cos(a), RANGE_NM * math.cos(a)],
                [(RANGE_NM - 3) * math.sin(a), RANGE_NM * math.sin(a)], color=DIM, lw=0.8)
        ax.text(RANGE_NM * 1.04 * math.cos(a), RANGE_NM * 1.04 * math.sin(a),
                f"{deg:03d}", color=DIM, fontsize=6.5, ha="center", va="center")
    xs = [p[0] for p in sector]; ys = [p[1] for p in sector]
    ax.plot(xs, ys, color="#2e8bff", lw=1.2, ls="--", alpha=0.7)
    ax.text(sector[0][0], sector[0][1], " CTA REIMS", color="#2e8bff", fontsize=8)
    for i, j in routes:
        ax.plot([wpts[i][0], wpts[j][0]], [wpts[i][1], wpts[j][1]], color="#14506b", lw=0.7)
    for x, y, nm in wpts:
        ax.plot(x, y, marker="^", color="#2e8bff", ms=4.5, mfc="none")
        ax.text(x + 1, y + 1, nm, color="#2e8bff", fontsize=6)
    for x, y, nm in apts:
        ax.plot(x, y, marker="s", color="#ffae42", ms=6, mfc="none", mew=1.3)
        ax.text(x + 1.2, y - 2.2, nm, color="#ffae42", fontsize=7.5, fontweight="bold")
    ax.plot(0, 0, marker="+", color=GREEN, ms=9)
    ax.set_xlim(-RANGE_NM * 1.12, RANGE_NM * 1.12); ax.set_ylim(-RANGE_NM * 1.12, RANGE_NM * 1.12)
    ax.set_aspect("equal"); ax.axis("off")


def draw_aircraft(ax, frames, f):
    snap = frames[f]
    for cs, (x, y, hdg, alt, gs) in snap.items():
        for k in range(max(0, f - 5), f):
            px, py = frames[k][cs][0], frames[k][cs][1]
            ax.plot(px, py, marker="s", color=DIM, ms=2)
        a = math.radians(90 - hdg)
        lead = gs / 60.0
        ax.plot([x, x + lead * math.cos(a)], [y, y + lead * math.sin(a)], color=GREEN, lw=1.0)
        ax.plot(x, y, marker="s", color=GREEN, ms=5.5, mfc="none", mew=1.5)
        ax.text(x + 2, y + 2, f"{cs}\n{int(round(alt/100)):03d} {int(round(gs)):03d}",
                color=GREEN, fontsize=7.5, va="bottom",
                bbox=dict(boxstyle="round,pad=0.12", fc=BG, ec=DIM, lw=0.5))


def draw_sweep(ax, angle_deg):
    a = math.radians(90 - angle_deg)
    ax.plot([0, RANGE_NM * math.cos(a)], [0, RANGE_NM * math.sin(a)], color=GREEN, lw=1.4, alpha=0.9)
    for k in range(1, 14):                                   # afterglow
        aa = math.radians(90 - (angle_deg - k * 4))
        ax.plot([0, RANGE_NM * math.cos(aa)], [0, RANGE_NM * math.sin(aa)],
                color=GREEN, lw=1.2, alpha=max(0.0, 0.28 - k * 0.02))


def main():
    os.makedirs(OUT, exist_ok=True)
    frames, wpts, apts, routes, sector = build()
    print(f"[*] {len(frames)} images, {len(wpts)} waypoints, {len(apts)} aeroports, {len(routes)} routes")

    plt.rcParams.update({"font.family": "monospace"})

    # PNG statique (frame finale)
    fig, ax = plt.subplots(figsize=(11, 11)); fig.patch.set_facecolor(BG)
    draw_static(ax, wpts, apts, routes, sector); draw_aircraft(ax, frames, len(frames) - 1)
    ax.set_title("BlueSky  -  CTR REIMS / URCA   (range 70 NM, leader = 1 min)",
                 color=GREEN, fontsize=12)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "radar_reims.png"), dpi=150, facecolor=BG)
    plt.close(fig)
    print(f"[OK] {os.path.join(OUT, 'radar_reims.png')}")

    # GIF anime (balayage + replay)
    figA, axA = plt.subplots(figsize=(9, 9)); figA.patch.set_facecolor(BG)

    def upd(f):
        axA.clear()
        draw_static(axA, wpts, apts, routes, sector)
        draw_aircraft(axA, frames, f)
        draw_sweep(axA, (f * SWEEP_STEP) % 360)
        axA.set_title(f"BlueSky  -  CTR REIMS   t={f*DT:03d}s   (balayage radar)",
                      color=GREEN, fontsize=11)
        return []

    anim = FuncAnimation(figA, upd, frames=len(frames), interval=180, blit=False)
    gif = os.path.join(OUT, "radar_reims.gif")
    anim.save(gif, writer=PillowWriter(fps=6), savefig_kwargs={"facecolor": BG})
    print(f"[OK] {gif}")
    print("[radar] PNG + GIF balayage generes.")


if __name__ == "__main__":
    main()
