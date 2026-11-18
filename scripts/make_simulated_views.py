"""Write CVD-simulated views of every dataset image. Author: Avneet.

Each image is saved as protan, deutan, and tritan at the evaluation severities.

Output: <out>/<cvd_type>_<severity>/<category>/<image_id>.png, e.g.
data/simulated/deutan_0.50/charts/charts_0012.png. Existing files are skipped unless
--overwrite is given.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from chromafix.color import load_image, save_image
from chromafix.constants import CVD_TYPES, EVAL_SEVERITIES
from chromafix.simulate import simulate


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    ap.add_argument("--root", type=Path, default=Path("."), help="repo root for manifest paths")
    ap.add_argument("--out", type=Path, default=Path("data/simulated"))
    ap.add_argument("--types", nargs="+", default=list(CVD_TYPES), choices=CVD_TYPES)
    ap.add_argument("--severities", nargs="+", type=float, default=list(EVAL_SEVERITIES))
    ap.add_argument("--split", choices=["test", "tune"], help="only this split (default: all)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    rows = read_manifest(args.manifest)
    if args.split:
        rows = [r for r in rows if r["split"] == args.split]
    written = skipped = missing = 0
    for row in rows:
        src = args.root / row["file"]
        if not src.exists():
            print(f"missing: {src}")
            missing += 1
            continue
        img = None
        for cvd_type in args.types:
            for severity in args.severities:
                dst = (
                    args.out
                    / f"{cvd_type}_{severity:.2f}"
                    / row["category"]
                    / f"{row['image_id']}.png"
                )
                if dst.exists() and not args.overwrite:
                    skipped += 1
                    continue
                if img is None:
                    img = load_image(src)
                dst.parent.mkdir(parents=True, exist_ok=True)
                save_image(dst, simulate(img, cvd_type, severity))
                written += 1
    print(f"{len(rows)} images: wrote {written}, skipped {skipped} existing, {missing} missing")


if __name__ == "__main__":
    main()
