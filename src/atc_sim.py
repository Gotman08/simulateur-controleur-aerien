"""
Gestionnaire de simulation temps reel - Application d'entrainement ATC
======================================================================
Pilote BlueSky (bluesky_runtime) dans un THREAD UNIQUE pour le rendu radar live :
- boucle d'avancement en temps reel (dt mur x vitesse de simulation),
- file de commandes thread-safe (CRE / HDG / ALT / SPD / ADDWPT),
- snapshot d'etat protege par verrou (lu par le serveur web / WebSocket),
- creation d'avions a partir d'une liste (situation generee par l'IA),
- donnees statiques de carte (navaids, aeroports, routes, contour secteur),
- detection de perte de separation (< 5 NM et < 1000 ft).

BlueSky n'etant pas thread-safe, TOUS les appels BlueSky se font dans le thread
de simulation : les autres threads deposent des commandes dans la file et lisent
une COPIE du snapshot. Les conventions geometriques/visuelles (centre Reims,
portee 70 NM, conversion NM) reprennent radar_anim.py sans importer matplotlib.
"""
import math
import time
import queue
import threading

import bluesky_runtime as bsk

# --- Reperes du secteur (identiques a radar_anim.py : Reims / URCA) ----------
CLAT, CLON = 49.25, 4.05
RANGE_NM = 70
COSLAT = math.cos(math.radians(CLAT))
SEP_NM = 5.0            # separation reglementaire (cf. secteur_graphe.json)
SEP_FT = 1000.0         # separation verticale
LOOKAHEAD_S = 120.0     # horizon de prediction de conflit (STCA ~ 2 min)


def to_nm(lat, lon):
    """Position (lat, lon) -> coordonnees plan (x, y) en NM autour du centre."""
    return (lon - CLON) * 60.0 * COSLAT, (lat - CLAT) * 60.0


def from_nm(x_nm, y_nm):
    """Coordonnees plan (x, y) en NM -> (lat, lon) autour du centre."""
    lat = CLAT + y_nm / 60.0
    lon = CLON + x_nm / (60.0 * COSLAT)
    return lat, lon


def _point_in_poly(x, y, pts):
    """Point dans polygone (ray casting), pts = [[x,y], ...] en NM."""
    n, inside, j = len(pts), False, len(pts) - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def sector_polygon(radius=55):
    pts = []
    for deg in (20, 75, 140, 200, 260, 320):
        a = math.radians(90 - deg)
        pts.append([radius * math.cos(a), radius * 0.85 * math.sin(a)])
    return pts + [pts[0]]


class SimManager:
    """Boucle BlueSky temps reel + etat partage thread-safe."""

    def __init__(self, dt=0.1, speed=1.0):
        self._dt = dt
        self._speed = speed
        self._paused = False
        self._running = False
        self._lock = threading.Lock()
        self._cmd_q = queue.Queue()
        self._thread = None
        self._nav = None
        self._meta = {}        # callsign -> {"type": str}
        self._sector_fixes = []
        self._wind = None      # {"dir": deg, "spd": kt, "alt": ft|None}
        self._turb = 0.0       # intensite de turbulence (m/s)
        self._zones = {}       # name -> {"type","shape","coords","color"}
        self._zone_seq = 0
        self._snapshot = {"t": 0.0, "running": False, "paused": False,
                          "speed": speed, "aircraft": [], "conflicts": []}

    # --- cycle de vie --------------------------------------------------------
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="atc-sim", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    # --- API appelee depuis les threads HTTP (non bloquante) -----------------
    def enqueue(self, trafscript_line):
        """Depose une ligne TrafScript (ex. 'HDG AFR1234 270') a appliquer."""
        if trafscript_line:
            self._cmd_q.put({"kind": "cmd", "line": str(trafscript_line)})

    def create_aircraft(self, aircraft):
        """Cree une liste d'avions [{callsign,type,lat,lon,hdg,alt_ft,spd_kt}, ...]."""
        created = []
        for ac in aircraft:
            cs = str(ac.get("callsign", "")).upper().strip()
            if not cs:
                continue
            item = {"kind": "create", "cs": cs,
                    "type": ac.get("type", "A320"),
                    "lat": float(ac["lat"]), "lon": float(ac["lon"]),
                    "hdg": float(ac.get("hdg", 0)), "alt_ft": float(ac.get("alt_ft", 20000)),
                    "spd_kt": float(ac.get("spd_kt", 250))}
            self._cmd_q.put(item)
            created.append(cs)
        return created

    # --- meteo / zones (fonctions BlueSky) -----------------------------------
    def set_wind(self, direction, speed, alt=None):
        """Definit le vent (BlueSky WIND). direction None -> efface le vent."""
        self._cmd_q.put({"kind": "wind", "dir": direction, "spd": speed, "alt": alt})

    def set_turbulence(self, level):
        """Active/regle la turbulence (m/s). 0 -> off."""
        self._cmd_q.put({"kind": "turb", "level": float(level)})

    def add_zone(self, ztype, shape, coords):
        """Ajoute une zone : ztype 'storm'|'restricted', shape 'CIRCLE'|'POLY',
        coords [lat,lon,rayon_nm] (cercle) ou [lat,lon,lat,lon,...] (polygone)."""
        self._cmd_q.put({"kind": "zone", "ztype": ztype, "shape": shape, "coords": coords})

    def clear_zones(self):
        self._cmd_q.put({"kind": "clearzones"})

    def set_speed(self, x):
        with self._lock:
            self._speed = max(0.1, min(20.0, float(x)))

    def pause(self):
        with self._lock:
            self._paused = True

    def resume(self):
        with self._lock:
            self._paused = False

    def reset(self):
        self._cmd_q.put({"kind": "reset"})

    def snapshot(self):
        """Copie thread-safe du dernier etat (pour HTTP / WebSocket)."""
        with self._lock:
            snap = dict(self._snapshot)
            snap["aircraft"] = [dict(a) for a in self._snapshot["aircraft"]]
            snap["conflicts"] = [list(c) for c in self._snapshot["conflicts"]]
            return snap

    def nav_static(self):
        """Donnees statiques de carte (calculees une fois par le thread sim)."""
        t0 = time.monotonic()
        while self._nav is None and time.monotonic() - t0 < 30:
            time.sleep(0.05)
        return self._nav or {"waypoints": [], "airports": [], "routes": [],
                             "sector": sector_polygon(), "range_nm": RANGE_NM,
                             "center": [CLAT, CLON]}

    # --- thread de simulation (seul a toucher BlueSky) -----------------------
    def _run(self):
        bsk.bs()
        bsk.reset()
        self._define_sector_fixes()
        self._enable_cd()
        self._nav = self._compute_nav()
        last = time.monotonic()
        while self._running:
            now = time.monotonic()
            wall = min(1.0, now - last)        # borne anti-saut (pause systeme, GC)
            last = now
            self._drain_queue()
            with self._lock:
                paused, speed = self._paused, self._speed
            if not paused and wall > 0:
                try:
                    bsk.advance(wall * speed)
                except Exception:
                    pass
            self._update_snapshot(paused, speed)
            time.sleep(self._dt)

    def _drain_queue(self):
        while True:
            try:
                item = self._cmd_q.get_nowait()
            except queue.Empty:
                return
            try:
                self._apply(item)
            except Exception:
                pass

    def _apply(self, item):
        kind = item.get("kind")
        if kind == "cmd":
            bsk.cmd(item["line"])
        elif kind == "create":
            if item["cs"] in self._meta:
                return                              # indicatif deja present -> on ignore
            bsk.create(item["cs"], item["type"], item["lat"], item["lon"],
                       item["hdg"], item["alt_ft"], item["spd_kt"])
            self._meta[item["cs"]] = {"type": item["type"]}
        elif kind == "wind":
            self._apply_wind(item["dir"], item["spd"], item["alt"])
        elif kind == "turb":
            self._apply_turb(item["level"])
        elif kind == "zone":
            self._apply_zone(item["ztype"], item["shape"], item["coords"])
        elif kind == "clearzones":
            self._clear_zones()
        elif kind == "reset":
            # On vide le radar (DEL de chaque avion) sans RESET global : cela
            # preserve le temps simu, les navaids et les fix deja definis.
            for s in bsk.state():
                bsk.cmd(f"DEL {s['id']}")
            bsk.advance(0.1)
            self._meta.clear()
            self._clear_zones()
            self._apply_wind(None, None, None)
            self._apply_turb(0.0)

    def _apply_wind(self, direction, speed, alt):
        wind = bsk.bs().traf.wind
        if direction is None:
            wind.clear()
            self._wind = None
            return
        d, s = int(round(float(direction))) % 360, max(0, int(round(float(speed))))
        if alt:
            bsk.cmd(f"WIND {CLAT:.4f} {CLON:.4f} {float(alt)} {d} {s}")
        else:
            bsk.cmd(f"WIND {CLAT:.4f} {CLON:.4f} {d} {s}")
        self._wind = {"dir": d, "spd": s, "alt": (int(alt) if alt else None)}

    def _apply_turb(self, level):
        try:
            turb = bsk.bs().traf.turbulence
            if level and level > 0:
                turb.SetStandards([level, level, level * 0.6])
                turb.setnoise(True)
            else:
                turb.setnoise(False)
            self._turb = float(level or 0.0)
        except Exception:
            self._turb = 0.0

    def _apply_zone(self, ztype, shape, coords):
        from bluesky.tools import areafilter
        self._zone_seq += 1
        name = f"{'STORM' if ztype == 'storm' else 'ZONE'}{self._zone_seq}"
        areafilter.defineArea(name, shape, [float(c) for c in coords])
        self._zones[name] = {"type": ztype, "shape": shape,
                             "coords": [float(c) for c in coords],
                             "color": ("#ff5ab0" if ztype == "storm" else "#ff4350")}

    def _clear_zones(self):
        try:
            from bluesky.tools import areafilter
            for name in list(self._zones):
                areafilter.deleteArea(name)
        except Exception:
            pass
        self._zones = {}

    def _enable_cd(self):
        """Active le moteur de detection de conflits integre a BlueSky (ASAS/CD,
        StateBased) avec zone 5 NM / 1000 ft et horizon 2 min."""
        try:
            for c in ("CDMETHOD ON", "ZONER 5", "ZONEDH 1000", "DTLOOK 120"):
                bsk.cmd(c)
            bsk.advance(0.1)
        except Exception:
            pass

    def _define_sector_fixes(self):
        """Definit les fix du secteur (graphe S2) autour du centre Reims :
        rend ADDWPT/'direct' operationnels et affiche les fix nommes au radar."""
        try:
            import graph_secteur
            g = graph_secteur.SectorGraph()
            fixes = {nid: tuple(n["pos_nm"]) for nid, n in g.nodes.items()}
            bsk.define_waypoints(fixes, center_lat=CLAT, center_lon=CLON)
            self._sector_fixes = [
                {"x": xn - 50, "y": yn - 25, "name": nid,
                 "type": g.nodes[nid].get("type", "fix")}
                for nid, (xn, yn) in fixes.items()]
        except Exception:
            self._sector_fixes = []

    def _update_snapshot(self, paused, speed):
        acs = []
        for s in bsk.state():
            x, y = to_nm(s["lat"], s["lon"])
            gs = s.get("tas_kt") or s.get("cas_kt") or 0
            acs.append({"id": s["id"], "x": round(x, 3), "y": round(y, 3),
                        "lat": s["lat"], "lon": s["lon"], "hdg": s["hdg"],
                        "alt_ft": s["alt_ft"], "fl": int(round(s["alt_ft"] / 100)),
                        "gs": int(round(gs)),
                        "type": self._meta.get(s["id"], {}).get("type", ""),
                        "conflict": False, "alert": ""})
        res = self._analyze_cd()                         # moteur BlueSky (CD&R)
        engine = "bluesky"
        if res is None:                                  # repli geometrie si CD inactif
            res = self._analyze(acs)
            engine = "geometry"
        conflicts, predicted = res
        los = {cs for pair in conflicts for cs in pair}
        warn = {cs for it in predicted for cs in it["pair"]}
        for a in acs:
            a["conflict"] = a["id"] in los
            a["alert"] = "los" if a["id"] in los else ("predicted" if a["id"] in warn else "")
        self._enrich(acs)                                # routes FMS + penetration de zone
        with self._lock:
            try:
                t = float(bsk.bs().sim.simt)
            except Exception:
                t = self._snapshot.get("t", 0.0)
            self._snapshot = {"t": round(t, 1), "running": True, "paused": paused,
                             "speed": speed, "aircraft": acs, "conflicts": conflicts,
                             "predicted": predicted, "cd_engine": engine,
                             "wind": self._wind, "turbulence": self._turb,
                             "zones": self._zones_payload()}

    def _enrich(self, acs):
        """Ajoute a chaque avion sa route FMS (en NM), la zone penetree, la
        vitesse verticale et l'altitude selectionnee (strips / bloc radar)."""
        for a in acs:
            a["route"], a["actwp"], a["inzone"], a["trk"] = [], -1, "", a["hdg"]
            a["vs_fpm"], a["sel_alt_ft"] = 0, None
        try:
            traf = bsk.bs().traf
            idx = {cs: i for i, cs in enumerate(getattr(traf, "id", []))}
            for a in acs:
                i = idx.get(a["id"])
                if i is None:
                    continue
                try:                                     # vitesse SOL + route sol (effet du vent visible)
                    a["gs"] = int(round(float(traf.gs[i]) * bsk.MS2KT))
                    a["trk"] = round(float(traf.trk[i]), 1)
                except Exception:
                    pass
                try:                                     # tendance verticale + niveau autorise
                    a["vs_fpm"] = int(round(float(traf.vs[i]) * bsk.M2FT * 60.0))
                    sel = float(traf.selalt[i]) * bsk.M2FT
                    if sel > 0:
                        a["sel_alt_ft"] = int(round(sel))
                except Exception:
                    pass
                if hasattr(traf, "ap") and i < len(traf.ap.route):
                    r = traf.ap.route[i]
                    if getattr(r, "nwp", 0) > 0:
                        a["route"] = [[round(x, 2), round(y, 2)]
                                      for x, y in (to_nm(la, lo) for la, lo in zip(r.wplat, r.wplon))]
                        a["actwp"] = int(getattr(r, "iactwp", -1))
        except Exception:
            pass
        # Penetration de zone en geometrie NM (la fonction compilee kwikdist de
        # BlueSky/areafilter.checkInside plante avec numpy 2.x).
        for z in self._zones_payload():
            for a in acs:
                if z["shape"] == "CIRCLE":
                    inside = math.hypot(a["x"] - z["cx"], a["y"] - z["cy"]) <= z["r"]
                else:
                    inside = _point_in_poly(a["x"], a["y"], z.get("points", []))
                if inside:
                    a["inzone"] = z["name"]

    def _zones_payload(self):
        """Zones converties en coordonnees plan (NM) pour le rendu radar."""
        out = []
        for name, z in self._zones.items():
            c = z["coords"]
            if z["shape"] == "CIRCLE":
                cx, cy = to_nm(c[0], c[1])
                out.append({"name": name, "type": z["type"], "shape": "CIRCLE",
                            "cx": round(cx, 2), "cy": round(cy, 2), "r": c[2], "color": z["color"]})
            else:
                pts = [list(to_nm(c[i], c[i + 1])) for i in range(0, len(c) - 1, 2)]
                out.append({"name": name, "type": z["type"], "shape": "POLY",
                            "points": [[round(x, 2), round(y, 2)] for x, y in pts], "color": z["color"]})
        return out

    @staticmethod
    def _analyze_cd():
        """Lit le moteur de detection de conflits de BlueSky (bs.traf.cd).
        Renvoie (perte_de_separation, conflits_predits) ou None si la CD est OFF.
        - lospairs : avions deja dans la zone protegee (vol trop proche) ;
        - confpairs : conflit predit (CPA sous la separation) dans l'horizon."""
        try:
            cd = bsk.bs().traf.cd
        except Exception:
            return None
        if type(cd).__name__ == "ConflictDetection":     # methode de base = OFF
            return None
        try:
            from bluesky.tools.aero import nm as _NM
        except Exception:
            _NM = 1852.0
        los_sets = {frozenset(p) for p in cd.lospairs if len(set(p)) == 2}
        conf_sets = {frozenset(p) for p in cd.confpairs if len(set(p)) == 2}
        info = {}
        cp, tc, dca = list(cd.confpairs), cd.tcpa, cd.dcpa
        for k, pr in enumerate(cp):
            key = frozenset(pr)
            if len(key) != 2:
                continue
            t = float(tc[k]) if k < len(tc) else 0.0
            d = float(dca[k]) / _NM if k < len(dca) else 0.0
            if key not in info or t < info[key][0]:
                info[key] = (t, d)
        current = [sorted(p) for p in los_sets]
        predicted = []
        for key in conf_sets:
            if key in los_sets:
                continue
            t, d = info.get(key, (0.0, 0.0))
            predicted.append({"pair": sorted(key), "t": int(round(t)), "d": round(d, 1)})
        return current, predicted

    @staticmethod
    def _vel_nm_s(a):
        """Vecteur vitesse (NM/s) a partir du cap et de la vitesse sol."""
        v = a["gs"] / 3600.0
        h = math.radians(a["hdg"])
        return v * math.sin(h), v * math.cos(h)        # x=est, y=nord

    @classmethod
    def _analyze(cls, acs):
        """Renvoie (perte_de_separation_maintenant, conflits_predits).
        - perte_de_separation : paires deja a < 5 NM et < 1000 ft ;
        - conflit predit : point de rapprochement le plus proche (CPA) sous 5 NM
          dans les 2 min, sur des trajectoires extrapolees lineairement."""
        current, predicted = [], []
        for i in range(len(acs)):
            for j in range(i + 1, len(acs)):
                a, b = acs[i], acs[j]
                if abs(a["alt_ft"] - b["alt_ft"]) >= SEP_FT:
                    continue                                  # separes verticalement
                dx, dy = a["x"] - b["x"], a["y"] - b["y"]
                if math.hypot(dx, dy) < SEP_NM:
                    current.append([a["id"], b["id"]])
                    continue
                avx, avy = cls._vel_nm_s(a)
                bvx, bvy = cls._vel_nm_s(b)
                rvx, rvy = avx - bvx, avy - bvy
                vv = rvx * rvx + rvy * rvy
                if vv < 1e-9:
                    continue                                  # vitesse relative nulle
                t = -(dx * rvx + dy * rvy) / vv               # temps du CPA
                if t <= 0 or t > LOOKAHEAD_S:
                    continue                                  # s'eloignent ou trop loin
                dcpa = math.hypot(dx + rvx * t, dy + rvy * t)
                if dcpa < SEP_NM:
                    predicted.append({"pair": [a["id"], b["id"]],
                                      "t": int(round(t)), "d": round(dcpa, 1)})
        return current, predicted

    def _compute_nav(self):
        import numpy as np
        nav = bsk.bs().navdb
        wpts, apts = [], []
        if getattr(nav, "wplat", None) is not None:
            wplat, wplon, wpid = np.asarray(nav.wplat), np.asarray(nav.wplon), list(nav.wpid)
            m = (np.abs(wplat - CLAT) < 1.0) & (np.abs(wplon - CLON) < 1.5)
            seen = set()
            for i in np.where(m)[0]:
                nm = str(wpid[i])
                if len(nm) == 5 and nm.isalpha() and nm not in seen:
                    seen.add(nm)
                    x, y = to_nm(float(wplat[i]), float(wplon[i]))
                    wpts.append({"x": round(x, 2), "y": round(y, 2), "name": nm})
                if len(wpts) >= 26:
                    break
        if getattr(nav, "aptlat", None) is not None:
            aptlat, aptlon, aptid = np.asarray(nav.aptlat), np.asarray(nav.aptlon), list(nav.aptid)
            m = (np.abs(aptlat - CLAT) < 0.9) & (np.abs(aptlon - CLON) < 1.3)
            for i in np.where(m)[0][:8]:
                x, y = to_nm(float(aptlat[i]), float(aptlon[i]))
                apts.append({"x": round(x, 2), "y": round(y, 2), "name": str(aptid[i])})
        routes = set()
        P = [(w["x"], w["y"]) for w in wpts]
        for i, (xi, yi) in enumerate(P):
            d = sorted(range(len(P)), key=lambda j: (P[j][0] - xi) ** 2 + (P[j][1] - yi) ** 2)
            for j in d[1:3]:
                if (P[j][0] - xi) ** 2 + (P[j][1] - yi) ** 2 < 45 ** 2:
                    routes.add(tuple(sorted((i, j))))
        return {"waypoints": wpts, "airports": apts, "routes": [list(r) for r in routes],
                "fixes": self._sector_fixes, "sector": sector_polygon(),
                "range_nm": RANGE_NM, "center": [CLAT, CLON]}
