"""Shared constants: CVD types, severities, random seed, and thresholds. Author: Avneet."""

CVD_TYPES = ("protan", "deutan", "tritan")
ALL_TYPES = ("normal",) + CVD_TYPES
SEVERITY_GRID = tuple(round(0.1 * i, 1) for i in range(11))  # 0.0 … 1.0
EVAL_SEVERITIES = (0.25, 0.5, 0.75, 1.0)
METHODS = ("none", "fixed", "personalized", "neural")
SEED = 4391

# Just-noticeable difference in CIEDE2000 units.
# PLACEHOLDER: Aliza sets the final value with a cited source (CLAUDE.md Section 6).
JND_DE00: float = 1.0

# ---------------------------------------------------------------------------
# Screening thresholds (used only by chromafix.screening; owned by Avneet).
# ---------------------------------------------------------------------------
# A plate's digit counts as unreadable for a viewer when the CIEDE2000 difference
# between the simulated figure and background colors drops to this value or below.
PLATE_HIDDEN_DE00: float = 2.5
# Every plate must be at least this far apart for typical (normal) vision.
# Physics limit: a plate that hides from mild CVD can only be subtle for normal vision too,
# so this is ~2 JND above the hidden threshold rather than a large gap.
PLATE_MIN_NORMAL_DE00: float = 4.5
# Difficulty level -> design severity: the severity at which the plate is built to
# disappear for its target type. Level 1 hides only for strong CVD; level 4 for milder CVD.
# Tritan levels start higher because the Machado tritan model barely shifts colors below
# ~0.7 severity, so milder tritan plates cannot stay readable for normal vision.
PLATE_DESIGN_SEVERITY: dict[str, dict[int, float]] = {
    "protan": {1: 0.9, 2: 0.7, 3: 0.5, 4: 0.4},
    "deutan": {1: 0.9, 2: 0.7, 3: 0.5, 4: 0.4},
    "tritan": {1: 0.95, 2: 0.9, 3: 0.8, 4: 0.7},
}
