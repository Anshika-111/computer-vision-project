
"""Convert downloaded images to standardized PNGs and build a reproducible manifest.

Reads a TSV/CSV export of the shared source tracker. This script does NOT
silently invent missing images, sources, licenses or annotations.
"""
from __future__ import annotations

import argparse
import csv
import random
import re
from pathlib import Path

from PIL import Image, ImageOps

from chromafix.constants import SEED


CATEGORIES = {
    "charts",
    "maps",
    "traffic",
    "food",
    "coded_items",
    "natural",
}

ALIASES = {
    "charts": "charts",
    "maps": "maps",
    "traffic": "traffic",
    "food": "food",
    "fruit": "food",
    "fruits": "food",
    "fruit/food": "food",
    "fruit (40)": "food",
    "food (40)": "food",
    "color coded items": "coded_items",
    "coded items": "coded_items",
    "coded_items": "coded_items",
    "natural scenes": "natural",
    "natural": "natural",
}

CATEGORY_COUNTS = {
    "charts": 40,
    "maps": 30,
    "traffic": 30,
    "food": 40,
    "coded_items": 30,
    "natural": 30,
}

FIELDS = [
    "image_id",
    "category",
    "file",
    "source",
    "source_url",
    "license",
    "photographer",
    "lighting",
    "split",
    "has_pairs",
]


def prepare(
    tracker: Path,
    source_root: Path,
    out: Path,
    manifest: Path,
    tune_count: int = 30,
    max_side: int = 1024,
    seed: int = SEED,
) -> int:
    if max_side < 1 or tune_count < 0:
        raise ValueError("Invalid max_side or tune_count")

    with tracker.open(encoding="utf-8-sig", newline="") as f:
        dialect = (
            csv.excel_tab
            if tracker.suffix.lower() == ".tsv"
            else csv.excel
        )
        records = list(csv.DictReader(f, dialect=dialect))

    if not records:
        raise ValueError("Source tracker is empty")

    parsed = []
    seen = set()

    for row in records:
        filename = (
            row.get("Filename")
            or row.get("filename")
            or ""
        ).strip()

        if not filename:
            continue

        if (
            Path(filename).name != filename
            or not filename.lower().endswith(
                (".png", ".jpg", ".jpeg", ".webp", ".svg")
            )
        ):
            raise ValueError(f"Invalid filename: {filename}")

        category_label = (
            row.get("Category")
            or row.get("category")
            or ""
        ).strip().lower()

        category = ALIASES.get(category_label)

        if category not in CATEGORIES:
            raise ValueError(
                f"Unknown category for {filename}: {category_label}"
            )

        original_id = Path(filename).stem
        match = re.fullmatch(r"(.+?)_(\d+)", original_id)
        if match is None:
            raise ValueError(f"Invalid image ID format: {original_id}")
        image_id = f"{match.group(1)}_{int(match.group(2)):04d}"

        if image_id in seen:
            raise ValueError(f"Duplicate image_id: {image_id}")

        seen.add(image_id)

        # Source files may be placed directly in the root
        # or in category folders.
        matches = [
            source_root / filename,
            source_root / category / filename,
            source_root
            / f"{category_label} ({CATEGORY_COUNTS[category]})"
            / filename,
        ]

        src = next(
            (p for p in matches if p.is_file()),
            None,
        )

        if src is None:
            # Match Google Drive category folders.
            found = list(source_root.glob(f"*/{filename}"))

            if len(found) == 1:
                src = found[0]

        if src is None:
            raise FileNotFoundError(
                f"Missing {filename} under {source_root}"
            )

        parsed.append((row, category, image_id, src))

    if not parsed:
        raise ValueError("No filenames found in tracker")

    if tune_count > len(parsed):
        raise ValueError(
            "Tune count exceeds available images"
        )

    rng = random.Random(seed)

    # Proportional stratification by category,
    # using largest remainders.
    groups = {
        c: [
            p[2]
            for p in parsed
            if p[1] == c
        ]
        for c in sorted(CATEGORIES)
    }

    quotas = {
        c: tune_count * len(ids) / len(parsed)
        for c, ids in groups.items()
    }

    allocations = {
        c: int(quotas[c])
        for c in groups
    }

    remainder = tune_count - sum(allocations.values())

    for c in sorted(
        groups,
        key=lambda c: (
            -(quotas[c] - allocations[c]),
            c,
        ),
    )[:remainder]:
        allocations[c] += 1

    tune_ids = set()

    for c, ids in groups.items():
        tune_ids.update(
            rng.sample(sorted(ids), allocations[c])
        )

    rows = []

    for row, category, image_id, src in parsed:
        dest = out / category / f"{image_id}.png"

        dest.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if src.suffix.lower() == ".svg":
            try:
                import cairosvg
            except ImportError as exc:
                raise RuntimeError(
                    "SVG requires cairosvg: pip install cairosvg"
                ) from exc

            import io

            raw = cairosvg.svg2png(url=str(src))
            im = Image.open(io.BytesIO(raw))
        else:
            im = Image.open(src)

        with im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail(
                (max_side, max_side),
                Image.Resampling.LANCZOS,
            )
            im.save(dest, format="PNG")

        source_type = (
            row.get("Source Type")
            or row.get("source")
            or "web"
        ).strip().lower()

        if source_type not in ("web", "team", "coco"):
            raise ValueError(
                f"Unknown source type: {source_type}"
            )

        rows.append(
            dict(
                image_id=image_id,
                category=category,
                file=dest.as_posix(),
                source=source_type,
                source_url=(
                    row.get("Source URL") or ""
                ).strip(),
                license=(
                    row.get("License") or ""
                ).strip(),
                photographer=(
                    (row.get("Collected By") or "").strip()
                    if source_type == "team"
                    else ""
                ),
                lighting="na",
                split=(
                    "tune"
                    if image_id in tune_ids
                    else "test"
                ),
                has_pairs="false",
            )
        )

    manifest.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with manifest.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__
    )

    ap.add_argument(
        "--tracker",
        required=True,
        type=Path,
        help="Google Sheet exported as CSV or TSV",
    )

    ap.add_argument(
        "--source-root",
        required=True,
        type=Path,
        help="Folder containing downloaded originals",
    )

    ap.add_argument(
        "--out",
        type=Path,
        default=Path("data/images"),
    )

    ap.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifest.csv"),
    )

    ap.add_argument(
        "--tune-count",
        type=int,
        default=30,
    )

    ap.add_argument(
        "--max-side",
        type=int,
        default=1024,
    )

    args = ap.parse_args()

    count = prepare(
        args.tracker,
        args.source_root,
        args.out,
        args.manifest,
        args.tune_count,
        args.max_side,
    )

    print(
        f"Prepared {count} images -> {args.manifest}"
    )


if __name__ == "__main__":
    main()
