"""Classification helpers."""

from __future__ import annotations


def simple_classification(
    generic_abs_z: float,
    dominant_witness_z: float,
    witness_name: str | None = None,
) -> str:
    if dominant_witness_z >= 20 and witness_name:
        return f"witness-confirmed: {witness_name}"
    if generic_abs_z >= 50:
        return "structured unknown / no exact witness"
    if generic_abs_z >= 10 or dominant_witness_z >= 5:
        return "borderline / needs longer horizon"
    return "random-like / no known witness"
