"""Validate color-pair polygon annotations and rasterize them into masks.

Coordinates are pixel coordinates on the *standardized* PNG image, with origin
at its top-left corner. A pair contains polygons named ``a`` and ``b``.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw


def polygon_mask(points: list[list[float]], shape: tuple[int, int]) -> np.ndarray:
    """Rasterize a polygon to a boolean (height, width) mask."""
    h, w = shape
    if h <= 0 or w <= 0 or len(points) < 3:
        raise ValueError("Image size must be positive and polygon needs >=3 vertices")
    p = np.asarray(points, dtype=float)
    if p.shape != (len(points), 2) or not np.isfinite(p).all():
        raise ValueError("Polygon must contain finite [x,y] vertices")
    if (p[:, 0] < 0).any() or (p[:, 0] >= w).any() or (p[:, 1] < 0).any() or (p[:, 1] >= h).any():
        raise ValueError("Polygon vertex outside image")
    canvas = Image.new("1", (w, h), 0)
    ImageDraw.Draw(canvas).polygon([tuple(map(float, pt)) for pt in p], fill=1)
    mask = np.asarray(canvas, dtype=bool)
    if not mask.any():
        raise ValueError("Polygon has no pixels")
    return mask


def load_annotations(path: str | Path) -> dict:
    """Return image_id -> list of pairs. Empty annotation files are valid."""
    with Path(path).open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict) or not isinstance(raw.get("images"), dict):
        raise ValueError('Annotations must have an "images" object')
    for image_id, pairs in raw["images"].items():
        if not isinstance(image_id, str) or not isinstance(pairs, list):
            raise ValueError("Each image_id must map to a list of pairs")
        for pair in pairs:
            if not isinstance(pair, dict) or "a" not in pair or "b" not in pair:
                raise ValueError(f"Malformed pair in {image_id}: expected a and b polygons")
    return raw["images"]


def pair_masks(pair: dict, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    a = polygon_mask(pair["a"], shape)
    b = polygon_mask(pair["b"], shape)
    if np.any(a & b):
        raise ValueError("Paired polygons must not overlap")
    return a, b
