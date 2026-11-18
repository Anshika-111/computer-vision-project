"""Tests for chromafix.simulate. Author: Avneet."""

import numpy as np
import pytest
from colour.blindness import matrix_cvd_Machado2009

from chromafix.constants import CVD_TYPES, SEVERITY_GRID
from chromafix.simulate import confusion_direction, simulate, simulation_matrix

COLOUR_NAMES = {"protan": "Protanomaly", "deutan": "Deuteranomaly", "tritan": "Tritanomaly"}


@pytest.mark.parametrize("cvd_type", CVD_TYPES)
@pytest.mark.parametrize("severity", SEVERITY_GRID)
def test_matches_colour_science_at_grid(cvd_type, severity):
    ref = matrix_cvd_Machado2009(COLOUR_NAMES[cvd_type], severity)
    assert np.allclose(simulation_matrix(cvd_type, severity), ref, atol=1e-4)


@pytest.mark.parametrize("cvd_type", CVD_TYPES)
@pytest.mark.parametrize(
    ("severity", "lo", "hi"), [(0.05, 0.0, 0.1), (0.37, 0.3, 0.4), (0.95, 0.9, 1.0)]
)
def test_interpolates_linearly_between_grid_steps(cvd_type, severity, lo, hi):
    # Compared against colour-science's grid values. Its own between-step function
    # extrapolates from the step above instead of interpolating, so it is not used here.
    a = matrix_cvd_Machado2009(COLOUR_NAMES[cvd_type], lo)
    b = matrix_cvd_Machado2009(COLOUR_NAMES[cvd_type], hi)
    f = (severity - lo) / (hi - lo)
    assert np.allclose(simulation_matrix(cvd_type, severity), (1 - f) * a + f * b, atol=1e-4)


def test_normal_and_zero_severity_are_identity():
    assert np.array_equal(simulation_matrix("normal", 0.0), np.eye(3))
    for t in CVD_TYPES:
        assert np.array_equal(simulation_matrix(t, 0.0), np.eye(3))
    img = np.random.default_rng(0).uniform(size=(6, 7, 3)).astype(np.float32)
    assert np.allclose(simulate(img, "normal", 0.0), img)


def test_simulate_shape_dtype_and_range():
    img = np.random.default_rng(1).uniform(size=(10, 12, 3)).astype(np.float32)
    out = simulate(img, "deutan", 0.6)
    assert out.shape == img.shape and out.dtype == np.float32
    assert out.min() >= 0.0 and out.max() <= 1.0


def test_simulate_equals_matrix_per_pixel():
    img = np.random.default_rng(2).uniform(size=(5, 5, 3))
    m = simulation_matrix("protan", 0.7)
    expected = np.clip(np.einsum("ij,hwj->hwi", m, img), 0, 1)
    assert np.allclose(simulate(img, "protan", 0.7), expected, atol=1e-6)


def test_white_stays_white():
    for t in CVD_TYPES:
        assert np.allclose(simulate(np.ones(3), t, 1.0), 1.0, atol=1e-3)


def test_bad_inputs_raise():
    with pytest.raises(ValueError):
        simulation_matrix("achromat", 0.5)
    with pytest.raises(ValueError):
        simulation_matrix("deutan", 1.2)


@pytest.mark.parametrize("cvd_type", CVD_TYPES)
def test_confusion_direction_is_collapsed_at_full_severity(cvd_type):
    v = confusion_direction(cvd_type)
    assert np.linalg.norm(v) == pytest.approx(1.0)
    m = simulation_matrix(cvd_type, 1.0)
    # Smallest stretch of the full-severity matrix: protan/deutan ~0, tritan small.
    assert np.linalg.norm(m @ v) < 0.2
