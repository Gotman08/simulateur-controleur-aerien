"""
Runtime BlueSky local (headless) - Semaines 8 (V4/V5)
=====================================================
Pilote le simulateur BlueSky (bluesky-simulator 1.1.1) sur le PC local :
init, creation d'avions, application des commandes TrafScript produites par le
pipeline (HDG/ALT/SPD/ADDWPT via 03_bluesky_connector), avancee du temps,
lecture de l'etat des vols.

Self-test (V4+V5) :  bluesky-env/Scripts/python.exe bluesky_runtime.py
"""
import math

_BS = {}
NM2DEG = 1.0 / 60.0          # 1 NM ~ 1/60 degre de latitude
M2FT = 1.0 / 0.3048
MS2KT = 1.0 / 0.514444


def bs():
    import bluesky as _b
    if "init" not in _BS:
        _b.init(mode="sim", detached=True)
        _BS["init"] = True
    return _b


def advance(seconds):
    """Avance la simulation d'environ `seconds` (boucle de pas)."""
    b = bs()
    t0 = float(b.sim.simt)
    guard = 0
    while float(b.sim.simt) - t0 < seconds and guard < 500000:
        b.sim.step()
        guard += 1
    return float(b.sim.simt) - t0


def reset():
    bs().stack.stack("RESET")
    advance(0.1)


def create(cs, actype, lat, lon, hdg, alt_ft, spd_kt):
    bs().stack.stack(f"CRE {cs} {actype} {lat} {lon} {hdg} {alt_ft} {spd_kt}")
    advance(0.1)


def cmd(line):
    """Applique une ligne TrafScript (ex. 'HDG AFR1234 270')."""
    bs().stack.stack(line)


def define_waypoints(fixes, center_lat=48.0, center_lon=2.0):
    """Definit des fix du secteur (graphe S2) en lat/lon autour d'un centre."""
    b = bs()
    for name, (x_nm, y_nm) in fixes.items():
        lat = center_lat + (y_nm - 25) * NM2DEG
        lon = center_lon + (x_nm - 50) * NM2DEG / max(0.2, math.cos(math.radians(center_lat)))
        b.stack.stack(f"DEFWPT {name} {lat:.5f} {lon:.5f} FIX")
    advance(0.1)


def state():
    t = bs().traf
    out = []
    ids = list(getattr(t, "id", []))
    for i, cs in enumerate(ids):
        rec = {"id": cs, "lat": round(float(t.lat[i]), 4), "lon": round(float(t.lon[i]), 4),
               "hdg": round(float(t.hdg[i]), 1), "alt_ft": round(float(t.alt[i]) * M2FT)}
        if hasattr(t, "cas"):
            rec["cas_kt"] = round(float(t.cas[i]) * MS2KT)
        rec["tas_kt"] = round(float(t.tas[i]) * MS2KT)
        out.append(rec)
    return out


def _self_test():
    print("[V4] init BlueSky...")
    bs()
    reset()
    create("AFR1234", "A320", 48.0, 2.0, hdg=90, alt_ft=10000, spd_kt=250)
    before = state()[0]
    print(f"[V4] avion cree : {before}")

    print("\n[V5] application TrafScript : HDG 270, ALT 5000, SPD 280 ...")
    for line in ["HDG AFR1234 270", "ALT AFR1234 5000", "SPD AFR1234 280"]:
        cmd(line)
        print("   >", line)
    dt = advance(180)             # ~3 min de simulation
    after = state()[0]
    print(f"[V5] apres {dt:.0f}s : {after}")
    print(f"[V5] deltas : hdg {before['hdg']}->{after['hdg']}  alt_ft {before['alt_ft']}->{after['alt_ft']}")
    ok_alt = after["alt_ft"] < before["alt_ft"] - 500           # descend vers 5000
    ok_hdg = abs((after["hdg"] - 270 + 180) % 360 - 180) < abs((before["hdg"] - 270 + 180) % 360 - 180)
    print(f"[V5] descente engagee: {ok_alt} | cap tourne vers 270: {ok_hdg}")
    assert ok_alt and ok_hdg, "la manoeuvre n'a pas ete appliquee"
    print("\n[V4/V5] BlueSky execute les commandes du pipeline. OK.")


if __name__ == "__main__":
    _self_test()
