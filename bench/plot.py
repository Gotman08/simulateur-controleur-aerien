"""Regenerate local campaign tables and theme-aware SVG figures from raw data."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def csv_rows(path):
    return list(csv.DictReader(path.open(encoding="utf-8"))) if path.exists() else []


def summarize(rows, group, metric, multiplier=1):
    result = []
    for size in sorted({int(row[group]) for row in rows}):
        values = [float(row[metric]) * multiplier for row in rows
                  if int(row[group]) == size and row["warmup"] == "False"]
        q1, median, q3 = np.quantile(values, [0.25, 0.5, 0.75], method="linear")
        result.append({"size": size, "n": len(values), "median": float(median),
                       "q1": float(q1), "q3": float(q3), "iqr": float(q3 - q1)})
    return result


def setup_theme(theme):
    background = "#ffffff" if theme == "light" else "#0d1117"
    foreground = "#24292f" if theme == "light" else "#e6edf3"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "svg.fonttype": "none", "svg.hashsalt": "atc-local-campaign",
                         "figure.facecolor": background, "axes.facecolor": background,
                         "text.color": foreground, "axes.labelcolor": foreground,
                         "axes.edgecolor": foreground, "xtick.color": foreground,
                         "ytick.color": foreground, "axes.spines.top": False,
                         "axes.spines.right": False})
    return background


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "bench/results/wsl-2026-09-12")
    parser.add_argument("--latest", action="store_true", help="Plot the last completed local campaign")
    args = parser.parse_args()
    directory = Path((ROOT / ".bench-runtime/latest-campaign.txt").read_text(encoding="utf-8")) if args.latest else args.input
    cases = json.loads((directory / "parser_cases.json").read_text(encoding="utf-8"))
    geometry = csv_rows(directory / "geometry.csv")
    constructed = json.loads((directory / "constructed_conflicts.json").read_text(encoding="utf-8"))
    timing = summarize(csv_rows(directory / "parser_timing.csv"), "case_count", "ns_per_clearance", 1e-6)
    status = json.loads((directory / "simulator_status.json").read_text(encoding="utf-8"))
    sim = summarize(csv_rows(directory / "bluesky_timing.csv"), "aircraft", "real_time_factor") if status["status"] == "measured" else []
    groups = []
    for flag, label in ((True, "Base grammar"), (False, "Extended corpus")):
        selected = [case for case in cases if case["in_grammar"] == flag]
        groups.append({"label": label, "correct": sum(case["correct"] for case in selected), "total": len(selected)})
    unambiguous = [row for row in geometry if row["ambiguous_boundary"] == "False"]
    errors = [abs(float(row["reported_d_nm"]) - float(row["grid_d_nm"]))
              for row in geometry if row["reported_d_nm"]]
    summary = {
        "parser_correct": sum(case["correct"] for case in cases), "parser_total": len(cases),
        "parser_strata": groups, "parser_timing_ms_per_clearance": timing,
        "geometry_total": len(geometry), "geometry_unambiguous": len(unambiguous),
        "geometry_disagreements": sum(row["agreement"] == "False" for row in unambiguous),
        "geometry_prediction_count": sum(row["production_prediction"] == "True" for row in geometry),
        "max_reported_dcpa_error_nm": max(errors, default=None),
        "constructed_passes": sum(row["passes"] for row in constructed), "constructed_total": len(constructed),
        "constructed_max_distance_nm": max(row["reference_d_nm"] for row in constructed),
        "bluesky_real_time_factor": sim, "simulator_status": status,
    }
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    assets = ROOT / "docs/assets"
    assets.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        background = setup_theme(theme)
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), layout="constrained")
        ax = axes[0]
        values = [100 * group["correct"] / group["total"] for group in groups]
        bars = ax.bar([group["label"] for group in groups], values,
                      color=["#0072B2", "#D55E00"], width=0.6)
        bars[1].set_hatch("//")
        for bar, value, group in zip(bars, values, groups, strict=True):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 2,
                    f"{group['correct']}/{group['total']}", ha="center")
        ax.set_ylim(0, 114)
        ax.set_ylabel("Exact command match (%)")
        ax.set_xlabel("Fixed annotated text corpus")
        ax = axes[1]
        median = np.array([row["median"] for row in timing])
        lower = np.array([row["q1"] for row in timing])
        upper = np.array([row["q3"] for row in timing])
        ax.errorbar([row["size"] for row in timing], median,
                    yerr=[median - lower, upper - median], color="#0072B2", fmt="o-", capsize=4)
        ax.set_ylabel("Median batch time / clearance (ms)")
        ax.set_xlabel("Corpus prefix (clearances)")
        ax.set_ylim(bottom=0)
        ax.set_xticks([row["size"] for row in timing])
        for extension in ("svg", "png"):
            fig.savefig(assets / f"local-parser-{theme}.{extension}", facecolor=background,
                        metadata={"Date": None} if extension == "svg" else None, dpi=160)
        plt.close(fig)
        if sim:
            fig, ax = plt.subplots(figsize=(7, 3.6), layout="constrained")
            median = np.array([row["median"] for row in sim])
            ax.errorbar([row["size"] for row in sim], median,
                        yerr=[median - [row["q1"] for row in sim], [row["q3"] for row in sim] - median],
                        color="#009E73", fmt="s-", capsize=4)
            ax.set_xlabel("Simulated aircraft (count)")
            ax.set_ylabel("Simulation speed / wall time (ratio)")
            ax.set_xticks([row["size"] for row in sim])
            ax.set_ylim(bottom=0)
            for extension in ("svg", "png"):
                fig.savefig(assets / f"local-simulator-{theme}.{extension}", facecolor=background,
                            metadata={"Date": None} if extension == "svg" else None, dpi=160)
            plt.close(fig)
    for path in assets.glob("local-*.svg"):
        path.write_text("\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()) + "\n",
                        encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
