"""Tests for chromafix.screening scoring and the simulated observer. Author: Avneet."""

import pytest

from chromafix.profile import CVDProfile
from chromafix.screening import Plate, generate_plates, score, simulated_answers, validate_plates


@pytest.fixture(scope="module")
def plates() -> list[Plate]:
    return validate_plates(generate_plates(4, seed=7))


@pytest.fixture(scope="module")
def by_id(plates) -> dict[str, Plate]:
    return {p.plate_id: p for p in plates}


def test_simulated_observer_deutan_full_is_scored_as_deutan(plates, by_id):
    """Required test (CLAUDE.md Section 9)."""
    profile = score(simulated_answers(plates, CVDProfile("deutan", 1.0)), by_id)
    assert profile.type == "deutan"
    assert profile.severity >= 0.85


@pytest.mark.parametrize(
    ("cvd_type", "severity"),
    [("protan", 1.0), ("protan", 0.6), ("deutan", 0.5), ("tritan", 0.9)],
)
def test_simulated_observers_are_typed_correctly(plates, by_id, cvd_type, severity):
    profile = score(simulated_answers(plates, CVDProfile(cvd_type, severity)), by_id)
    assert profile.type == cvd_type
    assert abs(profile.severity - severity) <= 0.15


def test_normal_observer_is_normal(plates, by_id):
    profile = score(simulated_answers(plates, CVDProfile.normal()), by_id)
    assert profile == CVDProfile("normal", 0.0, 1.0)


def test_missed_controls_lower_confidence(plates, by_id):
    answers = simulated_answers(plates, CVDProfile("deutan", 1.0))
    clean = score(answers, by_id).confidence
    for a in answers:
        if by_id[a["plate_id"]].is_control:
            a["answer"] = "none"
    assert score(answers, by_id).confidence < clean


def test_answers_are_normalized(plates, by_id):
    p = plates[0]
    answers = simulated_answers(plates, CVDProfile.normal())
    answers[0] = {"plate_id": p.plate_id, "answer": f" {p.digit} "}
    assert score(answers, by_id).type == "normal"


def test_bad_inputs_raise(plates, by_id):
    with pytest.raises(KeyError):
        score([{"plate_id": "nope", "answer": "1"}], by_id)
    controls_only = [{"plate_id": p.plate_id, "answer": "1"} for p in plates if p.is_control]
    with pytest.raises(ValueError):
        score(controls_only, by_id)
    with pytest.raises(ValueError):
        simulated_answers(plates, CVDProfile.normal(), lapse_rate=0.1)
