"""Tests for POST /api/simulate and POST /api/recolor. Author: Iris."""

import io
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from chromafix.color import linear_to_srgb, srgb_to_linear, to_float, to_uint8
from chromafix.constants import SEED
from chromafix.profile import CVDProfile
from chromafix.recolor import NeuralModelUnavailable, daltonize
from chromafix.simulate import simulate
from server.imageio import MAX_SIDE
from server.main import app
from server.routes import images as images_route

DEUTAN = {"type": "deutan", "severity": 0.6, "confidence": 0.8}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def srgb_u8() -> np.ndarray:
    """A random 8-bit sRGB test image with saturated reds and greens."""
    rng = np.random.default_rng(SEED)
    return rng.integers(0, 256, size=(24, 40, 3), dtype=np.uint8)


def png_bytes(arr: np.ndarray, mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(arr, mode=mode).save(buffer, format="PNG")
    return buffer.getvalue()


def decode(response_bytes: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(response_bytes)) as im:
        assert im.format == "PNG"
        assert im.mode == "RGB"
        return np.asarray(im)


def expected_u8(linear: np.ndarray) -> np.ndarray:
    return to_uint8(linear_to_srgb(linear))


def post(client: TestClient, path: str, image: bytes, **fields: str):
    return client.post(path, files={"image": ("x.png", image, "image/png")}, data=fields)


# --- /api/simulate ----------------------------------------------------------


def test_simulate_matches_chromafix(client: TestClient, srgb_u8: np.ndarray) -> None:
    response = post(client, "/api/simulate", png_bytes(srgb_u8), profile=json.dumps(DEUTAN))

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    linear = srgb_to_linear(to_float(srgb_u8))
    np.testing.assert_array_equal(
        decode(response.content), expected_u8(simulate(linear, "deutan", 0.6))
    )


def test_simulate_normal_returns_the_same_pixels(client: TestClient, srgb_u8: np.ndarray) -> None:
    profile = json.dumps({"type": "normal", "severity": 0.0})
    response = post(client, "/api/simulate", png_bytes(srgb_u8), profile=profile)

    assert response.status_code == 200, response.text
    diff = np.abs(decode(response.content).astype(int) - srgb_u8.astype(int))
    assert diff.max() <= 1  # sRGB -> linear -> sRGB round trip, within 1/255


def test_simulate_changes_red_green_for_deutan(client: TestClient) -> None:
    red_green = np.zeros((2, 2, 3), dtype=np.uint8)
    red_green[0] = (220, 30, 30)
    red_green[1] = (30, 180, 30)
    profile = json.dumps({"type": "deutan", "severity": 1.0})

    out = decode(post(client, "/api/simulate", png_bytes(red_green), profile=profile).content)

    assert not np.array_equal(out, red_green)


def test_alpha_and_grayscale_inputs_become_rgb(client: TestClient, srgb_u8: np.ndarray) -> None:
    rgba = np.dstack([srgb_u8, np.full(srgb_u8.shape[:2], 128, dtype=np.uint8)])
    gray = srgb_u8[..., 0]
    for data in (png_bytes(rgba, "RGBA"), png_bytes(gray, "L")):
        response = post(client, "/api/simulate", data, profile=json.dumps(DEUTAN))
        assert response.status_code == 200, response.text
        assert decode(response.content).shape == (*srgb_u8.shape[:2], 3)


def test_large_upload_is_downscaled(client: TestClient) -> None:
    big = np.zeros((MAX_SIDE + 200, MAX_SIDE // 2, 3), dtype=np.uint8)

    response = post(client, "/api/simulate", png_bytes(big), profile=json.dumps(DEUTAN))

    assert response.status_code == 200, response.text
    assert max(decode(response.content).shape[:2]) == MAX_SIDE


@pytest.mark.parametrize(
    "profile",
    [
        "not json",
        json.dumps({"type": "deutan"}),
        json.dumps({"type": "deutan", "severity": 1.5}),
        json.dumps({"type": "normal", "severity": 0.5}),
        json.dumps({"type": "achromat", "severity": 0.5}),
        json.dumps({**DEUTAN, "extra": 1}),
    ],
)
def test_bad_profile_is_422(client: TestClient, srgb_u8: np.ndarray, profile: str) -> None:
    response = post(client, "/api/simulate", png_bytes(srgb_u8), profile=profile)

    assert response.status_code == 422


@pytest.mark.parametrize("data", [b"", b"definitely not an image"])
def test_bad_image_is_422(client: TestClient, data: bytes) -> None:
    response = post(client, "/api/simulate", data, profile=json.dumps(DEUTAN))

    assert response.status_code == 422


def test_missing_fields_are_422(client: TestClient, srgb_u8: np.ndarray) -> None:
    assert client.post("/api/simulate", data={"profile": json.dumps(DEUTAN)}).status_code == 422
    assert post(client, "/api/simulate", png_bytes(srgb_u8)).status_code == 422


# --- /api/recolor -----------------------------------------------------------


@pytest.mark.parametrize("method", ["none", "fixed"])
def test_recolor_matches_chromafix(client: TestClient, srgb_u8: np.ndarray, method: str) -> None:
    response = post(
        client, "/api/recolor", png_bytes(srgb_u8), profile=json.dumps(DEUTAN), method=method
    )

    assert response.status_code == 200, response.text
    linear = srgb_to_linear(to_float(srgb_u8))
    expected = expected_u8(daltonize(linear, CVDProfile.from_dict(DEUTAN), method))
    np.testing.assert_array_equal(decode(response.content), expected)


def test_recolor_unknown_method_is_422(client: TestClient, srgb_u8: np.ndarray) -> None:
    response = post(
        client, "/api/recolor", png_bytes(srgb_u8), profile=json.dumps(DEUTAN), method="magic"
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "error", [NeuralModelUnavailable("no checkpoint"), NotImplementedError("not tuned")]
)
def test_unavailable_method_is_503(
    client: TestClient, srgb_u8: np.ndarray, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def unavailable(*args: object) -> np.ndarray:
        raise error

    monkeypatch.setattr(images_route, "recolor", unavailable)

    response = post(
        client, "/api/recolor", png_bytes(srgb_u8), profile=json.dumps(DEUTAN), method="neural"
    )

    assert response.status_code == 503
    assert str(error) in response.json()["detail"]


def test_recolor_passes_profile_and_method_through(
    client: TestClient, srgb_u8: np.ndarray, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = {}

    def fake(img: np.ndarray, profile: CVDProfile, method: str) -> np.ndarray:
        seen.update(profile=profile, method=method, shape=img.shape, dtype=img.dtype)
        return img

    monkeypatch.setattr(images_route, "recolor", fake)

    post(client, "/api/recolor", png_bytes(srgb_u8), profile=json.dumps(DEUTAN), method="neural")

    assert seen == {
        "profile": CVDProfile.from_dict(DEUTAN),
        "method": "neural",
        "shape": srgb_u8.shape,
        "dtype": np.float32,
    }
