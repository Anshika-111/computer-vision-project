"""Decode uploaded image bytes to a linear image and encode linear images as PNG. Author: Iris.

The server never stores uploads: bytes are decoded in memory and the response is built in
memory. All color conversion goes through chromafix.color (CLAUDE.md Section 5).
"""

import io

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from chromafix.color import linear_to_srgb, srgb_to_linear, to_float, to_uint8

# Uploads are resized so the longest side is at most this many pixels, matching the dataset.
MAX_SIDE = 1024
# Refuse files this large before decoding them.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
# Refuse images with more pixels than this before decoding them (decompression bombs).
MAX_PIXELS = 50_000_000


class BadImage(ValueError):
    """The upload is not a readable image, or is too large."""


def decode_upload(data: bytes) -> np.ndarray:
    """Decode an uploaded 8-bit sRGB image file to a linear image.

    EXIF rotation is applied, grayscale/palette images become RGB and alpha is dropped
    (same as chromafix.color.load_image). Images larger than MAX_SIDE are downscaled in
    sRGB with Lanczos resampling, the same way the dataset was prepared.

    Args:
        data: Raw file bytes (PNG, JPEG, ...).

    Returns:
        Linear RGB, float32, shape (H, W, 3), values in [0, 1].

    Raises:
        BadImage: Empty, too large, or not an image.
    """
    if not data:
        raise BadImage("empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise BadImage(f"file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    try:
        with Image.open(io.BytesIO(data)) as im:
            width, height = im.size
            if width * height > MAX_PIXELS:
                raise BadImage(f"image has more than {MAX_PIXELS} pixels")
            rgb = ImageOps.exif_transpose(im).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise BadImage("not a readable image file") from error
    if max(rgb.size) > MAX_SIDE:
        rgb.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    return srgb_to_linear(to_float(np.asarray(rgb)))


def encode_png(img: np.ndarray) -> bytes:
    """Encode a linear image as 8-bit sRGB PNG bytes (same pipeline as chromafix.color.save_image).

    Args:
        img: Linear RGB, shape (H, W, 3). Values are clipped to [0, 1].

    Returns:
        PNG file bytes.
    """
    buffer = io.BytesIO()
    Image.fromarray(to_uint8(linear_to_srgb(img)), mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()
