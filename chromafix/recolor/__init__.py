"""Recoloring: one entry point, recolor(), for every method. Author: Anshika.

Code outside chromafix/recolor/ should call recolor() (CLAUDE.md Section 6) and, for
Live mode, recolor_matrix().
"""

from __future__ import annotations

import numpy as np

from chromafix.profile import CVDProfile
from chromafix.recolor.daltonize import MATRIX_METHODS, daltonize, recolor_matrix
from chromafix.recolor.neural.infer import NeuralModelUnavailable, neural_recolor

__all__ = ["MATRIX_METHODS", "NeuralModelUnavailable", "daltonize", "recolor", "recolor_matrix"]


def recolor(img: np.ndarray, profile: CVDProfile, method: str) -> np.ndarray:
    """Recolor an image with any method.

    Args:
        img: Linear RGB, shape (..., 3), values in [0, 1].
        profile: The viewer's CVD profile.
        method: "none", "fixed", "personalized", or "neural".

    Returns:
        Linear RGB, float32, same shape, clipped to [0, 1].

    Raises:
        ValueError: Unknown method.
        NeuralModelUnavailable: method is "neural" and the model can't be loaded.
            The server turns this into HTTP 503.
    """
    if method == "neural":
        return neural_recolor(img, profile)
    if method in MATRIX_METHODS:
        return daltonize(img, profile, method)
    raise ValueError(f"method must be one of {MATRIX_METHODS + ('neural',)}, got {method!r}")
