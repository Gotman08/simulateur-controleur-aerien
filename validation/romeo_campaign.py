"""Reproducible real-BlueSky and HTTP/WebSocket campaigns (one process per case).

Run from the repository root: python validation/romeo_campaign.py sim --aircraft 100 --seed 2
No STT/LLM/TTS inference is simulated or claimed by this campaign.
"""
import argparse
import asyncio
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import socket
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import psutil


def summarize(values):
    values = sorted(values)
    return {"median_ms": round(statistics.median(values) * 1000, 2),
            "p95_ms": round(values[min(len(values) - 1, math.ceil(len(values) * .95) - 1)] * 1000, 2),
            "max_ms": round(max(values) * 1000, 2)}


def simulation(count, seed):
    import numpy as np
    import bluesky_runtime as bsk
    from atc_sim import SimManager, from_nm

    rng = random.Random(seed)
    np.random.seed(seed)
    sim = SimManager()
    bsk.reset()
    sim._define_sector_fixes()
    sim._enable_cd()
    initial_time = float(bsk.bs().sim.simt)
    for i in range(count):
        lat, lon = from_nm(rng.uniform(-45, 45), rng.uniform(-40, 40))
        sim.create_aircraft([{"callsign": f"TST{i:04}", "type": "A320", "lat": lat, "lon": lon,
                              "hdg": rng.uniform(0, 360), "alt_ft": rng.choice([28000, 30000, 32000]),
                              "spd_kt": rng.uniform(240, 300)}])
    while not sim._cmd_q.empty():
        sim._drain_queue()
    sim._update_snapshot(False, 1)
    assert float(bsk.bs().sim.simt) == initial_time, "creating traffic advanced the paused clock"
    assert len(sim.snapshot()["aircraft"]) == count, "aircraft creation failed"
    assert sim.snapshot()["cd_engine"] == "bluesky", "native conflict detection unavailable"
    sim.set_wind(270, 35)
    sim.set_turbulence(1)
    lat, lon = from_nm(0, 0)
    sim.add_zone("restricted", "CIRCLE", [lat, lon, 15])
    sim.enqueue("HDG TST0000 90")
    sim.enqueue("ALT TST0000 33000")
    sim.enqueue("SPD TST0000 260")
    fix = sim._sector_fixes[0]["name"]
    sim.enqueue(f"ADDWPT TST0001 {fix}")
    sim.enqueue("LNAV TST0001 ON")
    while not sim._cmd_q.empty():
        sim._drain_queue()
    durations, snapshots, conflicts = [], [], []
    start_sim = float(bsk.bs().sim.simt)
    before_rss = psutil.Process().memory_info().rss
    for _ in range(30):
        start = time.perf_counter()
        advanced = bsk.advance(5)
        assert advanced > 0, "simulation time stalled"
        sim._update_snapshot(False, 1)
        durations.append(time.perf_counter() - start)
        start = time.perf_counter()
        snap = sim.snapshot()
        snapshots.append(time.perf_counter() - start)
        json.dumps(snap, allow_nan=False)
        assert len(snap["aircraft"]) == count
        conflicts.append(len(snap["conflicts"]))
        assert not snap["command_errors"], snap["command_errors"]
    ac0, ac1 = snap["aircraft"][:2]
    assert ac0["sel_alt_ft"] == 33000, "ALT command not applied"
    assert abs(float(bsk.bs().traf.selspd[0]) * bsk.MS2KT - 260) < 1, "SPD command not applied"
    assert abs((ac0["hdg"] - 90 + 180) % 360 - 180) < 5, "HDG command not applied"
    assert ac1["route"] and ac1["route_names"], "FMS route not exposed"
    assert snap["wind"]["spd"] == 35 and snap["turbulence"] == 1
    assert snap["zones"], "zone not exposed"
    assert any(a["cas_kt"] != a["gs"] for a in snap["aircraft"]), "airspeed/groundspeed conflated"
    end_sim = float(bsk.bs().sim.simt)
    sim.reset()
    sim._drain_queue()
    sim._update_snapshot(False, 1)
    assert sim.snapshot()["aircraft"] == []
    assert sim.snapshot()["zones"] == [] and sim.snapshot()["wind"] is None
    assert float(bsk.bs().sim.simt) == end_sim, "reset advanced the paused clock"
    return {"aircraft": count, "seed": seed, "simulated_seconds": round(end_sim - start_sim, 2),
            "step_5s": summarize(durations), "snapshot": summarize(snapshots),
            "peak_conflict_pairs": max(conflicts), "rss_mb": round(psutil.Process().memory_info().rss / 2**20, 1),
            "rss_growth_mb": round((psutil.Process().memory_info().rss - before_rss) / 2**20, 1),
            "checks": ["native CD", "finite snapshots", "ALT", "SPD", "HDG", "FMS route", "wind", "turbulence", "zones", "reset", "paused clock"]}


async def api_campaign(directory, log_path):
    import httpx
    import websockets

    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "ATC_APP_NOBROWSER": "1"}
    # Tests must not call a user's configured external AI services.
    for name in ("STT", "LLM", "TTS"):
        env[f"ATC_{name}_URL"] = ""
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "atc_app:app", "--host", "127.0.0.1",
                             "--port", str(port)], env=env, cwd=directory, stdout=log, stderr=log)
    url = f"http://127.0.0.1:{port}"
    try:
        async with httpx.AsyncClient(base_url=url, timeout=15) as client:
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError("API process exited; inspect api-server.log")
                try:
                    response = await client.get("/api/state")
                    if response.status_code == 200 and response.json().get("sim_alive"):
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(.2)
            else:
                raise RuntimeError("API did not become ready")
            response = await client.post("/api/scenario/load", json={"name": "trafic_mixte"})
            assert response.status_code == 200, response.text
            for _ in range(100):
                snap = (await client.get("/api/state")).json()
                if len(snap["aircraft"]) == 5:
                    break
                await asyncio.sleep(.1)
            assert len(snap["aircraft"]) == 5
            latencies = []
            async def reader():
                for _ in range(30):
                    start = time.perf_counter()
                    response = await client.get("/api/state")
                    response.raise_for_status()
                    assert response.json()["sim_alive"]
                    latencies.append(time.perf_counter() - start)
            async def browser():
                async with websockets.connect(f"ws://127.0.0.1:{port}/ws", max_size=2**22) as ws:
                    times = []
                    while len(times) < 20:
                        frame = json.loads(await asyncio.wait_for(ws.recv(), 5))
                        if frame["type"] == "state":
                            times.append(frame["t"])
                    assert times[-1] > times[0], "WebSocket stalled"
            await asyncio.gather(*(reader() for _ in range(12)), *(browser() for _ in range(16)))
            for endpoint, payload in [("weather/zone", {"shape": "BAD"}), ("weather/turbulence", {"level": -2}),
                                      ("command", {"text": []}), ("scenario", {"description": []})]:
                assert (await client.post(f"/api/{endpoint}", json=payload)).status_code == 400
            assert (await client.post("/api/sim/pause")).status_code == 200
            await asyncio.sleep(.3)
            t = (await client.get("/api/state")).json()["t"]
            await asyncio.sleep(.3)
            assert (await client.get("/api/state")).json()["t"] == t
            await client.post("/api/sim/reset")
            await client.post("/api/scenario/load", json={"name": "trafic_mixte"})
            await asyncio.sleep(.5)
            paused = (await client.get("/api/state")).json()
            assert paused["t"] == t, "loading/resetting traffic advanced the paused clock"
            assert len(paused["aircraft"]) == 5 and paused["paused"]
            await client.post("/api/sim/resume")
            return {"http_requests": len(latencies), "websocket_clients": 16, "frames_per_client": 20,
                    "http_latency": summarize(latencies), "checks": ["real API", "real BlueSky", "parallel readers", "pause/resume", "paused scenario load", "invalid inputs"]}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        log.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=["sim", "api"])
    parser.add_argument("--aircraft", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    result = {"case": args.case, "job_id": os.environ.get("SLURM_JOB_ID"),
              "versions": {p: importlib.metadata.version(p) for p in ("bluesky-simulator", "numpy", "fastapi")}}
    try:
        with tempfile.TemporaryDirectory(prefix="atc-campaign-") as directory:
            os.chdir(directory)
            os.environ["ATC_BLUESKY_WORKDIR"] = directory
            result.update(simulation(args.aircraft, args.seed) if args.case == "sim" else asyncio.run(api_campaign(directory, output.with_suffix(".log"))))
        result["passed"] = True
    except Exception as exc:
        result.update(passed=False, error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        result["wall_seconds"] = round(time.perf_counter() - start, 2)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))


if __name__ == "__main__":
    main()
