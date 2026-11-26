"""Plot per-method means from results/recolor_metrics.csv. Author: Aliza."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from chromafix.constants import METHODS


def plot(input_csv: Path, out_dir: Path) -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with input_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("No evaluation rows: skipping plots (no results fabricated).")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for metric, label in (
        ("pair_de00_mean", "Mean pair distinguishability (ΔE00)"),
        ("pairs_below_jnd", "Fraction of pairs below JND"),
        ("naturalness", "Mean naturalness change (ΔE00)"),
    ):
        # Aggregate by method across available test images, CVD types and severities.
        grouped = defaultdict(list)
        for row in rows:
            if row[metric] != "":  # pair columns are blank for unannotated images
                grouped[row["method"]].append(float(row[metric]))
        if not grouped:
            continue
        names = [m for m in METHODS if m in grouped]
        values = [sum(grouped[n]) / len(grouped[n]) for n in names]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(names, values)
        ax.set_ylabel(label)
        ax.set_xlabel("Recoloring method")
        ax.set_title(label + " (observed conditions only)")
        fig.tight_layout()
        fig.savefig(out_dir / f"{metric}.png", dpi=160)
        plt.close(fig)
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=Path("results/recolor_metrics.csv"))
    ap.add_argument("--out", type=Path, default=Path("results/plots"))
    args = ap.parse_args()
    print(f"Plotted {plot(args.input, args.out)} observed rows")


if __name__ == "__main__":
    main()
