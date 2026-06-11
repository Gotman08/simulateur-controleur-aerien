"""
Moteur d'exercice - Application d'entrainement ATC
==================================================
L'IA cree la situation, l'eleve s'adapte : l'exercice genere un trafic dont
certains avions sont mathematiquement EN CONFLIT (construction geometrique,
cf. docs/VALIDATION.md par. 7), ajoute du trafic de remplissage (IA ROMEO ou
generateur local) et des conditions meteo selon la difficulte, puis MESURE la
performance de l'eleve en continu :

  - pertes de separation (< 5 NM et < 1000 ft) : nombre + duree cumulee,
  - conflits predits (CPA) resolus avant la perte de separation,
  - penetrations de zone orageuse / interdite,
  - commandes radio acceptees / rejetees.

Construction d'un conflit garanti : deux avions places a distances D1, D2 d'un
point de croisement P, caps pointant vers P, vitesses v1, v2 telles que
D1/v1 = D2/v2 = t_c (temps d'arrivee commun) -> d_CPA ~ 0 a t = t_c.

Bareme (documente et justifie dans docs/VALIDATION.md par. 6) :
  S_sep   = max(0, 50 - 25*N_LoS - 0.5*T_LoS)        separation = mission primaire
  S_conf  = 20 * resolus / predits   (20 si aucun)    anticipation des conflits
  S_zone  = max(0, 15 - 5*N_zone - 0.1*T_zone)        evitement meteo / zones
  S_radio = 15 * acceptees / totales (15 si aucune)   qualite de la phraseologie
  Score = S_sep + S_conf + S_zone + S_radio dans [0, 100] ; A>=90 B>=75 C>=60 D>=40.
"""
import os
import json
import math
import time
import random
import threading
from datetime import datetime

from atc_sim import from_nm

_HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(os.path.dirname(_HERE), "reports")

SEP_NM = 5.0
SEP_FT = 1000.0

#: Prefixes compagnies reserves a l'exercice (disjoints du generateur local
#: d'atc_ai pour eviter les collisions d'indicatifs avec le trafic de remplissage).
_AIRLINES = ["AFR", "BAW", "DLH", "SWR", "AUA", "THY", "UAE", "QTR"]

DIFFICULTIES = {
    "facile":    {"label": "Facile",    "pairs": 1, "filler": 1, "wind": None,
                  "storm": False, "turb": 0.0, "duration_min": 10},
    "moyen":     {"label": "Moyen",     "pairs": 2, "filler": 2, "wind": (15, 30),
                  "storm": False, "turb": 0.0, "duration_min": 10},
    "difficile": {"label": "Difficile", "pairs": 3, "filler": 2, "wind": (25, 40),
                  "storm": True, "turb": 2.5, "duration_min": 15},
}

_FILLER_TEMPLATES = [
    "two A320 from the {dir} at FL{fl} heading {hdg}, 12 miles apart",
    "one B738 from the {dir} at FL{fl}",
    "two A319 from the {dir} at FL{fl} heading {hdg}, 15 miles apart",
]


def _pair_key(pair):
    return "/".join(sorted(pair))


def grade(score):
    return "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else \
           "D" if score >= 40 else "E"


def make_conflict_pair(rng, callsigns, fl_ft):
    """Construit 2 avions en conflit garanti (meme temps d'arrivee au point P).

    Renvoie (avions, t_c) : t_c est l'instant theorique du croisement (s)."""
    px = rng.uniform(-12.0, 12.0)
    py = rng.uniform(-12.0, 12.0)
    b1 = rng.uniform(0.0, 360.0)
    b2 = (b1 + rng.choice([-1, 1]) * rng.uniform(60.0, 150.0)) % 360.0
    t_c = rng.uniform(240.0, 420.0)
    aircraft = []
    for cs, bearing in ((callsigns[0], b1), (callsigns[1], b2)):
        v = rng.uniform(240.0, 300.0)              # kt
        d = v * t_c / 3600.0                       # NM parcourus jusqu'a P
        rad = math.radians(bearing)
        x = px + d * math.sin(rad)
        y = py + d * math.cos(rad)
        lat, lon = from_nm(x, y)
        aircraft.append({"callsign": cs, "type": rng.choice(["A320", "A321", "B738"]),
                         "lat": lat, "lon": lon,
                         "hdg": (bearing + 180.0) % 360.0,
                         "alt_ft": float(fl_ft), "spd_kt": round(v)})
    return aircraft, t_c


class ExerciseEngine:
    """Genere l'exercice puis echantillonne le simulateur (~1 Hz) pour noter."""

    def __init__(self, sim, ai, emit):
        self._sim = sim
        self._ai = ai
        self._emit = emit
        self._lock = threading.Lock()
        self._thread = None
        self._active = False
        self._last_report = None
        self._reset_metrics()

    # ------------------------------------------------------------------ etat
    def _reset_metrics(self):
        self._t0 = None                 # temps simu au depart
        self._meta = {}                 # difficulte, duree, situation...
        self._minsep = []               # [[t_rel, min_nm], ...] (1 Hz)
        self._los = {}                  # key -> {pair, t_start, t_end, min_nm, open}
        self._predicted = {}            # key -> {pair, t_first, d_min}
        self._zone = {}                 # (cs, zone) -> {t_start, t_end, open}
        self._commands = []             # [{t, text, accepted, rejected}]
        self._watch = set()             # indicatifs de l'exercice
        self._predicted_now = set()     # paires actuellement en conflit predit

    @property
    def active(self):
        with self._lock:
            return self._active

    # ----------------------------------------------------------------- start
    def start(self, difficulty="moyen", duration_min=None, seed=None):
        if self.active:
            raise RuntimeError("un exercice est deja en cours")
        cfg = DIFFICULTIES.get(difficulty)
        if not cfg:
            raise ValueError(f"difficulte inconnue : {difficulty!r} "
                             f"(choix : {', '.join(DIFFICULTIES)})")
        rng = random.Random(seed)
        duration_min = float(duration_min or cfg["duration_min"])

        self._sim.reset()                          # radar vierge (vide la file avant)
        aircraft, conflicts = [], []
        used = set()

        def new_cs():
            while True:
                cs = f"{rng.choice(_AIRLINES)}{rng.randint(100, 999)}"
                if cs not in used:
                    used.add(cs)
                    return cs

        for _ in range(cfg["pairs"]):
            fl = rng.choice([28000, 30000, 32000, 34000])
            pair_ac, t_c = make_conflict_pair(rng, [new_cs(), new_cs()], fl)
            aircraft += pair_ac
            conflicts.append({"pair": [a["callsign"] for a in pair_ac],
                              "fl": fl // 100, "t_cross_s": round(t_c)})

        filler = []
        for _ in range(cfg["filler"]):
            tpl = rng.choice(_FILLER_TEMPLATES)
            desc = tpl.format(dir=rng.choice(["north", "south", "east", "west"]),
                              fl=rng.choice([240, 260, 360, 380]),
                              hdg=rng.choice([90, 180, 270, 360]))
            filler += self._ai.scenario(desc)
        # remplissage : indicatifs uniques + FL disjoints des conflits (figurants)
        filler = [f for f in filler if f["callsign"] not in used]
        for f in filler:
            used.add(f["callsign"])
        aircraft += filler

        created = self._sim.create_aircraft(aircraft)

        wind = None
        if cfg["wind"]:
            wind = {"dir": rng.randrange(0, 360, 10),
                    "spd": rng.randint(*cfg["wind"])}
            self._sim.set_wind(wind["dir"], wind["spd"])
        storm = None
        if cfg["storm"]:
            ang = rng.uniform(0, 2 * math.pi)
            d = rng.uniform(12, 28)
            sx, sy = d * math.cos(ang), d * math.sin(ang)
            lat, lon = from_nm(sx, sy)
            storm = {"x": round(sx, 1), "y": round(sy, 1), "r": rng.randint(10, 14)}
            self._sim.add_zone("storm", "CIRCLE", [lat, lon, storm["r"]])
        if cfg["turb"]:
            self._sim.set_turbulence(cfg["turb"])

        objectives = [f"Maintenir la séparation : {SEP_NM:.0f} NM / {SEP_FT:.0f} ft "
                      f"entre tous les aéronefs",
                      f"Résoudre les {cfg['pairs']} conflit(s) programmé(s) avant "
                      f"perte de séparation"]
        if storm:
            objectives.append("Garder le trafic hors de la cellule orageuse")
        if wind:
            objectives.append(f"Composer avec le vent {wind['dir']:03d}°/{wind['spd']} kt")
        objectives.append(f"Durée : {duration_min:.0f} min (temps simulé)")

        with self._lock:
            self._reset_metrics()
            self._watch = set(used)
            self._meta = {"difficulty": difficulty, "label": cfg["label"],
                          "duration_s": duration_min * 60.0,
                          "started_iso": datetime.now().isoformat(timespec="seconds"),
                          "mode_ia": self._ai.mode(), "seed": seed,
                          "aircraft": sorted(used), "created": created,
                          "conflicts_built": conflicts, "wind": wind, "storm": storm,
                          "turbulence": cfg["turb"], "objectives": objectives}
            self._active = True
        self._thread = threading.Thread(target=self._run, name="atc-exercise", daemon=True)
        self._thread.start()
        self._emit({"type": "exercise_started", **self.state()})
        return self.state()

    # ------------------------------------------------------- boucle de mesure
    def _run(self):
        while self.active:
            try:
                self._sample(self._sim.snapshot())
            except Exception:
                pass
            time.sleep(1.0)

    def _sample(self, snap):
        t = float(snap.get("t", 0.0))
        with self._lock:
            if self._t0 is None:
                self._t0 = t
            rel = t - self._t0
            acs = snap.get("aircraft", [])
            pos = {a["id"]: a for a in acs}

            # separation minimale globale (paires non separees verticalement)
            best = None
            for i in range(len(acs)):
                for j in range(i + 1, len(acs)):
                    a, b = acs[i], acs[j]
                    if abs(a["alt_ft"] - b["alt_ft"]) >= SEP_FT:
                        continue
                    d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
                    best = d if best is None else min(best, d)
            self._minsep.append([round(rel, 1), round(best, 2) if best is not None else None])

            # pertes de separation (ouverture / fermeture / distance mini)
            now_los = set()
            for pair in snap.get("conflicts", []):
                key = _pair_key(pair)
                now_los.add(key)
                a, b = pos.get(pair[0]), pos.get(pair[1])
                d = round(math.hypot(a["x"] - b["x"], a["y"] - b["y"]), 2) if a and b else None
                ev = self._los.get(key)
                if ev is None:
                    self._los[key] = {"pair": sorted(pair), "t_start": round(rel, 1),
                                      "t_end": None, "min_nm": d, "open": True}
                    self._emit({"type": "exercise_event", "kind": "los",
                                "pair": sorted(pair), "t": round(rel)})
                else:
                    ev["open"] = True
                    ev["t_end"] = None
                    if d is not None and (ev["min_nm"] is None or d < ev["min_nm"]):
                        ev["min_nm"] = d
            for key, ev in self._los.items():
                if key not in now_los and ev["t_end"] is None:
                    ev["t_end"] = round(rel, 1)
                    ev["open"] = False

            # conflits predits (CPA) observes
            for p in snap.get("predicted", []):
                key = _pair_key(p["pair"])
                ev = self._predicted.get(key)
                if ev is None:
                    self._predicted[key] = {"pair": sorted(p["pair"]),
                                            "t_first": round(rel, 1), "d_min": p.get("d")}
                    self._emit({"type": "exercise_event", "kind": "predicted",
                                "pair": sorted(p["pair"]), "t": round(rel),
                                "tcpa": p.get("t"), "dcpa": p.get("d")})
                elif p.get("d") is not None and (ev["d_min"] is None or p["d"] < ev["d_min"]):
                    ev["d_min"] = p["d"]
            self._predicted_now = {_pair_key(p["pair"]) for p in snap.get("predicted", [])}

            # penetrations de zone
            for a in acs:
                if a.get("inzone"):
                    k = (a["id"], a["inzone"])
                    ev = self._zone.get(k)
                    if ev is None:
                        self._zone[k] = {"callsign": a["id"], "zone": a["inzone"],
                                         "t_start": round(rel, 1), "t_end": None, "open": True}
                        self._emit({"type": "exercise_event", "kind": "zone",
                                    "callsign": a["id"], "zone": a["inzone"], "t": round(rel)})
            inzone_now = {(a["id"], a["inzone"]) for a in acs if a.get("inzone")}
            for k, ev in self._zone.items():
                if k not in inzone_now and ev["t_end"] is None:
                    ev["t_end"] = round(rel, 1)
                    ev["open"] = False

            done = rel >= self._meta["duration_s"]
        if done:
            self.stop(auto=True)

    # ------------------------------------------------------------- commandes
    def note_command(self, text, n_accepted, n_rejected):
        """Appele par le serveur a chaque clairance de l'eleve."""
        with self._lock:
            if not self._active or self._t0 is None:
                return
            self._commands.append({"t": self._elapsed_unlocked(), "text": text,
                                   "accepted": int(n_accepted), "rejected": int(n_rejected)})

    # --------------------------------------------------------------- scoring
    def _score_unlocked(self, rel):
        """Bareme documente dans docs/VALIDATION.md (par. 6). Appeler sous verrou."""
        n_los = len(self._los)
        t_los = sum((ev["t_end"] if ev["t_end"] is not None else rel) - ev["t_start"]
                    for ev in self._los.values())
        s_sep = max(0.0, 50.0 - 25.0 * n_los - 0.5 * t_los)

        predicted = set(self._predicted)
        unresolved = set(self._los) | getattr(self, "_predicted_now", set())
        resolved = predicted - unresolved
        s_conf = 20.0 * len(resolved) / len(predicted) if predicted else 20.0

        n_zone = len(self._zone)
        t_zone = sum((ev["t_end"] if ev["t_end"] is not None else rel) - ev["t_start"]
                     for ev in self._zone.values())
        s_zone = max(0.0, 15.0 - 5.0 * n_zone - 0.1 * t_zone)

        acc = sum(c["accepted"] for c in self._commands)
        rej = sum(c["rejected"] for c in self._commands)
        s_radio = 15.0 * acc / (acc + rej) if (acc + rej) else 15.0

        total = max(0.0, min(100.0, s_sep + s_conf + s_zone + s_radio))
        return {"total": round(total, 1), "grade": grade(total),
                "separation": round(s_sep, 1), "conflits": round(s_conf, 1),
                "zones": round(s_zone, 1), "radio": round(s_radio, 1),
                "n_los": n_los, "t_los_s": round(t_los, 1),
                "conflits_predits": len(predicted), "conflits_resolus": len(resolved),
                "n_zone": n_zone, "t_zone_s": round(t_zone, 1),
                "cmd_acceptees": acc, "cmd_rejetees": rej}

    def _elapsed_unlocked(self):
        if self._t0 is None or not self._minsep:
            return 0.0
        return self._minsep[-1][0]

    # ------------------------------------------------------------------- api
    def state(self):
        """Etat live (objectifs, temps ecoule, score courant)."""
        with self._lock:
            if not self._active:
                return {"active": False,
                        "last_report": bool(self._last_report)}
            rel = self._elapsed_unlocked()
            return {"active": True, **self._meta,
                    "elapsed_s": round(rel, 1),
                    "remaining_s": max(0.0, round(self._meta["duration_s"] - rel, 1)),
                    "score": self._score_unlocked(rel)}

    def stop(self, auto=False):
        """Termine l'exercice, calcule et archive le rapport de debrief."""
        with self._lock:
            if not self._active:
                return self._last_report
            self._active = False
            rel = self._elapsed_unlocked()
            for ev in self._los.values():
                if ev["t_end"] is None:
                    ev["t_end"] = round(rel, 1)
                    ev["open"] = False
            for ev in self._zone.values():
                if ev["t_end"] is None:
                    ev["t_end"] = round(rel, 1)
                    ev["open"] = False
            report = {**self._meta,
                      "ended_iso": datetime.now().isoformat(timespec="seconds"),
                      "auto_ended": auto, "elapsed_s": round(rel, 1),
                      "score": self._score_unlocked(rel),
                      "minsep_series": self._minsep,
                      "los_events": list(self._los.values()),
                      "predicted_events": list(self._predicted.values()),
                      "zone_events": list(self._zone.values()),
                      "commands": self._commands}
            self._last_report = report
        self._save(report)
        self._emit({"type": "exercise_ended", "auto": auto,
                    "score": report["score"], "elapsed_s": report["elapsed_s"]})
        return report

    def last_report(self):
        with self._lock:
            return self._last_report

    @staticmethod
    def _save(report):
        try:
            os.makedirs(REPORTS_DIR, exist_ok=True)
            name = f"exercice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(os.path.join(REPORTS_DIR, name), "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=1)
        except Exception:
            pass
