"""Tests for chromafix.screening plate generation and validation. Author: Avneet."""

import numpy as np
import pytest

from chromafix.constants import CVD_TYPES, PLATE_DESIGN_SEVERITY
from chromafix.screening import (
    Plate,
    can_read,
    generate_plates,
    render_plate,
    select_plates,
    validate_plates,
)


@pytest.fixture(scope="module")
def plates() -> list[Plate]:
    return validate_plates(generate_plates(4, seed=7))


def test_generation_counts_and_determinism():
    a = generate_plates(2, seed=3, n_controls=4)
    b = generate_plates(2, seed=3, n_controls=4)
    assert a == b
    n_levels = sum(len(PLATE_DESIGN_SEVERITY[t]) for t in CVD_TYPES)
    assert len(a) == 4 + 2 * n_levels
    assert len({p.plate_id for p in a}) == len(a)
    assert all(0 <= p.digit <= 9 for p in a)


def test_validated_plates_have_expected_fail_pattern(plates):
    assert len(plates) > 0.9 * (6 + 4 * 12)
    for p in plates:
        assert set(p.fail_severity) == set(CVD_TYPES)
        assert can_read(p, "normal", 0.0)
        if p.is_control:
            assert all(v is None for v in p.fail_severity.values())
        else:
            fail = p.fail_severity[p.target_type]
            design = PLATE_DESIGN_SEVERITY[p.target_type][p.difficulty]
            assert fail is not None and abs(fail - design) <= 0.15


def test_validate_does_not_modify_input():
    raw = generate_plates(1, seed=1, n_controls=1)
    validate_plates(raw)
    assert all(p.fail_severity == {} for p in raw)


def test_json_round_trip_and_public_form(plates):
    p = plates[-1]
    assert Plate.from_dict(p.to_dict()) == p
    public = p.public_dict()
    assert "fail_severity" not in public and "digit" not in public


def test_render_plate_is_deterministic_linear_image(plates):
    img = render_plate(plates[0], size=128)
    assert img.shape == (128, 128, 3) and img.dtype == np.float32
    assert 0.0 <= img.min() and img.max() <= 1.0
    assert np.array_equal(img, render_plate(plates[0], size=128))


def test_select_plates_is_balanced(plates):
    chosen = select_plates(plates, n=24, n_controls=3, seed=0)
    assert len(chosen) == 24
    assert sum(p.is_control for p in chosen) == 3
    assert len({p.plate_id for p in chosen}) == 24
    per_type = {t: sum(p.target_type == t for p in chosen) for t in CVD_TYPES}
    assert all(n == 7 for n in per_type.values())
