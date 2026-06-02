"""
Radar scope realiste (style ecran de controle ATC) a partir de BlueSky
======================================================================
Rend un vrai scope radar a partir des donnees REELLES du simulateur BlueSky :
- scenario multi-avions autour de Paris-CDG (LFPG),
- navaids reels (bs.navdb : waypoints, aeroports) en fond de carte,
- anneaux de distance, blips + vecteur vitesse (leader line) + bloc de donnees
  (indicatif / niveau de vol / vitesse sol), historique radar.

Lancer : bluesky-env/Scripts/python.exe radar_scope.py  -> demo_out/radar_scope.png
"""
import os
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import bluesky_runtime as bsk

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_out")
CLAT, CLON = 49.00, 2.55          # centre radar : zone Paris-CDG
RANGE_NM = 70                     # portee affichee
COSLAT = math.cos(math.radians(CLAT))

# flotte (callsign, type, lat, lon, hdg, alt_ft, spd_kt) autour du secteur
FLEET = [
    ("AFR1234", "A320", 49.35, 1.40, 110, 11000, 250),
    ("BAW57",   "B738", 48.70, 3.30, 70,  23000, 300),
    ("DLH88",   "A319", 49.55, 2.90, 200, 15000, 270),
    ("RYR9",    "B738", 48.55, 2.10, 20,  9000,  240),
    ("EZY21",   "A320", 49.10, 3.70, 250, 19000, 280),
    ("KLM45",   "E190", 48.80, 1.70, 90,  7000,  220),
]
CMDS = ["HDG AFR1234 130", "ALT AFR1234 6000", "HDG BAW57 90", "ALT DLH88 9000",
        "HDG RYR9 50", "SPD EZY21 250", "ALT KLM45 4000"]


def to_nm(lat, lon):
    return (lon - CLON) * 60.0 * COSLAT, (lat - CLAT) * 60.0


def main():
    os.makedirs(OUT, exist_ok=True)
    bsk.bs(); bsk.reset()
    for cs, *a in FLEET:
        bsk.create(cs, *a)
    for c in CMDS:
        bsk.cmd(c)

    # historique radar : quelques balayages
    history = {cs: [] for cs, *_ in FLEET}
    for _ in range(6):
        for s in bsk.state():
            if s["id"] in history:
                history[s["id"]].append(to_nm(s["lat"], s["lon"]))
        bsk.advance(20)
    snap = {s["id"]: s for s in bsk.state()}

    # navaids reels dans la fenetre (base BlueSky)
    nav = bsk.bs().navdb
    wpts = []
    wplat = getattr(nav, "wplat", None)
    if wplat is not None:
        wplat = np.asarray(nav.wplat); wplon = np.asarray(nav.wplon); wpid = list(nav.wpid)
        m = (np.abs(wplat - CLAT) < 1.0) & (np.abs(wplon - CLON) < 1.4)
        idx = np.where(m)[0]
        seen = set()
        for i in idx:
            name = str(wpid[i])
            if len(name) == 5 and name.isalpha() and name not in seen:   # fixes RNAV 5 lettres
                seen.add(name); wpts.append((wplat[i], wplon[i], name))
            if len(wpts) >= 28:
                break
    apts = []
    aptlat = getattr(nav, "aptlat", None)
    if aptlat is not None:
        aptlat = np.asarray(nav.aptlat); aptlon = np.asarray(nav.aptlon); aptid = list(nav.aptid)
        m = (np.abs(aptlat - CLAT) < 0.9) & (np.abs(aptlon - CLON) < 1.2)
        for i in np.where(m)[0][:8]:
            apts.append((aptlat[i], aptlon[i], str(aptid[i])))

    # --- rendu radar --------------------------------------------------------
    plt.rcParams.update({"font.family": "monospace"})
    fig, ax = plt.subplots(figsize=(11, 11))
    fig.patch.set_facecolor("#04140a"); ax.set_facecolor("#04140a")
    GREEN, DIM = "#33ff66", "#1d6b33"

    for r in range(20, RANGE_NM + 1, 20):                       # anneaux de distance
        ax.add_patch(plt.Circle((0, 0), r, fill=False, ec=DIM, lw=0.8))
        ax.text(0, r, f"{r}", color=DIM, fontsize=8, ha="center", va="bottom")
    for deg in range(0, 360, 30):                                # graduations cap
        a = math.radians(90 - deg)
        x0, y0 = (RANGE_NM - 3) * math.cos(a), (RANGE_NM - 3) * math.sin(a)
        x1, y1 = RANGE_NM * math.cos(a), RANGE_NM * math.sin(a)
        ax.plot([x0, x1], [y0, y1], color=DIM, lw=0.8)
        ax.text(RANGE_NM * 1.03 * math.cos(a), RANGE_NM * 1.03 * math.sin(a),
                f"{deg:03d}", color=DIM, fontsize=7, ha="center", va="center")

    for lat, lon, name in wpts:                                  # waypoints
        x, y = to_nm(lat, lon)
        if x * x + y * y <= RANGE_NM ** 2:
            ax.plot(x, y, marker="^", color="#2e8bff", ms=5, mfc="none")
            ax.text(x + 1, y + 1, name, color="#2e8bff", fontsize=6.5)
    for lat, lon, name in apts:                                  # aeroports
        x, y = to_nm(lat, lon)
        if x * x + y * y <= RANGE_NM ** 2:
            ax.plot(x, y, marker="s", color="#ffae42", ms=7, mfc="none", mew=1.4)
            ax.text(x + 1.2, y - 2.2, name, color="#ffae42", fontsize=8, fontweight="bold")

    for cs, s in snap.items():                                   # avions
        x, y = to_nm(s["lat"], s["lon"])
        gs = s.get("tas_kt") or s.get("cas_kt") or 0
        a = math.radians(90 - s["hdg"])
        lead = gs / 60.0                                         # position a +1 min
        hx, hy = x + lead * math.cos(a), y + lead * math.sin(a)
        for hxn, hyn in history[cs][-5:]:                        # historique (echos)
            ax.plot(hxn, hyn, marker="s", color=DIM, ms=2)
        ax.plot([x, hx], [y, hy], color=GREEN, lw=1.0)           # vecteur vitesse
        ax.plot(x, y, marker="s", color=GREEN, ms=6, mfc="none", mew=1.6)
        block = f"{cs}\n{int(round(s['alt_ft']/100)):03d} {int(round(gs)):03d}"
        ax.text(x + 2.0, y + 2.0, block, color=GREEN, fontsize=8.5, va="bottom",
                bbox=dict(boxstyle="round,pad=0.15", fc="#04140a", ec=DIM, lw=0.6))

    ax.plot(0, 0, marker="+", color=GREEN, ms=10)                # site radar
    ax.set_xlim(-RANGE_NM * 1.1, RANGE_NM * 1.1); ax.set_ylim(-RANGE_NM * 1.1, RANGE_NM * 1.1)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("BlueSky  -  APP/CTR  LFPG sector   (range 70 NM, leader = 1 min)",
                 color=GREEN, fontsize=12, fontfamily="monospace")
    fig.tight_layout()
    p = os.path.join(OUT, "radar_scope.png")
    fig.savefig(p, dpi=150, facecolor=fig.get_facecolor())
    print(f"[OK] {p}  | {len(snap)} avions, {len(wpts)} waypoints, {len(apts)} aeroports")


if __name__ == "__main__":
    main()
