"""Tests for chromafix.recolor (fixed daltonization and the dispatcher). Author: Anshika."""

import numpy as np
import pytest

from chromafix.color import delta_e00, linear_to_lab
from chromafix.constants import CVD_TYPES
from chromafix.profile import CVDProfile
from chromafix.recolor import NeuralModelUnavailable, daltonize, recolor, recolor_matrix
from chromafix.recolor.daltonize import error_shift_matrix
from chromafix.simulate import confusion_direction, simulate, simulation_matrix

RNG = np.random.default_rng(4391)
IMG = RNG.uniform(size=(16, 20, 3)).astype(np.float32)


def per_pixel_fixed(img: np.ndarray, cvd_type: str) -> np.ndarray:
    """Daltonization written out step by step, one pixel at a time, as a reference."""
    s = simulation_matrix(cvd_type, 1.0)
    e = error_shift_matrix(cvd_type)
    out = np.empty(img.shape, dtype=np.float64)
    for idx in np.ndindex(img.shape[:-1]):
        px = img[idx].astype(np.float64)
        simulated = s @ px  # not clipped: keeps the method linear
        error = px - simulated
        out[idx] = px + e @ error
    return np.clip(out, 0.0, 1.0)


# --- Required by CLAUDE.md Section 9 --------------------------------------------------


@pytest.mark.parametrize("method", ["none", "fixed", "personalized"])
def test_normal_profile_is_identity_for_every_method(method):
    normal = CVDProfile.normal()
    assert np.array_equal(recolor_matrix(normal, method), np.eye(3))
    assert np.allclose(daltonize(IMG, normal, method), IMG, atol=1e-7)


@pytest.mark.parametrize("cvd_type", CVD_TYPES)
@pytest.mark.parametrize("severity", [0.2, 0.6, 1.0])
def test_output_in_range_dtype_and_shape(cvd_type, severity):
    # Include the RGB cube corners: saturated colors are the ones pushed out of range.
    corners = np.array(np.meshgrid([0, 1], [0, 1], [0, 1])).reshape(3, -1).T.astype(np.float32)
    for img in (IMG, corners):
        out = daltonize(img, CVDProfile(cvd_type, severity), "fixed")
        assert out.shape == img.shape and out.dtype == np.float32
        assert out.min() >= 0.0 and out.max() <= 1.0


@pytest.mark.parametrize("cvd_type", CVD_TYPES)
def test_matrix_path_matches_per_pixel_path(cvd_type):
    out = daltonize(IMG, CVDProfile(cvd_type, 1.0), "fixed")
    assert np.max(np.abs(out - per_pixel_fixed(IMG, cvd_type))) < 1e-5


# --- Behaviour ----------------------------------------------------------------------


@pytest.mark.parametrize("cvd_type", CVD_TYPES)
def test_fixed_makes_a_confusion_pair_easier_to_tell_apart(cvd_type):
    # Two colors on one of this type's confusion lines look alike after simulation.
    base = np.array([0.4, 0.4, 0.4])
    step = 0.15 * confusion_direction(cvd_type)
    pair = np.clip(np.stack([base - step, base + step]), 0.0, 1.0)
    profile = CVDProfile(cvd_type, 1.0)

    def seen_de00(colors):
        lab = linear_to_lab(simulate(colors, cvd_type, 1.0))
        return float(delta_e00(lab[0], lab[1]))

    assert seen_de00(daltonize(pair, profile, "fixed")) > 2.0 * seen_de00(pair)


@pytest.mark.parametrize("cvd_type", CVD_TYPES)
def test_neutral_grays_are_unchanged(cvd_type):
    grays = np.linspace(0.0, 1.0, 11)[:, None].repeat(3, axis=1)
    out = daltonize(grays, CVDProfile(cvd_type, 1.0), "fixed")
    assert np.allclose(out, grays, atol=5e-3)


def test_fixed_ignores_severity():
    a = recolor_matrix(CVDProfile("deutan", 0.3), "fixed")
    b = recolor_matrix(CVDProfile("deutan", 1.0), "fixed")
    assert np.array_equal(a, b)
    assert a.shape == (3, 3) and a.dtype == np.float64


def test_none_method_is_identity_for_cvd_profiles():
    for t in CVD_TYPES:
        assert np.array_equal(recolor_matrix(CVDProfile(t, 0.8), "none"), np.eye(3))


def test_personalized_not_ready_yet():
    with pytest.raises(NotImplementedError):
        recolor_matrix(CVDProfile("protan", 0.5), "personalized")


def test_bad_methods_raise():
    with pytest.raises(ValueError, match="no matrix form"):
        recolor_matrix(CVDProfile("deutan", 0.5), "neural")
    with pytest.raises(ValueError):
        recolor_matrix(CVDProfile("deutan", 0.5), "sepia")
    with pytest.raises(ValueError):
        daltonize(np.zeros((4, 4)), CVDProfile("deutan", 0.5))


# --- Dispatcher ---------------------------------------------------------------------


def test_recolor_dispatches_to_daltonize():
    p = CVDProfile("protan", 0.7)
    assert np.array_equal(recolor(IMG, p, "fixed"), daltonize(IMG, p, "fixed"))
    assert np.allclose(recolor(IMG, p, "none"), IMG, atol=1e-7)


def test_recolor_neural_unavailable():
    with pytest.raises(NeuralModelUnavailable):
        recolor(IMG, CVDProfile("deutan", 0.5), "neural")
    with pytest.raises(ValueError):
        recolor(IMG, CVDProfile("deutan", 0.5), "sepia")
