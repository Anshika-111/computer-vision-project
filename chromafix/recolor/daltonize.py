"""Daltonization (Fidaner et al., 2005) as one 3x3 linear-RGB matrix. Author: Anshika.

Daltonization simulates what a viewer with CVD sees, takes the error (the color
information they miss), shifts that error into channels they can still perceive, and
adds it back:

    simulated = S @ px
    error     = px - simulated
    out       = px + E @ error          =>   out = (I + E @ (I - S)) @ px

S is the Machado simulation matrix and E is the error-shift matrix. Every step is
linear, so the whole method is one 3x3 matrix acting on linear RGB column vectors
(CLAUDE.md Section 5). Live mode runs that matrix in a WebGL shader.

The intermediate simulation is deliberately NOT clipped. Clipping there would make the
method non-linear and the matrix path would no longer equal the per-pixel path. Only
the final output is clipped to [0, 1].

Reference: O. Fidaner, P. Lin, N. Ozguven. Analysis of color blindness. Psych 221
project report, Stanford University, 2005.
"""

from __future__ import annotations

import numpy as np

from chromafix.constants import CVD_TYPES
from chromafix.profile import CVDProfile
from chromafix.simulate import simulation_matrix

# Methods that have a 3x3 matrix form. "neural" is image-only (see chromafix.recolor).
MATRIX_METHODS = ("none", "fixed", "personalized")

# The fixed method always corrects for full-strength CVD, whatever the user's severity.
FIXED_SEVERITY = 1.0

# Error-shift matrices E, row-major. Row i says how much of each channel's error is
# added to output channel i.
_ERROR_SHIFT: dict[str, tuple[tuple[float, float, float], ...]] = {
    # Fidaner et al. (2005): drop the red error, add 0.7 of it to green and blue.
    "protan": (
        (0.0, 0.0, 0.0),
        (0.7, 1.0, 0.0),
        (0.7, 0.0, 1.0),
    ),
    "deutan": (
        (0.0, 0.0, 0.0),
        (0.7, 1.0, 0.0),
        (0.7, 0.0, 1.0),
    ),
    # Fidaner only defines red-green correction. For tritan we use the usual mirrored
    # form: drop the blue error, add 0.7 of it to red and green.
    "tritan": (
        (1.0, 0.0, 0.7),
        (0.0, 1.0, 0.7),
        (0.0, 0.0, 0.0),
    ),
}


def error_shift_matrix(cvd_type: str) -> np.ndarray:
    """Fixed error-shift matrix E for a CVD type.

    Args:
        cvd_type: "protan", "deutan", or "tritan".

    Returns:
        (3, 3) float64 matrix, row-major, acting on linear RGB error vectors.
    """
    if cvd_type not in CVD_TYPES:
        raise ValueError(f"cvd_type must be one of {CVD_TYPES}, got {cvd_type!r}")
    return np.array(_ERROR_SHIFT[cvd_type], dtype=np.float64)


def daltonization_matrix(cvd_type: str, severity: float, shift: np.ndarray) -> np.ndarray:
    """Collapse daltonization into one matrix: I + E @ (I - S).

    Args:
        cvd_type: "protan", "deutan", or "tritan".
        severity: Severity used for the simulation step, 0.0-1.0.
        shift: (3, 3) error-shift matrix E.

    Returns:
        (3, 3) float64 matrix acting on linear RGB column vectors.
    """
    shift = np.asarray(shift, dtype=np.float64)
    if shift.shape != (3, 3):
        raise ValueError(f"shift must have shape (3, 3), got {shift.shape}")
    s = simulation_matrix(cvd_type, severity)
    eye = np.eye(3)
    return eye + shift @ (eye - s)


def recolor_matrix(profile: CVDProfile, method: str) -> np.ndarray:
    """3x3 recoloring matrix for a profile and method.

    Args:
        profile: The viewer's CVD profile.
        method: "none", "fixed", or "personalized".
            "none" gives the identity. "fixed" is Fidaner daltonization at severity 1.0
            of profile.type. "personalized" uses tuned parameters (Phase 2).
            A "normal" profile gives the identity for every method.

    Returns:
        (3, 3) float64 matrix, row-major, acting on linear RGB column vectors
        (out_px = M @ in_px).

    Raises:
        ValueError: Unknown method, or "neural" (which has no matrix form).
        NotImplementedError: "personalized" before its Phase 2 parameters exist.
    """
    if method == "neural":
        raise ValueError("'neural' has no matrix form; use chromafix.recolor.recolor() instead")
    if method not in MATRIX_METHODS:
        raise ValueError(f"method must be one of {MATRIX_METHODS}, got {method!r}")
    if method == "none" or profile.type == "normal":
        return np.eye(3)
    if method == "fixed":
        return daltonization_matrix(profile.type, FIXED_SEVERITY, error_shift_matrix(profile.type))
    raise NotImplementedError(
        "Personalized daltonization is not tuned yet (Phase 2, "
        "chromafix/recolor/params/personalized.json)."
    )


def daltonize(img: np.ndarray, profile: CVDProfile, method: str = "fixed") -> np.ndarray:
    """Recolor an image so a viewer with the given profile can tell more colors apart.

    Equivalent to img @ recolor_matrix(profile, method).T, clipped.

    Args:
        img: Linear RGB, shape (..., 3) (an (H, W, 3) image or an (N, 3) color list),
            values in [0, 1].
        profile: The viewer's CVD profile.
        method: "none", "fixed", or "personalized".

    Returns:
        Linear RGB, float32, same shape, clipped to [0, 1].
    """
    img = np.asarray(img)
    if img.shape[-1] != 3:
        raise ValueError(f"img must have 3 channels in the last axis, got shape {img.shape}")
    m = recolor_matrix(profile, method)
    out = img.astype(np.float64) @ m.T
    return np.clip(out, 0.0, 1.0).astype(np.float32)
