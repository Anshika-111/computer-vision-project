"""GET /api/methods: the recoloring methods this server can run right now. Author: Iris."""

import numpy as np
from fastapi import APIRouter

from chromafix.constants import METHODS
from chromafix.profile import CVDProfile
from chromafix.recolor import NeuralModelUnavailable, recolor, recolor_matrix
from server.schemas import MethodName

router = APIRouter()

# Any CVD profile works for the probes below; availability does not depend on it.
_PROBE_PROFILE = CVDProfile(type="deutan", severity=0.5)
# Small gray image for the neural probe. 32 px so a downsampling network still has pixels left.
_PROBE_IMAGE = np.full((32, 32, 3), 0.5, dtype=np.float32)


def personalized_available() -> bool:
    """True once Anshika's tuned personalized parameters exist."""
    try:
        recolor_matrix(_PROBE_PROFILE, "personalized")
    except NotImplementedError:
        return False
    return True


def neural_available() -> bool:
    """True when the neural model loads (checkpoint present and torch installed)."""
    try:
        recolor(_PROBE_IMAGE, _PROBE_PROFILE, "neural")
    except NeuralModelUnavailable:
        return False
    return True


def available_methods() -> list[MethodName]:
    """Methods that work right now, in the order of chromafix.constants.METHODS."""
    optional = {"personalized": personalized_available, "neural": neural_available}
    return [m for m in METHODS if m not in optional or optional[m]()]


@router.get("/methods")
def get_methods() -> list[MethodName]:
    """List the available methods. The frontend hides anything not listed."""
    return available_methods()
