"""Checks that the server's spelled-out enums match chromafix.constants. Author: Iris."""

from typing import get_args

from chromafix.constants import ALL_TYPES, METHODS
from server.schemas import CVDTypeName, MethodName


def test_cvd_type_names_match_constants() -> None:
    assert get_args(CVDTypeName) == ALL_TYPES


def test_method_names_match_constants() -> None:
    assert get_args(MethodName) == METHODS
