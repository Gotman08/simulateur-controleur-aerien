"""Measure the existing local parser and simulator without an AI provider."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
from datetime import UTC, datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "bench")]

import numpy as np

from atc_ai import local_interpret
from atc_exercise import make_conflict_pair
from atc_sim import SimManager, to_nm
from bench_corpus import all_cases


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def command(args):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def environment():
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), platform.processor())
    memory = next((int(line.split()[1]) * 1024 for line in Path("/proc/meminfo").read_text().splitlines()
                   if line.startswith("MemTotal:")), None)
    packages = {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()}
    sources = ["src/atc_ai.py", "src/atc_sim.py", "src/atc_exercise.py", "src/bluesky_runtime.py",
               "bench/bench_corpus.py", "validation/03_parseur_eval.py", "bench/measure_local.py",
               "bench/bluesky.cfg"]
    return {
        "captured_utc": datetime.now(UTC).isoformat(),
        "git_head": command(["git", "rev-parse", "HEAD"]),
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
        "cpu": cpu, "logical_processors": os.cpu_count(), "ram_bytes": memory,
        "os": platform.freedesktop_os_release().get("PRETTY_NAME", platform.system()),
        "kernel": platform.release(), "python": platform.python_version(),
        "compiler": platform.python_compiler(), "compile_options": "CPython; no project compilation",
        "thread_limits": {name: os.environ.get(name) for name in
                          ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
        "packages": dict(sorted(packages.items())),
    }


def measure_parser(repetitions):
    cases = all_cases()
    rows, details = [], []
    for index, case in enumerate(cases):
        actual = local_interpret(case["phrase"])
        got = list(actual["trafscript"])
        details.append({"id": index, **case, "actual": got, "rejected": actual["rejected"],
                        "correct": sorted(got) == sorted(case["attendu"])})
    for count in (16, 68, len(cases)):
        for rep in range(-1, repetitions):
            indices = list(range(count))
            random.Random(20260912 + rep).shuffle(indices)
            start = time.perf_counter_ns()
            for index in indices:
                local_interpret(cases[index]["phrase"])
            elapsed = time.perf_counter_ns() - start
            rows.append({"case_count": count, "repetition": rep, "warmup": rep < 0,
                         "elapsed_ns": elapsed, "ns_per_clearance": elapsed / count})
    return rows, details


def check_geometry(count):
    """Compare production predictions with direct sampling of linear trajectories."""
    rows = []
    times = np.arange(0, 300.025, 0.05)
    for seed in (42, 43, 44):
        rng = np.random.default_rng(seed)
        for index in range(count):
            x1, y1, x2, y2 = rng.uniform(-80, 80, 4)
            h1, h2 = rng.uniform(0, 360, 2)
            s1, s2 = rng.uniform(150, 550, 2)
            vx1, vy1 = s1 * math.sin(math.radians(h1)) / 3600, s1 * math.cos(math.radians(h1)) / 3600
            vx2, vy2 = s2 * math.sin(math.radians(h2)) / 3600, s2 * math.cos(math.radians(h2)) / 3600
            distance = np.hypot((x1 - x2) + (vx1 - vx2) * times,
                                (y1 - y2) + (vy1 - vy2) * times)
            minimum = int(np.argmin(distance))
            grid_t, grid_d = float(times[minimum]), float(distance[minimum])
            initial = math.hypot(x1 - x2, y1 - y2) < 5
            expected = not initial and 0 < grid_t <= 120 and grid_d < 5
            aircraft = [{"id": "A", "x": x1, "y": y1, "alt_ft": 30000, "hdg": h1, "gs": s1},
                        {"id": "B", "x": x2, "y": y2, "alt_ft": 30000, "hdg": h2, "gs": s2}]
            current, predicted = SimManager._analyze(aircraft)
            # A sampled reference cannot resolve cases very close to decision boundaries.
            ambiguous = abs(grid_t - 120) <= 0.05 or abs(grid_d - 5) < 0.01
            rows.append({"seed": seed, "case": index, "x1_nm": x1, "y1_nm": y1,
                         "x2_nm": x2, "y2_nm": y2, "h1_deg": h1, "h2_deg": h2,
                         "s1_kt": s1, "s2_kt": s2, "grid_t_s": grid_t, "grid_d_nm": grid_d,
                         "initial_loss": initial, "production_current": bool(current),
                         "expected_prediction": bool(expected), "production_prediction": bool(predicted),
                         "ambiguous_boundary": ambiguous,
                         "agreement": bool(current) == initial and bool(predicted) == expected,
                         "reported_t_s": predicted[0]["t"] if predicted else "",
                         "reported_d_nm": predicted[0]["d"] if predicted else ""})
    return rows


def check_constructed_conflicts(count):
    rows = []
    for seed in range(count):
        aircraft, promised = make_conflict_pair(random.Random(seed), ["AAA111", "BBB222"], 30000)
        values = []
        for aircraft_item in aircraft:
            x, y = to_nm(aircraft_item["lat"], aircraft_item["lon"])
            speed, heading = aircraft_item["spd_kt"] / 3600, math.radians(aircraft_item["hdg"])
            values.append((x, y, speed * math.sin(heading), speed * math.cos(heading)))
        dx, dy, vx, vy = (values[0][i] - values[1][i] for i in range(4))
        t = -(dx * vx + dy * vy) / (vx * vx + vy * vy)
        distance = math.hypot(dx + vx * t, dy + vy * t)
        rows.append({"seed": seed, "aircraft": aircraft, "announced_t_s": promised,
                     "reference_t_s": t, "reference_d_nm": distance,
                     "passes": bool(distance < 5 and 240 <= promised <= 420 and abs(t - promised) < 10)})
    return rows


def measure_bluesky(repetitions):
    import bluesky
    import bluesky_runtime as bsk

    runtime = ROOT / ".bench-runtime"
    runtime.mkdir(exist_ok=True)
    previous = Path.cwd()
    os.chdir(runtime)
    rows = []
    try:
        # Configure the dependency outside the timer, then use the unchanged
        # application wrapper for every reset, creation, state read and step.
        bluesky.init(mode="sim", detached=True, workdir=runtime,
                     configfile=ROOT / "bench/bluesky.cfg")
        bsk._BS["init"] = True
        for count in (5, 25, 100):
            for rep in range(-1, repetitions):
                bsk.reset()
                rng = np.random.default_rng(4242)
                for index in range(count):
                    bearing, radius = rng.uniform(0, 360), rng.uniform(5, 60)
                    lat = 49.25 + radius * math.cos(math.radians(bearing)) / 60
                    lon = 4.05 + radius * math.sin(math.radians(bearing)) / (60 * 0.653)
                    bsk.create(f"TST{index:03}", "A320", lat, lon, rng.uniform(0, 360),
                               30000 + 1000 * (index % 10), rng.uniform(220, 300))
                observed_count = len(bsk.state())
                if observed_count != count:
                    raise RuntimeError(f"Aircraft creation failed: expected {count}, observed {observed_count}")
                start = time.perf_counter_ns()
                simulated = bsk.advance(10)
                elapsed = time.perf_counter_ns() - start
                if simulated < 10:
                    raise RuntimeError(f"Simulation stalled after {simulated} seconds")
                rows.append({"aircraft": count, "repetition": rep, "warmup": rep < 0,
                             "elapsed_ns": elapsed, "simulated_s": simulated,
                             "real_time_factor": simulated / (elapsed * 1e-9)})
                print(f"BlueSky aircraft={count} repetition={rep} completed", flush=True)
        bsk.reset()
        return rows, {"status": "measured"}
    except Exception as error:
        return rows, {"status": "non mesuré", "reason": f"{type(error).__name__}: {error}"}
    finally:
        os.chdir(previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "bench/results/local" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S-%f"))
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--geometry-per-seed", type=int, default=500)
    parser.add_argument("--constructed", type=int, default=200)
    parser.add_argument("--skip-simulator", action="store_true")
    args = parser.parse_args()
    if args.repetitions < 2 or args.geometry_per_seed < 1 or args.constructed < 1:
        parser.error("Use at least two repetitions and positive correctness sample counts")
    output = args.output.resolve()
    if output.exists():
        parser.error("The output directory already exists; choose a new directory to keep campaigns separate")
    output.mkdir(parents=True)
    write_json(output / "environment.json", environment())
    write_json(output / "protocol.json", {"repetitions": args.repetitions, "warmups": 1,
               "parser_order_seed": 20260912, "parser_sizes": [16, 68, 116],
               "geometry_seeds": [42, 43, 44], "geometry_per_seed": args.geometry_per_seed,
               "grid_dt_s": 0.05, "grid_horizon_s": 300, "constructed_cases": args.constructed,
               "simulator_seed": 4242, "simulator_counts": [5, 25, 100],
               "simulated_s_per_trial": 10, "summary": "median and linearly interpolated quartiles"})
    parser_rows, cases = measure_parser(args.repetitions)
    write_csv(output / "parser_timing.csv", parser_rows)
    write_json(output / "parser_cases.json", cases)
    print(f"Parser: {sum(case['correct'] for case in cases)}/{len(cases)} exact", flush=True)
    geometry = check_geometry(args.geometry_per_seed)
    write_csv(output / "geometry.csv", geometry)
    constructed = check_constructed_conflicts(args.constructed)
    write_json(output / "constructed_conflicts.json", constructed)
    if args.skip_simulator:
        simulator_rows, status = [], {"status": "non mesuré", "reason": "Skipped explicitly by --skip-simulator"}
    else:
        simulator_rows, status = measure_bluesky(args.repetitions)
    write_csv(output / "bluesky_timing.csv", simulator_rows)
    write_json(output / "simulator_status.json", status)
    write_json(output / "unmeasured.json", {
        "STT, LLM, TTS, complete voice loop": "non mesuré: no model services configured for this WSL campaign",
        "ROMEO cluster": "non mesuré: this campaign uses the local WSL machine",
    })
    print(json.dumps({"geometry_agreements": sum(row["agreement"] for row in geometry),
                      "geometry_cases": len(geometry), "constructed_passes": sum(row["passes"] for row in constructed),
                      "constructed_cases": len(constructed), "simulator": status}), flush=True)
    runtime = ROOT / ".bench-runtime"
    runtime.mkdir(exist_ok=True)
    (runtime / "latest-campaign.txt").write_text(str(output), encoding="utf-8")
    print(f"Completed campaign: {output}", flush=True)


if __name__ == "__main__":
    main()
