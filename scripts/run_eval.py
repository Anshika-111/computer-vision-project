"""Evaluate available recoloring conditions on annotated test images.

Always evaluates the no-correction baseline. Other methods can be supplied as
``module:function`` callables accepting (linear_image, cvd_type, severity).
No experimental measurements are fabricated when annotations/methods are missing.
"""
from __future__ import annotations

import argparse
import csv
import importlib
from pathlib import Path
import numpy as np
from chromafix.color import load_image
from chromafix.constants import CVD_TYPES, EVAL_SEVERITIES
from chromafix.eval.annotations import load_annotations, pair_masks
from chromafix.eval.metrics import naturalness, pair_distinguishability, pairs_below_jnd
from chromafix.simulate import simulate

FIELDS = ["image_id", "category", "method", "cvd_type", "severity", "pair_count", "mean_de00", "fraction_below_jnd", "naturalness_de00"]


def load_method(spec: str):
    if ":" not in spec:
        raise ValueError("Method must be module:function")
    module, function = spec.split(":", 1)
    fn = getattr(importlib.import_module(module), function)
    if not callable(fn):
        raise ValueError(f"Not callable: {spec}")
    return fn


def evaluate(manifest: Path, annotations: Path, output: Path, root: Path,
             methods: dict | None = None, cvd_types=CVD_TYPES, severities=EVAL_SEVERITIES) -> list[dict]:
    methods = {"none": lambda img, cvd_type, severity: img, **(methods or {})}
    pairs_by_image = load_annotations(annotations)
    with manifest.open(encoding="utf-8", newline="") as f:
        images = list(csv.DictReader(f))
    results = []
    for row in images:
        if row.get("split") != "test":
            continue
        image_id = row["image_id"]
        pairs = pairs_by_image.get(image_id, [])
        if not pairs:
            continue  # cannot compute distinguishability without real annotations
        path = root / row["file"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing annotated image: {path}")
        original = load_image(path)
        masks = [pair_masks(p, original.shape[:2]) for p in pairs]
        for cvd_type in cvd_types:
            for severity in severities:
                for method, recolor in methods.items():
                    corrected = np.asarray(recolor(original.copy(), cvd_type, severity))
                    if corrected.shape != original.shape or not np.isfinite(corrected).all() or (corrected < 0).any() or (corrected > 1).any():
                        raise ValueError(f"{method} produced invalid linear RGB image")
                    seen = simulate(corrected, cvd_type, float(severity))
                    differences = np.array([pair_distinguishability(seen, a, b) for a, b in masks])
                    results.append(dict(image_id=image_id, category=row["category"], method=method,
                                        cvd_type=cvd_type, severity=severity, pair_count=len(masks),
                                        mean_de00=float(differences.mean()),
                                        fraction_below_jnd=pairs_below_jnd(differences),
                                        naturalness_de00=naturalness(original, corrected)))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    ap.add_argument("--annotations", type=Path, default=Path("data/annotations/pairs.json"))
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, default=Path("results/recolor_metrics.csv"))
    for name in ("fixed", "personalized", "neural"):
        ap.add_argument(f"--{name}", help=f"Optional {name} implementation: module:function")
    args = ap.parse_args()
    methods = {name: load_method(getattr(args, name)) for name in ("fixed", "personalized", "neural") if getattr(args, name)}
    rows = evaluate(args.manifest, args.annotations, args.out, args.root, methods)
    print(f"Wrote {len(rows)} evaluation rows to {args.out}")
    if not rows:
        print("No annotated test images yet. Add real pairs to data/annotations/pairs.json before evaluating.")


if __name__ == "__main__":
    main()
