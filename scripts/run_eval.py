"""Evaluate every recoloring method on the test split. Author: Aliza.

For each test image x CVD type x severity x method, recolors with
``chromafix.recolor.recolor`` and writes one row to ``results/recolor_metrics.csv``
(columns from CLAUDE.md Section 7):

  pair_de00_mean   mean CIEDE2000 between annotated region pairs after simulation (higher better)
  pairs_below_jnd  fraction of those pairs below JND_DE00 (lower better)
  naturalness      mean per-pixel CIEDE2000 to the original, normal vision (lower better)

Images without annotated pairs still get a naturalness value; their pair columns are blank.
Methods that are not available yet (personalized before tuning, neural without a model)
are skipped with a message, never filled in.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections.abc import Iterable
from pathlib import Path

import numpy as np

from chromafix.constants import CVD_TYPES, EVAL_SEVERITIES, METHODS
from chromafix.eval.dataset import load_split
from chromafix.eval.metrics import naturalness, pair_distinguishability, pairs_below_jnd
from chromafix.profile import CVDProfile
from chromafix.recolor import NeuralModelUnavailable, recolor

FIELDS = [
    "image_id",
    "category",
    "cvd_type",
    "severity",
    "method",
    "pair_de00_mean",
    "pairs_below_jnd",
    "naturalness",
]


def evaluate(
    manifest: Path,
    pairs: Path,
    root: Path,
    methods: Iterable[str] = METHODS,
    cvd_types: Iterable[str] = CVD_TYPES,
    severities: Iterable[float] = EVAL_SEVERITIES,
    annotated_only: bool = False,
    log=print,
) -> list[dict]:
    """Run the evaluation grid on the test split.

    Args:
        manifest: Path to data/manifest.csv.
        pairs: Path to data/annotations/pairs.json.
        root: Repo root for manifest file paths.
        methods: Subset of METHODS to run.
        cvd_types: CVD types to evaluate.
        severities: Severities to evaluate.
        annotated_only: Skip test images that have no pairs.
        log: Where progress and skip messages go.

    Returns:
        One dict per row, keys = FIELDS. Unavailable methods produce no rows.
    """
    methods = list(methods)
    unavailable: dict[str, str] = {}
    rows: list[dict] = []
    for item in load_split("test", manifest, pairs, root, annotated_only=annotated_only):
        natural_cache: dict[bytes, float] = {}
        for cvd_type in cvd_types:
            for severity in severities:
                profile = CVDProfile(type=cvd_type, severity=float(severity))
                for method in methods:
                    if method in unavailable:
                        continue
                    try:
                        out = recolor(item.img, profile, method)
                    except (NotImplementedError, NeuralModelUnavailable) as exc:
                        unavailable[method] = str(exc)
                        log(f"Skipping method {method!r}: {exc}")
                        continue
                    if out.shape != item.img.shape or not np.isfinite(out).all():
                        raise ValueError(f"{method} returned an invalid image for {item.image_id}")
                    key = hashlib.blake2b(np.ascontiguousarray(out).tobytes()).digest()
                    if key not in natural_cache:
                        natural_cache[key] = naturalness(item.img, out)
                    row = dict(
                        image_id=item.image_id,
                        category=item.category,
                        cvd_type=cvd_type,
                        severity=severity,
                        method=method,
                        pair_de00_mean="",
                        pairs_below_jnd="",
                        naturalness=round(natural_cache[key], 4),
                    )
                    if item.pairs:
                        d = pair_distinguishability(out, item.pairs, cvd_type, severity)
                        row["pair_de00_mean"] = round(float(d.mean()), 4)
                        row["pairs_below_jnd"] = round(pairs_below_jnd(d), 4)
                    rows.append(row)
        log(f"{item.image_id}: done")
    return rows


def write_rows(rows: list[dict], output: Path) -> None:
    """Write rows to CSV with the contract header (header only if there are no rows)."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    ap.add_argument("--pairs", type=Path, default=Path("data/annotations/pairs.json"))
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, default=Path("results/recolor_metrics.csv"))
    ap.add_argument("--methods", nargs="+", default=list(METHODS), choices=METHODS)
    ap.add_argument("--types", nargs="+", default=list(CVD_TYPES), choices=CVD_TYPES)
    ap.add_argument("--severities", nargs="+", type=float, default=list(EVAL_SEVERITIES))
    ap.add_argument(
        "--annotated-only", action="store_true", help="only test images with pairs (faster)"
    )
    args = ap.parse_args()
    rows = evaluate(
        args.manifest,
        args.pairs,
        args.root,
        args.methods,
        args.types,
        args.severities,
        args.annotated_only,
    )
    write_rows(rows, args.out)
    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
