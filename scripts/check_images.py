"""Check that a local data/images/ matches the dataset the repo was built on. Author: Aliza.

Images are not in git (CLAUDE.md Section 4); everyone downloads the repo-ready
``data/images/`` folder from the team Drive. That folder must be the *processed* images
written by scripts/prepare_dataset.py (PNG, longest side <= 1024 px, 4-digit names), not the
raw originals: the region-pair polygons and every evaluation number are in the processed
images' pixel coordinates.

  python -m scripts.check_images            verify data/images/ against data/image_checksums.csv
  python -m scripts.check_images --write    (Aliza) regenerate the checksum list

Exit code 1 if anything is missing, extra, the wrong size, or has different contents.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from PIL import Image

from chromafix.eval.dataset import read_manifest

FIELDS = ["image_id", "file", "width", "height", "sha256"]


def file_record(root: Path, row: dict[str, str]) -> dict:
    """Size and SHA-256 of one manifest image."""
    path = root / row["file"]
    with Image.open(path) as im:
        if im.format != "PNG":
            raise ValueError(f"{path} is {im.format}, expected PNG")
        w, h = im.size
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(image_id=row["image_id"], file=row["file"], width=w, height=h, sha256=digest)


def write_checksums(manifest: Path, root: Path, out: Path) -> int:
    """Record every manifest image's size and hash. Returns the number of images."""
    records = [file_record(root, r) for r in read_manifest(manifest)]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(records)
    return len(records)


def verify(checksums: Path, root: Path) -> list[str]:
    """Compare data/images/ under root with the checksum list. Returns problems found."""
    with checksums.open(newline="", encoding="utf-8") as f:
        expected = list(csv.DictReader(f))
    problems = []
    for e in expected:
        path = root / e["file"]
        if not path.exists():
            problems.append(f"missing  {e['file']}")
            continue
        try:
            with Image.open(path) as im:
                fmt, size = im.format, im.size
        except OSError:
            problems.append(f"unreadable {e['file']}")
            continue
        if fmt != "PNG":
            problems.append(f"not PNG  {e['file']} is {fmt} (raw original? use the processed set)")
        elif size != (int(e["width"]), int(e["height"])):
            problems.append(
                f"size     {e['file']} is {size[0]}x{size[1]}, expected "
                f"{e['width']}x{e['height']} (raw original? use the processed set)"
            )
        elif hashlib.sha256(path.read_bytes()).hexdigest() != e["sha256"]:
            problems.append(f"content  {e['file']} differs from the dataset version")
    known = {e["file"] for e in expected}
    images = root / "data" / "images"
    if images.exists():
        for p in sorted(images.rglob("*")):
            rel = p.relative_to(root).as_posix()
            if p.is_file() and not p.name.startswith(".") and rel not in known:
                problems.append(f"extra    {rel} (not in the manifest)")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    ap.add_argument("--checksums", type=Path, default=Path("data/image_checksums.csv"))
    ap.add_argument("--root", type=Path, default=Path("."), help="repo root holding data/images")
    ap.add_argument("--write", action="store_true", help="regenerate the checksum list")
    args = ap.parse_args()
    if args.write:
        n = write_checksums(args.manifest, args.root, args.checksums)
        print(f"Wrote checksums for {n} images to {args.checksums}")
        return
    problems = verify(args.checksums, args.root)
    for p in problems:
        print(p)
    if problems:
        raise SystemExit(f"{len(problems)} problem(s). Download data/images/ from the team Drive.")
    print("data/images/ matches the dataset exactly.")


if __name__ == "__main__":
    main()
