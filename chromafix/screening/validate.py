"""Plate validation: label each plate's fail_severity and drop bad plates. Author: Avneet."""

from __future__ import annotations

import dataclasses

import numpy as np

from chromafix.constants import CVD_TYPES, PLATE_HIDDEN_DE00, PLATE_MIN_NORMAL_DE00, SEVERITY_GRID
from chromafix.screening.plates import Plate, pair_contrast


def plate_contrast(plate: Plate, cvd_type: str, severity: float) -> float:
    """CIEDE2000 between the plate's figure and background as a given viewer sees them."""
    fig, bg = np.array(plate.figure_rgb), np.array(plate.background_rgb)
    return float(pair_contrast(fig, bg, cvd_type, severity))


def can_read(plate: Plate, cvd_type: str, severity: float) -> bool:
    """Whether a viewer of this type and severity can read the plate's digit."""
    return plate_contrast(plate, cvd_type, severity) > PLATE_HIDDEN_DE00


def compute_fail_severity(plate: Plate) -> dict[str, float | None]:
    """Lowest grid severity at which each CVD type can no longer read the digit.

    Returns:
        {"protan": s | None, "deutan": s | None, "tritan": s | None}; None means the
        digit stays readable at every severity.
    """
    out: dict[str, float | None] = {}
    for cvd_type in CVD_TYPES:
        out[cvd_type] = next(
            (s for s in SEVERITY_GRID[1:] if not can_read(plate, cvd_type, s)), None
        )
    return out


def validate_plates(plates: list[Plate]) -> list[Plate]:
    """Fill fail_severity on every plate and drop plates that don't work.

    A plate is dropped when:
      - normal vision sees less than PLATE_MIN_NORMAL_DE00 between figure and background;
      - it is a target plate that never fails for its target type;
      - it is a control plate that fails for any type.

    Args:
        plates: Output of generate_plates().

    Returns:
        New Plate objects (inputs are not modified), in the same order, minus dropped ones.
    """
    kept: list[Plate] = []
    for plate in plates:
        if plate_contrast(plate, "normal", 0.0) < PLATE_MIN_NORMAL_DE00 - 1e-6:
            continue
        fail = compute_fail_severity(plate)
        if plate.is_control and any(v is not None for v in fail.values()):
            continue
        if not plate.is_control and fail[plate.target_type] is None:
            continue
        kept.append(dataclasses.replace(plate, fail_severity=fail))
    return kept


def select_plates(
    plates: list[Plate], n: int = 24, n_controls: int = 3, seed: int = 0
) -> list[Plate]:
    """Pick a balanced test set: a few controls plus targets spread over type × difficulty.

    Used for GET /api/plates?n=24 and for the screening evaluation, so both see the same mix.

    Args:
        plates: Validated plates.
        n: Total plates to return.
        n_controls: How many of them are control plates.
        seed: Random seed for which plates are chosen and their order.

    Returns:
        n plates (fewer if not enough exist), shuffled.
    """
    rng = np.random.default_rng(seed)
    controls = [p for p in plates if p.is_control]
    cells: dict[tuple[str, int], list[Plate]] = {}
    for p in plates:
        if not p.is_control:
            cells.setdefault((p.target_type, p.difficulty), []).append(p)
    for group in cells.values():
        rng.shuffle(group)
    picks = rng.permutation(len(controls))[: min(n_controls, len(controls))]
    chosen = [controls[j] for j in picks]
    keys = sorted(cells, key=lambda k: (k[1], k[0]))  # rotate types first, then levels
    i = 0
    while len(chosen) < n and any(cells.values()):
        key = keys[i % len(keys)]
        if cells[key]:
            chosen.append(cells[key].pop())
        i += 1
    order = rng.permutation(len(chosen))
    return [chosen[j] for j in order]
