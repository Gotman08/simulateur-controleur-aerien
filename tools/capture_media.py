"""
Capture des visuels du README (PNG + GIF anime) sur l'application EN MARCHE.
============================================================================
Met en scene une situation riche via l'API (exercice Difficile : conflits
programmes, vent, cellule orageuse), selectionne un avion, puis capture :

  - docs/assets/app_radar.png        radar + strips (onglet Trafic)
  - docs/assets/app_exercice.png     exercice en cours (objectifs + score live)
  - docs/assets/app_debrief.png      debrief (score, barème, courbe de separation)
  - docs/assets/app_radar_live.gif   ~12 s de radar vivant (balayage, trainees)

Prerequis : l'application tournant sur http://127.0.0.1:8000 et
            pip install playwright && playwright install chromium

Execution : src\\bluesky-env\\Scripts\\python.exe tools\\capture_media.py
"""
import io
import os
import time

import requests
from PIL import Image
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "docs", "assets")

VIEW_W, VIEW_H = 1900, 1000      # fenetre de capture
SIDEBAR_W, TOPBAR_H = 400, 48    # geometrie de l'interface (App.tsx / TopBar.tsx)
RANGE_NM = 70.0

GIF_FRAMES = 70
GIF_WIDTH = 1040
GIF_FRAME_MS = 150


def api(method, path, **kw):
    r = requests.request(method, BASE + path, timeout=120, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


def stage_scene():
    """Exercice Difficile + une route directe + une descente : scene riche."""
    api("post", "/api/health/refresh")
    api("post", "/api/sim/reset")
    time.sleep(1.5)
    ex = api("post", "/api/exercise/start",
             json={"difficulty": "difficile", "duration_min": 15, "seed": 7})
    conflict_cs = {cs for c in ex["conflicts_built"] for cs in c["pair"]}
    time.sleep(2.0)

    st = api("get", "/api/state")
    fillers = [a["id"] for a in st["aircraft"] if a["id"] not in conflict_cs]
    if fillers:                                   # route FMS visible au radar
        api("post", "/api/command", json={"text": f"{fillers[0]} proceed direct CROSS"})
    if len(fillers) > 1:                          # fleche de descente sur les strips
        api("post", "/api/command", json={"text": f"{fillers[1]} descend flight level two two zero"})

    # avance acceleree jusqu'a l'apparition des conflits predits (lignes ambre)
    api("post", "/api/sim/speed", json={"value": 6})
    for _ in range(40):
        time.sleep(2)
        st = api("get", "/api/state")
        if st.get("predicted"):
            break
    api("post", "/api/sim/speed", json={"value": 4})
    return st


def select_aircraft_click(page, state):
    """Clique sur un avion en conflit predit -> anneau de selection cyan."""
    target = None
    pred = state.get("predicted") or []
    if pred:
        target = next((a for a in state["aircraft"] if a["id"] == pred[0]["pair"][0]), None)
    target = target or (state["aircraft"][0] if state["aircraft"] else None)
    if not target:
        return
    w, h = VIEW_W - SIDEBAR_W, VIEW_H - TOPBAR_H
    scale = (min(w, h) / 2 - 30) / (RANGE_NM * 1.05)
    px = w / 2 + target["x"] * scale
    py = h / 2 - target["y"] * scale + TOPBAR_H
    if 0 < px < w and TOPBAR_H < py < VIEW_H:
        page.mouse.click(px, py)


def shoot(page, tab_label, path, settle_ms=1800):
    """Bascule d'onglet par CLIC (un changement de hash seul ne re-rend pas la SPA)."""
    page.locator("nav button", has_text=tab_label).click()
    page.wait_for_timeout(settle_ms)
    page.screenshot(path=path)
    print(f"  [png] {os.path.relpath(path, os.path.dirname(HERE))}"
          f" ({os.path.getsize(path) // 1024} ko)")


def record_gif(page, path):
    """Frames pleine page -> GIF optimise (reduit a GIF_WIDTH px de large)."""
    frames = []
    for _ in range(GIF_FRAMES):
        t0 = time.time()
        png = page.screenshot()
        im = Image.open(io.BytesIO(png)).convert("RGB")
        ratio = GIF_WIDTH / im.width
        im = im.resize((GIF_WIDTH, round(im.height * ratio)), Image.LANCZOS)
        frames.append(im.quantize(colors=128, dither=Image.NONE))
        time.sleep(max(0.0, GIF_FRAME_MS / 1000 - (time.time() - t0)))
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=GIF_FRAME_MS, loop=0, optimize=True)
    print(f"  [gif] {os.path.relpath(path, os.path.dirname(HERE))}"
          f" ({os.path.getsize(path) // 1024} ko, {len(frames)} images)")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    print("[1] mise en scene (exercice Difficile + meteo + conflits)...")
    state = stage_scene()
    npred = len(state.get("predicted") or [])
    print(f"    {len(state['aircraft'])} avions, {npred} conflit(s) predit(s)")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": VIEW_W, "height": VIEW_H},
                                device_scale_factor=1)
        print("[2] stills...")
        page.goto(f"{BASE}/#trafic")
        page.wait_for_timeout(2500)
        select_aircraft_click(page, api("get", "/api/state"))
        page.wait_for_timeout(700)
        page.screenshot(path=os.path.join(ASSETS, "app_radar.png"))
        print("  [png] docs/assets/app_radar.png")
        shoot(page, "Exercice", os.path.join(ASSETS, "app_exercice.png"))

        print("[3] gif du radar vivant...")
        shoot_back = page.locator("nav button", has_text="Trafic")
        shoot_back.click()
        page.wait_for_timeout(1200)
        record_gif(page, os.path.join(ASSETS, "app_radar_live.gif"))

        print("[4] debrief...")
        api("post", "/api/sim/speed", json={"value": 1})
        api("post", "/api/exercise/stop")
        time.sleep(1.5)
        shoot(page, "Débrief", os.path.join(ASSETS, "app_debrief.png"))
        browser.close()
    print("[OK] visuels regeneres dans docs/assets/")


if __name__ == "__main__":
    main()
