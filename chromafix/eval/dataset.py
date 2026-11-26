"""Read the dataset manifest and load a split with its annotations. Author: Aliza.

The tune split (30 images) is the only data allowed for tuning or model selection
(CLAUDE.md Section 7). Tuning code should call ``load_split("tune")``; evaluation uses
``load_split("test")``.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from chromafix.color import load_image
from chromafix.eval.annotations import load_pairs

SPLITS = ("test", "tune")
MANIFEST_FIELDS = (
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
)


@dataclass(frozen=True)
class DatasetImage:
    """One dataset image with its annotated region pairs.

    Attributes:
        image_id: e.g. ``charts_0012``.
        category: Dataset category.
        img: Linear RGB, float32, shape (H, W, 3), values in [0, 1].
        pairs: Pair dicts from ``pairs.json``; empty if the image is not annotated.
    """

    image_id: str
    category: str
    img: np.ndarray
    pairs: list[dict]


def read_manifest(path: str | Path = "data/manifest.csv") -> list[dict[str, str]]:
    """Read ``data/manifest.csv`` and check its header.

    Args:
        path: Manifest path.

    Returns:
        One dict per row, all values as strings.

    Raises:
        ValueError: The header does not match CLAUDE.md Section 7.
    """
    with Path(path).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != MANIFEST_FIELDS:
            raise ValueError(f"Manifest header must be {','.join(MANIFEST_FIELDS)}")
        return list(reader)


def split_ids(rows: list[dict[str, str]], split: str) -> list[str]:
    """Image ids in one split, in manifest order.

    Args:
        rows: Manifest rows from ``read_manifest``.
        split: "test" or "tune".

    Returns:
        Image ids whose ``split`` column equals ``split``.
    """
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")
    return [r["image_id"] for r in rows if r["split"] == split]


def load_split(
    split: str,
    manifest: str | Path = "data/manifest.csv",
    pairs: str | Path = "data/annotations/pairs.json",
    root: str | Path = ".",
    annotated_only: bool = False,
) -> Iterator[DatasetImage]:
    """Yield the images of one split, loaded as linear RGB, with their pairs.

    Args:
        split: "test" or "tune".
        manifest: Path to ``data/manifest.csv``.
        pairs: Path to ``data/annotations/pairs.json``.
        root: Repo root that manifest ``file`` paths are relative to.
        annotated_only: Skip images that have no pairs.

    Yields:
        ``DatasetImage`` per image, in manifest order.

    Raises:
        FileNotFoundError: An image listed in the manifest is missing (download it from
            the team Drive into ``data/images/``).
    """
    rows = read_manifest(manifest)
    by_id = {r["image_id"]: r for r in rows}
    pairs_by_image = load_pairs(pairs)
    for image_id in split_ids(rows, split):
        image_pairs = pairs_by_image.get(image_id, [])
        if annotated_only and not image_pairs:
            continue
        row = by_id[image_id]
        path = Path(root) / row["file"]
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing; sync data/images from the team Drive")
        yield DatasetImage(image_id, row["category"], load_image(path), image_pairs)
