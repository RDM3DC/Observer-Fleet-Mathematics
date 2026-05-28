"""Fleet scoring, calibration, and classification."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, stdev
from typing import Callable, Iterable

from .ships import entropy_bits_per_digit, zlib_compression_ratio


@dataclass(frozen=True)
class ObserverShip:
    """A memory-bearing observer represented by a return function."""

    name: str
    return_map: Callable[[str], float]
    kind: str = "generic"

    def observe(self, landscape: str) -> float:
        return float(self.return_map(landscape))


@dataclass
class ObserverFleet:
    ships: list[ObserverShip]

    def fingerprint(self, landscape: str) -> dict[str, float]:
        return {ship.name: ship.observe(landscape) for ship in self.ships}

    @classmethod
    def from_functions(
        cls,
        generic: dict[str, Callable[[str], float]],
        witness: dict[str, Callable[[str], float]] | None = None,
    ) -> "ObserverFleet":
        ships = [ObserverShip(name, fn, "generic") for name, fn in generic.items()]
        if witness:
            ships.extend(ObserverShip(name, fn, "witness") for name, fn in witness.items())
        return cls(ships)


def score_landscape(name: str, landscape: str, fleet: ObserverFleet) -> dict[str, float | str | int]:
    row: dict[str, float | str | int] = {
        "sequence": name,
        "digits": len(landscape),
        "entropy_bits_per_digit": entropy_bits_per_digit(landscape),
        "zlib_compression_ratio": zlib_compression_ratio(landscape),
    }
    row.update(fleet.fingerprint(landscape))
    return row


def calibrate_against_random(
    random_landscapes: Iterable[str],
    fleet: ObserverFleet,
) -> dict[str, dict[str, float]]:
    values: dict[str, list[float]] = {ship.name: [] for ship in fleet.ships}

    for landscape in random_landscapes:
        fp = fleet.fingerprint(landscape)
        for k, v in fp.items():
            values[k].append(v)

    baseline: dict[str, dict[str, float]] = {}
    for k, vals in values.items():
        baseline[k] = {
            "mean": mean(vals),
            "std": stdev(vals) if len(vals) > 1 else 0.0,
            "min": min(vals),
            "max": max(vals),
        }
    return baseline


def z_fingerprint(
    landscape: str,
    fleet: ObserverFleet,
    baseline: dict[str, dict[str, float]],
) -> dict[str, float]:
    fp = fleet.fingerprint(landscape)
    out: dict[str, float] = {}

    for k, v in fp.items():
        mu = baseline[k]["mean"]
        sd = baseline[k]["std"]
        out[k.replace("_ship", "_z")] = (v - mu) / sd if sd else 0.0

    return out


def classify_z_fingerprint(z: dict[str, float]) -> dict[str, object]:
    generic = {k: v for k, v in z.items() if not k.startswith("witness_")}
    witness = {k: v for k, v in z.items() if k.startswith("witness_")}

    generic_abs_z = sum(abs(v) for v in generic.values())
    dominant_generic = max(generic, key=lambda k: abs(generic[k])) if generic else None
    dominant_generic_abs_z = abs(generic[dominant_generic]) if dominant_generic else 0.0

    if witness:
        dominant_witness = max(witness, key=lambda k: witness[k])
        dominant_witness_z = witness[dominant_witness]
        witness_name = dominant_witness.replace("witness_", "").replace("_z", "")
    else:
        dominant_witness = None
        dominant_witness_z = 0.0
        witness_name = None

    if dominant_witness_z >= 20:
        prediction = f"witness-confirmed: {witness_name}"
        confidence = "very high"
    elif generic_abs_z >= 50:
        prediction = "structured unknown / no exact witness"
        confidence = "high"
    elif generic_abs_z >= 10 or dominant_witness_z >= 5:
        prediction = "borderline / needs longer horizon"
        confidence = "medium"
    else:
        prediction = "random-like / no known witness"
        confidence = "low-to-medium"

    return {
        "prediction": prediction,
        "confidence": confidence,
        "generic_abs_z": generic_abs_z,
        "dominant_generic": dominant_generic,
        "dominant_generic_abs_z": dominant_generic_abs_z,
        "dominant_witness": dominant_witness,
        "dominant_witness_z": dominant_witness_z,
    }
