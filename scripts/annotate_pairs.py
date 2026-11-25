"""Annotate, check, and preview region pairs in data/annotations/pairs.json. Author: Aliza.

Subcommands:

  add IMAGE_ID      Click polygon a, press Enter; click polygon b, press Enter; type a note.
                    Left-click adds a vertex, right-click removes the last one.
  check             Validate every pair against the manifest and image sizes, then set
                    has_pairs (0/1) in data/manifest.csv to match pairs.json.
  preview [IDS...]  Write overlay PNGs (a = cyan, b = magenta) for a visual spot-check.

Examples:
  python -m scripts.annotate_pairs add charts_0012
  python -m scripts.annotate_pairs check
  python -m scripts.annotate_pairs preview --out results/annotation_previews
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

from chromafix.eval.annotations import dump_pairs, load_pairs, next_pair_id, pair_masks
from chromafix.eval.dataset import MANIFEST_FIELDS, read_manifest


def image_size(root: Path, row: dict[str, str]) -> tuple[int, int]:
    """Return (height, width) of a manifest image."""
    with Image.open(root / row["file"]) as im:
        return im.height, im.width


def check(manifest: Path, pairs_path: Path, root: Path, write: bool = True) -> list[str]:
    """Validate pairs.json against the manifest and images; optionally sync has_pairs.

    Args:
        manifest: Path to data/manifest.csv.
        pairs_path: Path to data/annotations/pairs.json.
        root: Repo root for manifest file paths.
        write: Rewrite has_pairs in the manifest.

    Returns:
        Problems found (empty when everything is valid).
    """
    rows = read_manifest(manifest)
    by_id = {r["image_id"]: r for r in rows}
    pairs_by_image = load_pairs(pairs_path)
    problems = []
    for image_id, pairs in pairs_by_image.items():
        if image_id not in by_id:
            problems.append(f"{image_id}: not in manifest")
            continue
        path = root / by_id[image_id]["file"]
        if not path.exists():
            problems.append(f"{image_id}: image file missing at {path}")
            continue
        shape = image_size(root, by_id[image_id])
        for pair in pairs:
            try:
                pair_masks(pair, shape)
            except ValueError as exc:
                problems.append(f"{pair['pair_id']}: {exc}")
    if write and not problems:
        for r in rows:
            r["has_pairs"] = "1" if pairs_by_image.get(r["image_id"]) else "0"
        with manifest.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    return problems


def coverage(manifest: Path, pairs_path: Path) -> Counter:
    """Count annotated images and pairs per split."""
    rows = read_manifest(manifest)
    pairs_by_image = load_pairs(pairs_path)
    counts: Counter = Counter()
    for r in rows:
        n = len(pairs_by_image.get(r["image_id"], []))
        if n:
            counts[f"{r['split']} images"] += 1
            counts[f"{r['split']} pairs"] += n
    return counts


def preview(image_id: str, row: dict[str, str], pairs: list[dict], root: Path, out: Path) -> Path:
    """Save the image with its pair polygons drawn on top; return the PNG path."""
    with Image.open(root / row["file"]) as im:
        canvas = im.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    for pair in pairs:
        for key, color in (("a", (0, 255, 255)), ("b", (255, 0, 255))):
            pts = [tuple(p) for p in pair[key]]
            draw.line(pts + [pts[0]], fill=color, width=3)
            draw.text(pts[0], f"{pair['pair_id'].rsplit('_', 1)[1]}{key}", fill=color)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{image_id}.png"
    canvas.save(dest)
    return dest


def add(image_id: str, row: dict[str, str], pairs_path: Path, root: Path) -> int:
    """Interactively add pairs for one image. Returns how many pairs were added."""
    import matplotlib.pyplot as plt

    pairs_by_image = load_pairs(pairs_path)
    existing = list(pairs_by_image.get(image_id, []))
    with Image.open(root / row["file"]) as im:
        pixels = im.convert("RGB")
    shape = (pixels.height, pixels.width)
    added = 0
    while True:
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.imshow(pixels)
        polys = {}
        for key in ("a", "b"):
            ax.set_title(f"{image_id}: click region {key}, Enter to finish (right-click = undo)")
            fig.canvas.draw()
            pts = plt.ginput(n=-1, timeout=0)
            polys[key] = [[round(x, 1), round(y, 1)] for x, y in pts]
            if len(pts) >= 3:
                ax.fill(*zip(*pts), alpha=0.3, color="cyan" if key == "a" else "magenta")
        plt.close(fig)
        pair = {"pair_id": next_pair_id(image_id, existing), **polys}
        try:
            pair_masks(pair, shape)
        except ValueError as exc:
            print(f"Not saved: {exc}")
        else:
            pair["note"] = input("Note (e.g. 'red line vs green line'): ").strip()
            existing.append(pair)
            pairs_by_image[image_id] = existing
            pairs_path.write_text(dump_pairs(pairs_by_image), encoding="utf-8")
            added += 1
            print(f"Saved {pair['pair_id']}")
        if input("Another pair on this image? [y/N] ").strip().lower() != "y":
            return added


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    ap.add_argument("--pairs", type=Path, default=Path("data/annotations/pairs.json"))
    ap.add_argument("--root", type=Path, default=Path("."))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add", help="annotate one image interactively")
    p_add.add_argument("image_id")
    p_check = sub.add_parser("check", help="validate pairs.json and sync has_pairs")
    p_check.add_argument("--no-write", action="store_true", help="validate only")
    p_prev = sub.add_parser("preview", help="write overlay PNGs")
    p_prev.add_argument("image_ids", nargs="*", help="default: every annotated image")
    p_prev.add_argument("--out", type=Path, default=Path("results/annotation_previews"))
    args = ap.parse_args()

    rows = {r["image_id"]: r for r in read_manifest(args.manifest)}
    if args.cmd == "add":
        if args.image_id not in rows:
            raise SystemExit(f"{args.image_id} is not in {args.manifest}")
        n = add(args.image_id, rows[args.image_id], args.pairs, args.root)
        print(f"Added {n} pair(s). Run 'check' to update has_pairs.")
    elif args.cmd == "check":
        problems = check(args.manifest, args.pairs, args.root, write=not args.no_write)
        for p in problems:
            print("PROBLEM:", p)
        counts = coverage(args.manifest, args.pairs)
        print(", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "No pairs yet.")
        if problems:
            raise SystemExit(1)
    else:
        pairs_by_image = load_pairs(args.pairs)
        for image_id in args.image_ids or sorted(pairs_by_image):
            dest = preview(
                image_id, rows[image_id], pairs_by_image.get(image_id, []), args.root, args.out
            )
            print(dest)


if __name__ == "__main__":
    main()
