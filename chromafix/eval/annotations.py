"""Load, validate, and rasterize region-pair annotations. Author: Aliza.

File format (CLAUDE.md Section 7, ``data/annotations/pairs.json``)::

    [
      {"image_id": "charts_0012",
       "pairs": [{"pair_id": "charts_0012_p0",
                  "a": [[x, y], [x, y], [x, y]],
                  "b": [[x, y], [x, y], [x, y]],
                  "note": "red line vs green line"}]}
    ]

Polygons are ``[x, y]`` pixel coordinates (x = column, y = row, origin at the top-left
corner) on the standardized PNG in ``data/images/``. Region ``a`` and region ``b`` mark two
areas that a viewer must be able to tell apart.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

_IMAGE_ID = re.compile(r"[a-z_]+_\d{4}")


def polygon_mask(points: list[list[float]], shape: tuple[int, int]) -> np.ndarray:
    """Rasterize one polygon to a boolean mask.

    Args:
        points: At least three ``[x, y]`` vertices in pixel coordinates.
        shape: Image ``(height, width)``.

    Returns:
        Boolean mask, shape ``(height, width)``; True inside the polygon.

    Raises:
        ValueError: Fewer than three vertices, a vertex outside the image, or no pixels.
    """
    h, w = shape
    if h <= 0 or w <= 0 or len(points) < 3:
        raise ValueError("Image size must be positive and polygon needs >=3 vertices")
    p = np.asarray(points, dtype=float)
    if p.shape != (len(points), 2) or not np.isfinite(p).all():
        raise ValueError("Polygon must contain finite [x,y] vertices")
    if (p[:, 0] < 0).any() or (p[:, 0] > w - 1).any() or (p[:, 1] < 0).any():
        raise ValueError(f"Polygon vertex outside image of size {w}x{h}")
    if (p[:, 1] > h - 1).any():
        raise ValueError(f"Polygon vertex outside image of size {w}x{h}")
    canvas = Image.new("1", (w, h), 0)
    ImageDraw.Draw(canvas).polygon([(float(x), float(y)) for x, y in p], fill=1)
    mask = np.asarray(canvas, dtype=bool)
    if not mask.any():
        raise ValueError("Polygon has no pixels")
    return mask


def pair_masks(pair: Mapping, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Rasterize a pair's ``a`` and ``b`` polygons.

    Args:
        pair: One pair dict with ``a`` and ``b`` polygons.
        shape: Image ``(height, width)``.

    Returns:
        ``(mask_a, mask_b)``, boolean, shape ``(height, width)``.

    Raises:
        ValueError: A polygon is invalid or the two regions overlap.
    """
    a = polygon_mask(pair["a"], shape)
    b = polygon_mask(pair["b"], shape)
    if np.any(a & b):
        raise ValueError(f"Regions a and b overlap in {pair.get('pair_id', 'pair')}")
    return a, b


def _check_polygon(points: object, where: str) -> None:
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError(f"{where}: polygon needs at least 3 [x, y] vertices")
    for pt in points:
        ok = isinstance(pt, list) and len(pt) == 2
        if not ok or not all(isinstance(v, (int, float)) and np.isfinite(v) for v in pt):
            raise ValueError(f"{where}: vertex {pt!r} is not a finite [x, y] pair")


def parse_pairs(raw: object) -> dict[str, list[dict]]:
    """Validate the decoded JSON of a pairs file.

    Args:
        raw: Decoded JSON (a list of ``{"image_id", "pairs"}`` objects).

    Returns:
        ``image_id -> list of pair dicts``, in file order.

    Raises:
        ValueError: Any structural problem, with the offending image or pair named.
    """
    if not isinstance(raw, list):
        raise ValueError("pairs.json must be a JSON list of {image_id, pairs} objects")
    out: dict[str, list[dict]] = {}
    seen_pairs: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) != {"image_id", "pairs"}:
            raise ValueError(f"Each entry needs exactly image_id and pairs, got {entry!r:.80}")
        image_id = entry["image_id"]
        if not isinstance(image_id, str) or not _IMAGE_ID.fullmatch(image_id):
            raise ValueError(f"Bad image_id {image_id!r}")
        if image_id in out:
            raise ValueError(f"{image_id} appears more than once")
        if not isinstance(entry["pairs"], list):
            raise ValueError(f"{image_id}: pairs must be a list")
        for pair in entry["pairs"]:
            if not isinstance(pair, dict) or not {"pair_id", "a", "b"} <= set(pair):
                raise ValueError(f"{image_id}: each pair needs pair_id, a and b")
            pid = pair["pair_id"]
            if not isinstance(pid, str) or not re.fullmatch(rf"{image_id}_p\d+", pid):
                raise ValueError(f"{image_id}: pair_id {pid!r} must look like {image_id}_p0")
            if pid in seen_pairs:
                raise ValueError(f"Duplicate pair_id {pid}")
            seen_pairs.add(pid)
            _check_polygon(pair["a"], f"{pid}.a")
            _check_polygon(pair["b"], f"{pid}.b")
            if not isinstance(pair.get("note", ""), str):
                raise ValueError(f"{pid}: note must be a string")
        out[image_id] = entry["pairs"]
    return out


def load_pairs(path: str | Path) -> dict[str, list[dict]]:
    """Read and validate ``data/annotations/pairs.json``.

    Args:
        path: Path to the pairs file.

    Returns:
        ``image_id -> list of pair dicts``. Images without pairs are absent.
    """
    with Path(path).open(encoding="utf-8") as f:
        return parse_pairs(json.load(f))


def dump_pairs(pairs_by_image: Mapping[str, list[dict]]) -> str:
    """Serialize pairs to the contract JSON form, sorted by image_id, one vertex per line.

    Args:
        pairs_by_image: ``image_id -> list of pair dicts``.

    Returns:
        JSON text ending in a newline. Images with no pairs are dropped.
    """
    entries = [
        {"image_id": image_id, "pairs": list(pairs)}
        for image_id, pairs in sorted(pairs_by_image.items())
        if pairs
    ]
    parse_pairs(entries)
    return json.dumps(entries, indent=2) + "\n"


def next_pair_id(image_id: str, existing: Iterable[dict]) -> str:
    """Return the next free ``<image_id>_p<k>`` id."""
    used = {int(p["pair_id"].rsplit("_p", 1)[1]) for p in existing}
    k = 0
    while k in used:
        k += 1
    return f"{image_id}_p{k}"
