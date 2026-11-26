"""CIEDE2000 evaluation metrics: distinguishability, naturalness, JND share. Author: Aliza.

Signatures follow CLAUDE.md Section 6. Every color difference is CIEDE2000 via
``chromafix.color.delta_e00``; anything tuned or reported must import these functions.
"""

from __future__ import annotations

import numpy as np

from chromafix.color import delta_e00, linear_to_lab
from chromafix.constants import JND_DE00
from chromafix.eval.annotations import pair_masks
from chromafix.simulate import simulate


def _check_image(img: np.ndarray, name: str = "img") -> np.ndarray:
    img = np.asarray(img)
    if img.ndim != 3 or img.shape[-1] != 3:
        raise ValueError(f"{name} must have shape (H, W, 3), got {img.shape}")
    return img


def pair_distinguishability(
    img: np.ndarray, pairs: list[dict], cvd_type: str, severity: float
) -> np.ndarray:
    """How different each annotated region pair looks to a simulated CVD viewer.

    Simulates ``img`` for ``cvd_type`` at ``severity``, converts every pixel to CIELAB,
    averages the Lab values inside region ``a`` and inside region ``b``, and returns the
    CIEDE2000 difference between the two means.

    Args:
        img: Linear RGB, shape (H, W, 3), values in [0, 1]. Pass the *unsimulated* image
            (original or recolored); simulation happens here.
        pairs: Pair dicts with ``a`` and ``b`` polygons in ``[x, y]`` pixel coordinates, as
            stored in ``data/annotations/pairs.json``.
        cvd_type: "normal", "protan", "deutan", or "tritan".
        severity: In [0, 1]; ignored for "normal".

    Returns:
        CIEDE2000 per pair, float64, shape (len(pairs),). Higher is better.

    Raises:
        ValueError: Bad image shape, or a polygon that is invalid for this image.
    """
    img = _check_image(img)
    if not pairs:
        return np.zeros(0, dtype=np.float64)
    lab = linear_to_lab(simulate(img, cvd_type, severity))
    out = np.empty(len(pairs), dtype=np.float64)
    for i, pair in enumerate(pairs):
        mask_a, mask_b = pair_masks(pair, img.shape[:2])
        out[i] = delta_e00(lab[mask_a].mean(axis=0), lab[mask_b].mean(axis=0))
    return out


def naturalness(original: np.ndarray, recolored: np.ndarray) -> float:
    """Mean per-pixel CIEDE2000 between two images, seen with normal vision.

    Args:
        original: Linear RGB, shape (H, W, 3), values in [0, 1].
        recolored: Linear RGB, same shape.

    Returns:
        Mean CIEDE2000 over all pixels. 0.0 for identical images; lower is better.

    Raises:
        ValueError: The shapes differ or are not (H, W, 3).
    """
    original = _check_image(original, "original")
    recolored = _check_image(recolored, "recolored")
    if original.shape != recolored.shape:
        raise ValueError(f"Shapes differ: {original.shape} vs {recolored.shape}")
    return float(np.mean(delta_e00(linear_to_lab(original), linear_to_lab(recolored))))


def pairs_below_jnd(distances: np.ndarray, threshold: float = JND_DE00) -> float:
    """Fraction of pairs whose CIEDE2000 distance is below the just-noticeable difference.

    Args:
        distances: CIEDE2000 per pair, e.g. from ``pair_distinguishability``.
        threshold: JND in CIEDE2000 units; defaults to ``constants.JND_DE00``.

    Returns:
        Fraction in [0, 1]. Lower is better.

    Raises:
        ValueError: Empty, non-finite, or negative distances, or a bad threshold.
    """
    distances = np.asarray(distances, dtype=np.float64)
    if distances.size == 0:
        raise ValueError("At least one pair distance is required")
    if not np.all(np.isfinite(distances)) or np.any(distances < 0):
        raise ValueError("Distances must be finite and nonnegative")
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("Threshold must be finite and nonnegative")
    return float(np.mean(distances < threshold))
