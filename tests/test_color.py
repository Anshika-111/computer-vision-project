"""Tests for chromafix.color. Author: Avneet."""

import numpy as np
import pytest

from chromafix import color


def test_srgb_linear_round_trip_all_uint8_values():
    x = np.arange(256, dtype=np.float32) / 255.0
    back = color.linear_to_srgb(color.srgb_to_linear(x))
    assert np.max(np.abs(back - x)) < 1.0 / 255.0


def test_known_srgb_values():
    assert color.srgb_to_linear(np.array([0.0, 1.0])) == pytest.approx([0.0, 1.0])
    assert float(color.srgb_to_linear(np.array(0.5))) == pytest.approx(0.214041, abs=1e-5)
    assert float(color.linear_to_srgb(np.array(0.0031308))) == pytest.approx(0.04045, abs=1e-5)


def test_uint8_float_round_trip():
    u = np.arange(256, dtype=np.uint8)
    assert np.array_equal(color.to_uint8(color.to_float(u)), u)


def test_lab_of_white_black_and_gray():
    lab = color.linear_to_lab(np.array([[1.0, 1.0, 1.0], [0.0, 0.0, 0.0]]))
    assert lab[0] == pytest.approx([100.0, 0.0, 0.0], abs=1e-2)  # skimage rounding
    assert lab[1] == pytest.approx([0.0, 0.0, 0.0], abs=1e-3)


def test_lab_round_trip():
    rng = np.random.default_rng(0)
    lin = rng.uniform(0.01, 0.99, size=(500, 3)).astype(np.float32)
    back = color.lab_to_linear(color.linear_to_lab(lin))
    assert np.max(np.abs(back - lin)) < 1e-3


def test_lab_keeps_image_shape():
    img = np.full((4, 5, 3), 0.5, dtype=np.float32)
    assert color.linear_to_lab(img).shape == (4, 5, 3)


@pytest.mark.parametrize(
    ("lab1", "lab2", "expected"),
    [  # Sharma, Wu & Dalal (2005) CIEDE2000 test data, pairs 1 and 7
        ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
        ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
    ],
)
def test_delta_e00_known_pairs(lab1, lab2, expected):
    assert float(color.delta_e00(np.array(lab1), np.array(lab2))) == pytest.approx(
        expected, abs=1e-4
    )


def test_delta_e00_identical_is_zero_and_broadcasts():
    lab = color.linear_to_lab(np.random.default_rng(1).uniform(size=(3, 4, 3)))
    assert np.allclose(color.delta_e00(lab, lab), 0.0)
    assert color.delta_e00(lab, np.array([50.0, 0.0, 0.0])).shape == (3, 4)


def test_save_load_round_trip(tmp_path):
    rng = np.random.default_rng(2)
    img = color.srgb_to_linear(rng.integers(0, 256, size=(8, 9, 3)) / 255.0)
    path = tmp_path / "x.png"
    color.save_image(path, img)
    back = color.load_image(path)
    assert back.dtype == np.float32 and back.shape == (8, 9, 3)
    assert np.max(np.abs(color.linear_to_srgb(back) - color.linear_to_srgb(img))) < 1 / 255
