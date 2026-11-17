"""Color conversions, image I/O, and CIEDE2000 color difference. Author: Avneet.

Every other module converts through these functions (CLAUDE.md Section 5).
In-memory images are linear RGB, float32, shape (H, W, 3), values in [0, 1].
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, lab2rgb, rgb2lab


def to_float(img_u8: np.ndarray) -> np.ndarray:
    """Convert uint8 values in [0, 255] to float32 in [0, 1]. Color space is unchanged."""
    return np.asarray(img_u8, dtype=np.float32) / 255.0


def to_uint8(img: np.ndarray) -> np.ndarray:
    """Convert float values in [0, 1] to uint8 with rounding. Color space is unchanged."""
    return np.round(np.clip(img, 0.0, 1.0) * 255.0).astype(np.uint8)


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    """Decode sRGB to linear RGB (IEC 61966-2-1 piecewise curve).

    Args:
        x: sRGB values in [0, 1], any shape.

    Returns:
        Linear RGB values in [0, 1], float32, same shape.
    """
    x = np.clip(np.asarray(x, dtype=np.float64), 0.0, 1.0)
    out = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
    return out.astype(np.float32)


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    """Encode linear RGB to sRGB (IEC 61966-2-1 piecewise curve).

    Args:
        x: Linear RGB values, any shape. Values are clipped to [0, 1] first.

    Returns:
        sRGB values in [0, 1], float32, same shape.
    """
    x = np.clip(np.asarray(x, dtype=np.float64), 0.0, 1.0)
    out = np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)
    return out.astype(np.float32)


def linear_to_lab(img: np.ndarray) -> np.ndarray:
    """Convert linear RGB to CIELAB (D65 white point, 2° observer).

    Args:
        img: Linear RGB, shape (..., 3), values in [0, 1].

    Returns:
        CIELAB, float64, shape (..., 3). L in [0, 100].
    """
    img = np.asarray(img)
    srgb = linear_to_srgb(img).astype(np.float64)
    flat = srgb.reshape(-1, 1, 3)
    lab = rgb2lab(flat, illuminant="D65", observer="2")
    return lab.reshape(img.shape[:-1] + (3,))


def lab_to_linear(lab: np.ndarray) -> np.ndarray:
    """Convert CIELAB (D65) to linear RGB, clipped to [0, 1].

    Args:
        lab: CIELAB, shape (..., 3).

    Returns:
        Linear RGB, float32, shape (..., 3).
    """
    lab = np.asarray(lab, dtype=np.float64)
    srgb = lab2rgb(lab.reshape(-1, 1, 3), illuminant="D65", observer="2")
    return srgb_to_linear(srgb.reshape(lab.shape))


def delta_e00(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """CIEDE2000 color difference between two CIELAB arrays.

    The only color-difference function the project reports (CLAUDE.md Section 5).

    Args:
        lab1: CIELAB, shape (..., 3).
        lab2: CIELAB, same shape as lab1 (or broadcastable to it).

    Returns:
        CIEDE2000 values, float64, shape (...).
    """
    lab1, lab2 = np.broadcast_arrays(np.asarray(lab1, np.float64), np.asarray(lab2, np.float64))
    return np.asarray(deltaE_ciede2000(lab1, lab2, channel_axis=-1), dtype=np.float64)


def load_image(path: str | Path) -> np.ndarray:
    """Read an image file as a linear image.

    Grayscale and palette images are expanded to RGB; alpha is dropped.

    Args:
        path: Path to an 8-bit sRGB image (PNG, JPEG, ...).

    Returns:
        Linear RGB, float32, shape (H, W, 3), values in [0, 1].
    """
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"))
    return srgb_to_linear(to_float(rgb))


def save_image(path: str | Path, img: np.ndarray) -> None:
    """Write a linear image as an 8-bit sRGB PNG (or any format Pillow infers from path).

    Args:
        path: Output path. Parent folders must exist.
        img: Linear RGB, shape (H, W, 3). Values are clipped to [0, 1].
    """
    Image.fromarray(to_uint8(linear_to_srgb(img)), mode="RGB").save(path)
