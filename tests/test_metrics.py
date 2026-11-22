
"""Tests for ChromaFix evaluation metrics. Author: Aliza."""

import numpy as np
import pytest

from chromafix.eval.metrics import (
    naturalness,
    pair_distinguishability,
    pairs_below_jnd,
)


def test_naturalness_identical_images():
    image = np.full((4, 4, 3), 0.5, dtype=np.float32)

    result = naturalness(image, image.copy())

    assert result == pytest.approx(0.0, abs=1e-6)


def test_naturalness_different_images():
    original = np.zeros((4, 4, 3), dtype=np.float32)
    recolored = np.ones((4, 4, 3), dtype=np.float32)

    result = naturalness(original, recolored)

    assert result > 0.0


def test_naturalness_shape_mismatch():
    original = np.zeros((4, 4, 3), dtype=np.float32)
    recolored = np.zeros((2, 2, 3), dtype=np.float32)

    with pytest.raises(ValueError):
        naturalness(original, recolored)


def test_identical_region_colors():
    image = np.full((4, 4, 3), 0.5, dtype=np.float32)

    mask_a = np.zeros((4, 4), dtype=bool)
    mask_b = np.zeros((4, 4), dtype=bool)

    mask_a[:, :2] = True
    mask_b[:, 2:] = True

    result = pair_distinguishability(image, mask_a, mask_b)

    assert result == pytest.approx(0.0, abs=1e-6)


def test_different_region_colors():
    image = np.zeros((4, 4, 3), dtype=np.float32)
    image[:, :2] = [1.0, 0.0, 0.0]
    image[:, 2:] = [0.0, 1.0, 0.0]

    mask_a = np.zeros((4, 4), dtype=bool)
    mask_b = np.zeros((4, 4), dtype=bool)

    mask_a[:, :2] = True
    mask_b[:, 2:] = True

    result = pair_distinguishability(image, mask_a, mask_b)

    assert result > 0.0


def test_empty_region_raises():
    image = np.zeros((4, 4, 3), dtype=np.float32)
    empty = np.zeros((4, 4), dtype=bool)
    valid = np.ones((4, 4), dtype=bool)

    with pytest.raises(ValueError):
        pair_distinguishability(image, empty, valid)


def test_pairs_below_jnd():
    differences = np.array([0.2, 0.5, 1.5, 3.0])

    result = pairs_below_jnd(differences)

    assert result == pytest.approx(0.5)


def test_pairs_below_jnd_empty():
    with pytest.raises(ValueError):
        pairs_below_jnd(np.array([]))


def test_pairs_below_jnd_all_distinguishable():
    differences = np.array([2.0, 5.0, 10.0])

    assert pairs_below_jnd(differences) == 0.0
