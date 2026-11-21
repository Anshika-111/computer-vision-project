
"""Evaluation metrics for ChromaFix color accessibility."""

import numpy as np

from chromafix.color import delta_e00, linear_to_lab
from chromafix.constants import JND_DE00


def naturalness(original: np.ndarray, recolored: np.ndarray) -> float:
    """Mean per-pixel CIEDE2000 difference. Lower is better."""
    if original.shape != recolored.shape:
        raise ValueError("Images must have the same shape.")

    original_lab = linear_to_lab(original)
    recolored_lab = linear_to_lab(recolored)

    differences = delta_e00(original_lab, recolored_lab)
    return float(np.mean(differences))


def pair_distinguishability(
    image: np.ndarray,
    region_a: np.ndarray,
    region_b: np.ndarray,
) -> float:
    """CIEDE2000 distance between two annotated image regions.

    Args:
        image: Linear RGB image, shape (H, W, 3).
        region_a: Boolean mask, shape (H, W).
        region_b: Boolean mask, shape (H, W).

    Returns:
        CIEDE2000 difference between mean region colors.
        Higher is better.
    """
    image = np.asarray(image)
    region_a = np.asarray(region_a)
    region_b = np.asarray(region_b)

    if image.ndim != 3 or image.shape[-1] != 3:
        raise ValueError("Image must have shape (H, W, 3).")

    if region_a.shape != image.shape[:2]:
        raise ValueError("Region A mask has incorrect shape.")

    if region_b.shape != image.shape[:2]:
        raise ValueError("Region B mask has incorrect shape.")

    if region_a.dtype != np.bool_ or region_b.dtype != np.bool_:
        raise ValueError("Region masks must be boolean.")

    if not region_a.any() or not region_b.any():
        raise ValueError("Region masks cannot be empty.")

    mean_a = np.mean(image[region_a], axis=0)
    mean_b = np.mean(image[region_b], axis=0)

    lab_a = linear_to_lab(mean_a)
    lab_b = linear_to_lab(mean_b)

    return float(delta_e00(lab_a, lab_b))


def pairs_below_jnd(
    differences: np.ndarray,
    threshold: float = JND_DE00,
) -> float:
    """Fraction of annotated pairs below the JND threshold.

    Args:
        differences: CIEDE2000 distances for annotated pairs.
        threshold: Just-noticeable-difference threshold.

    Returns:
        Fraction of pairs below threshold, between 0 and 1.
        Lower is better.
    """
    differences = np.asarray(differences, dtype=np.float64)

    if differences.size == 0:
        raise ValueError("At least one color pair is required.")

    if not np.all(np.isfinite(differences)):
        raise ValueError("Differences must be finite.")

    if np.any(differences < 0):
        raise ValueError("Differences cannot be negative.")

    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("Threshold must be finite and nonnegative.")

    return float(np.mean(differences < threshold))
