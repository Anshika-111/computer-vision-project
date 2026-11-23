"""Neural recoloring inference. Placeholder until the Phase 3 model exists. Author: Anshika.

Keeps the CLAUDE.md Section 6 contract today: neural_recolor() raises
NeuralModelUnavailable, so the server can answer 503 and the frontend hides "neural".
"""

from __future__ import annotations

import numpy as np

from chromafix.profile import CVDProfile


class NeuralModelUnavailable(RuntimeError):
    """Raised when models/neural_recolor.pt is missing or torch is not installed."""


def neural_recolor(img: np.ndarray, profile: CVDProfile) -> np.ndarray:
    """Recolor an image with the profile-conditioned network.

    Args:
        img: Linear RGB, shape (H, W, 3), values in [0, 1].
        profile: The viewer's CVD profile.

    Returns:
        Linear RGB, float32, shape (H, W, 3), clipped to [0, 1].

    Raises:
        NeuralModelUnavailable: Always, until the Phase 3 model is trained.
    """
    raise NeuralModelUnavailable(
        "Neural recoloring is not available yet: models/neural_recolor.pt has not been trained."
    )
