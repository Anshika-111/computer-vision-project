"""Tests for chromafix.profile. Author: Avneet."""

import pytest

from chromafix.profile import CVDProfile


def test_dict_and_json_round_trip():
    p = CVDProfile("deutan", 0.6, 0.8)
    assert p.to_dict() == {"type": "deutan", "severity": 0.6, "confidence": 0.8}
    assert CVDProfile.from_dict(p.to_dict()) == p
    assert CVDProfile.from_json(p.to_json()) == p


def test_confidence_defaults_to_one():
    assert CVDProfile.from_dict({"type": "protan", "severity": 1}).confidence == 1.0


def test_normal_profile():
    assert CVDProfile.normal().to_dict() == {"type": "normal", "severity": 0.0, "confidence": 1.0}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "achromat", "severity": 0.5},
        {"type": "deutan", "severity": 1.5},
        {"type": "deutan", "severity": 0.5, "confidence": -0.1},
        {"type": "normal", "severity": 0.3},
    ],
)
def test_invalid_profiles_raise(kwargs):
    with pytest.raises(ValueError):
        CVDProfile(**kwargs)


def test_is_frozen():
    p = CVDProfile("tritan", 0.4)
    with pytest.raises(AttributeError):
        p.severity = 0.9  # type: ignore[misc]
