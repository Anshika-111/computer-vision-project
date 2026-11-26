"""Tests for chromafix.eval.metrics. Author: Aliza."""

import numpy as np
import pytest

from chromafix.color import delta_e00, linear_to_lab
from chromafix.eval.metrics import naturalness, pair_distinguishability, pairs_below_jnd

# CIEDE2000 test data: Sharma, Wu & Dalal, Color Res. Appl. 30(1), 2005, Table 1.
# Only pairs whose colors are inside the sRGB gamut, so they can be put in an image.
# Pairs 9-16 are left out: they sit on the hue-angle discontinuity, where a 1e-4 change
# in b* flips the answer (7.1792 vs 7.2195), which is below float32 round-trip noise.
SHARMA_PAIRS = [
    ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
    ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((50.0, 2.5, 0.0), (61.0, -5.0, 29.0), 22.8977),
    ((50.0, 2.5, 0.0), (56.0, -27.0, -3.0), 31.9030),
    ((50.0, 2.5, 0.0), (58.0, 24.0, 15.0), 19.4535),
    ((50.0, 2.5, 0.0), (50.0, 3.1736, 0.5854), 1.0000),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
    ((61.2901, 3.7196, -5.3901), (61.4292, 2.2480, -4.9620), 1.8731),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((36.4612, 47.8580, 18.3852), (36.2715, 50.5065, 21.2231), 1.4146),
    ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    ((6.7747, -0.2908, -2.4247), (5.8714, -0.0985, -2.2286), 0.6377),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]
# Lab -> 8-bit-free float32 linear RGB -> Lab round trip moves values by ~0.01.
TOL = 0.03

LEFT = {"pair_id": "x_0000_p0", "a": [[0, 0], [3, 0], [3, 7], [0, 7]]}
HALVES = {**LEFT, "b": [[5, 0], [7, 0], [7, 7], [5, 7]]}


def lab_to_linear_rgb(lab):
    colour = pytest.importorskip("colour")
    wp = colour.CCS_ILLUMINANTS["CIE 1931 2 Degree Standard Observer"]["D65"]
    xyz = colour.Lab_to_XYZ(np.asarray(lab, dtype=np.float64), wp)
    rgb = colour.XYZ_to_RGB(xyz, "sRGB", wp, apply_cctf_encoding=False)
    assert ((rgb >= 0) & (rgb <= 1)).all()
    return rgb.astype(np.float32)


def two_tone(left, right, shape=(8, 8)):
    img = np.zeros(shape + (3,), dtype=np.float32)
    img[:, :4] = left
    img[:, 4:] = right
    return img


# --- naturalness ----------------------------------------------------------------------


def test_naturalness_identical_images_is_zero():
    img = np.random.default_rng(4391).random((16, 16, 3), dtype=np.float32)
    assert naturalness(img, img.copy()) == 0.0


@pytest.mark.parametrize(("lab1", "lab2", "expected"), SHARMA_PAIRS)
def test_naturalness_known_lab_pairs(lab1, lab2, expected):
    a = np.broadcast_to(lab_to_linear_rgb(lab1), (4, 4, 3))
    b = np.broadcast_to(lab_to_linear_rgb(lab2), (4, 4, 3))
    assert naturalness(a, b) == pytest.approx(expected, abs=TOL)


def test_naturalness_is_mean_of_per_pixel_differences():
    a = np.zeros((2, 2, 3), dtype=np.float32)
    b = a.copy()
    b[0, 0] = 1.0  # one pixel black -> white (CIEDE2000 = 100)
    assert naturalness(a, b) == pytest.approx(25.0, abs=1e-3)


def test_naturalness_shape_mismatch():
    with pytest.raises(ValueError):
        naturalness(np.zeros((4, 4, 3)), np.zeros((2, 2, 3)))


# --- pair_distinguishability ----------------------------------------------------------


@pytest.mark.parametrize(("lab1", "lab2", "expected"), SHARMA_PAIRS)
def test_pair_distinguishability_known_lab_pairs(lab1, lab2, expected):
    img = two_tone(lab_to_linear_rgb(lab1), lab_to_linear_rgb(lab2))
    d = pair_distinguishability(img, [HALVES], "normal", 0.0)
    assert d.shape == (1,)
    assert d[0] == pytest.approx(expected, abs=TOL)


def test_one_value_per_pair_and_empty_pairs():
    img = two_tone([0.8, 0.1, 0.1], [0.1, 0.6, 0.1])
    same = {"pair_id": "x_0000_p1", "a": [[0, 0], [2, 0], [2, 2]], "b": [[0, 7], [1, 7], [0, 5]]}
    d = pair_distinguishability(img, [HALVES, same], "normal", 0.0)
    assert d.shape == (2,) and d[0] > 10 and d[1] == pytest.approx(0.0, abs=1e-9)
    assert pair_distinguishability(img, [], "deutan", 1.0).shape == (0,)


def test_uses_mean_of_lab_not_mean_of_rgb():
    img = np.zeros((8, 8, 3), dtype=np.float32)
    img[:, :2] = [1.0, 0.0, 0.0]  # region a is half red, half blue
    img[:, 2:4] = [0.0, 0.0, 1.0]
    img[:, 4:] = [0.5, 0.5, 0.5]
    lab = linear_to_lab(img)
    expected = delta_e00(lab[:, :4].reshape(-1, 3).mean(0), lab[:, 4:].reshape(-1, 3).mean(0))
    d = pair_distinguishability(img, [HALVES], "normal", 0.0)
    assert d[0] == pytest.approx(float(expected), abs=1e-6)


def test_normal_and_zero_severity_match_unsimulated():
    img = two_tone([0.6, 0.2, 0.1], [0.2, 0.5, 0.1])
    base = pair_distinguishability(img, [HALVES], "normal", 0.0)
    assert pair_distinguishability(img, [HALVES], "deutan", 0.0) == pytest.approx(base)


@pytest.mark.parametrize("cvd_type", ["protan", "deutan"])
def test_red_green_pair_collapses_for_red_green_cvd(cvd_type):
    # Red vs green: clearly different for normal vision, much closer after simulation.
    img = two_tone([0.45, 0.10, 0.02], [0.12, 0.22, 0.02])
    normal = pair_distinguishability(img, [HALVES], "normal", 0.0)[0]
    mild = pair_distinguishability(img, [HALVES], cvd_type, 0.5)[0]
    strong = pair_distinguishability(img, [HALVES], cvd_type, 1.0)[0]
    assert normal > mild > strong


def test_bad_polygon_raises():
    img = two_tone([0, 0, 0], [1, 1, 1])
    outside = {**HALVES, "b": [[5, 0], [70, 0], [7, 7]]}
    with pytest.raises(ValueError, match="outside"):
        pair_distinguishability(img, [outside], "normal", 0.0)
    with pytest.raises(ValueError):
        pair_distinguishability(np.zeros((8, 8)), [HALVES], "normal", 0.0)


# --- pairs_below_jnd ------------------------------------------------------------------


def test_pairs_below_jnd():
    assert pairs_below_jnd(np.array([0.2, 0.5, 1.5, 3.0]), threshold=1.0) == pytest.approx(0.5)
    assert pairs_below_jnd(np.array([2.0, 5.0]), threshold=1.0) == 0.0
    assert pairs_below_jnd(np.array([1.0]), threshold=1.0) == 0.0  # strictly below


def test_pairs_below_jnd_uses_constant_by_default():
    from chromafix.constants import JND_DE00

    d = np.array([JND_DE00 * 0.5, JND_DE00 * 2])
    assert pairs_below_jnd(d) == pytest.approx(0.5)


@pytest.mark.parametrize("bad", [np.array([]), np.array([np.nan]), np.array([-1.0])])
def test_pairs_below_jnd_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        pairs_below_jnd(bad)
