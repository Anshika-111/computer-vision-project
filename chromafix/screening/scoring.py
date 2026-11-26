"""Turn screening answers into a CVDProfile, plus a simulated observer for testing. Author: Avneet.

Scoring compares the user's read/missed pattern with what every candidate profile
(normal, or type × severity on the 0.1 grid) would be expected to read, using each plate's
fail_severity. The candidate whose predictions agree with the most answers wins:
  - type: the type that explains the most answers (ties go to the more common type:
    deutan, then protan, then tritan);
  - severity: the median of the best-matching severities for that type;
  - confidence: share of target plates the winning profile explains, lowered when
    control plates are missed or when protan and deutan explain the answers equally well.
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np

from chromafix.constants import CVD_TYPES, SEVERITY_GRID
from chromafix.profile import CVDProfile
from chromafix.screening.plates import Plate
from chromafix.screening.validate import can_read


class PlateAnswer(TypedDict):
    """One answer: `answer` is a digit "0"–"9" or "none" (CLAUDE.md Section 6)."""

    plate_id: str
    answer: str


def is_correct(plate: Plate, answer: str) -> bool:
    """Whether an answer reads the plate's digit. "none" and anything else is a miss."""
    return answer.strip().lower() == str(plate.digit)


def _expected_read(plate: Plate, cvd_type: str, severity: float) -> bool:
    if cvd_type == "normal":
        return True
    fail = plate.fail_severity.get(cvd_type)
    return fail is None or severity < fail - 1e-9


def score(answers: list[PlateAnswer], plates: dict[str, Plate]) -> CVDProfile:
    """Estimate a CVD profile from screening answers.

    Args:
        answers: One PlateAnswer per plate shown.
        plates: Validated plates (fail_severity filled) keyed by plate_id.

    Returns:
        The estimated CVDProfile.

    Raises:
        KeyError: An answer refers to an unknown plate_id.
        ValueError: No target plates were answered, or a plate has no fail_severity.
    """
    targets: list[tuple[Plate, bool]] = []
    controls_missed = controls_total = 0
    for a in answers:
        plate = plates[a["plate_id"]]
        read = is_correct(plate, a["answer"])
        if plate.is_control:
            controls_total += 1
            controls_missed += not read
        else:
            if not plate.fail_severity:
                raise ValueError(f"Plate {plate.plate_id} has no fail_severity; validate first")
            targets.append((plate, read))
    if not targets:
        raise ValueError("No target plates answered")

    observed = np.array([read for _, read in targets])
    candidates = [("normal", 0.0)] + [(t, s) for t in CVD_TYPES for s in SEVERITY_GRID[1:]]
    agreement = np.array(
        [np.mean([_expected_read(p, t, s) for p, _ in targets] == observed) for t, s in candidates]
    )
    best = agreement.max()
    tied = [c for c, a in zip(candidates, agreement, strict=True) if a >= best - 1e-9]

    control_rate = 1.0 - controls_missed / controls_total if controls_total else 1.0
    if any(t == "normal" for t, _ in tied):
        return CVDProfile("normal", 0.0, round(float(best * control_rate), 2))

    counts = {t: sum(1 for c, _ in tied if c == t) for t in CVD_TYPES}
    # Tie-break: the more common type (deutan > protan > tritan; Birch 2012). Plate labels
    # are not used, since mild protan and deutan often fail the very same plates.
    prevalence = {"deutan": 2, "protan": 1, "tritan": 0}
    cvd_type = max(CVD_TYPES, key=lambda t: (counts[t], prevalence[t]))
    severity = float(np.median([s for t, s in tied if t == cvd_type]))
    ambiguous = sum(1 for t in CVD_TYPES if counts[t] > 0) > 1
    confidence = best * control_rate * (0.75 if ambiguous else 1.0)
    return CVDProfile(cvd_type, round(severity, 2), round(float(confidence), 2))


def simulated_answers(
    plates: list[Plate],
    profile: CVDProfile,
    lapse_rate: float = 0.0,
    rng: np.random.Generator | None = None,
) -> list[PlateAnswer]:
    """Answers a simulated viewer with this profile would give.

    The viewer reads a plate when its figure/background contrast, after simulation,
    stays above the hidden threshold. With lapse_rate > 0, each answer is flipped
    (read <-> missed) with that probability, to mimic attention slips.

    Args:
        plates: Plates shown, in order.
        profile: The simulated viewer.
        lapse_rate: Probability of a random mistake per plate.
        rng: Random generator, required when lapse_rate > 0.

    Returns:
        One PlateAnswer per plate.
    """
    out: list[PlateAnswer] = []
    for p in plates:
        read = can_read(p, profile.type, profile.severity)
        if lapse_rate > 0:
            if rng is None:
                raise ValueError("rng is required when lapse_rate > 0")
            if rng.random() < lapse_rate:
                read = not read
        out.append({"plate_id": p.plate_id, "answer": str(p.digit) if read else "none"})
    return out
