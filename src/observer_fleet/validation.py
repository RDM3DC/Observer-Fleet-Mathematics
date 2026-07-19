"""Empirical validation helpers for Observer Fleet Mathematics."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Iterable, Mapping, Sequence

from .fleet import ObserverFleet, z_fingerprint


@dataclass(frozen=True)
class LearnedThresholds:
    generic_borderline: float
    generic_structured: float
    witness_borderline: float
    witness_confirmed: float
    borderline_fpr: float
    target_fpr: float
    training_samples: int
    witness_negative_samples: int

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def empirical_quantile(values: Sequence[float], q: float) -> float:
    """Conservative empirical upper-tail quantile."""
    if not values:
        raise ValueError("values must not be empty")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be between 0 and 1")
    ordered = sorted(float(v) for v in values)
    rank = math.ceil((len(ordered) + 1) * q) - 1
    return ordered[min(max(rank, 0), len(ordered) - 1)]


def fingerprint_components(z: Mapping[str, float]) -> dict[str, object]:
    generic = {k: float(v) for k, v in z.items() if not k.startswith("witness_")}
    witness = {k: float(v) for k, v in z.items() if k.startswith("witness_")}
    generic_abs_z = sum(abs(v) for v in generic.values())
    dominant_generic = max(generic, key=lambda k: abs(generic[k])) if generic else None
    if witness:
        dominant_witness = max(witness, key=witness.get)
        dominant_witness_z = witness[dominant_witness]
        witness_name = dominant_witness.removeprefix("witness_").removesuffix("_z")
    else:
        dominant_witness = None
        dominant_witness_z = 0.0
        witness_name = None
    return {
        "generic_abs_z": generic_abs_z,
        "dominant_generic": dominant_generic,
        "dominant_generic_abs_z": abs(generic[dominant_generic]) if dominant_generic else 0.0,
        "dominant_witness": dominant_witness,
        "dominant_witness_z": dominant_witness_z,
        "witness_name": witness_name,
    }


def learn_thresholds(
    random_landscapes: Iterable[str],
    fleet: ObserverFleet,
    baseline: dict[str, dict[str, float]],
    *,
    witness_negative_landscapes: Iterable[str] | None = None,
    target_fpr: float = 0.01,
    borderline_fpr: float = 0.05,
) -> LearnedThresholds:
    """Learn generic thresholds from random controls and witness thresholds from
    random controls plus optional structured decoys.
    """
    if not 0.0 < target_fpr < borderline_fpr < 1.0:
        raise ValueError("require 0 < target_fpr < borderline_fpr < 1")
    generic_scores: list[float] = []
    witness_scores: list[float] = []
    for landscape in random_landscapes:
        c = fingerprint_components(z_fingerprint(landscape, fleet, baseline))
        generic_scores.append(float(c["generic_abs_z"]))
        witness_scores.append(float(c["dominant_witness_z"]))
    if len(generic_scores) < 2:
        raise ValueError("at least two training landscapes are required")
    witness_negative_samples = 0
    if witness_negative_landscapes is not None:
        for landscape in witness_negative_landscapes:
            c = fingerprint_components(z_fingerprint(landscape, fleet, baseline))
            witness_scores.append(float(c["dominant_witness_z"]))
            witness_negative_samples += 1
    return LearnedThresholds(
        generic_borderline=empirical_quantile(generic_scores, 1.0 - borderline_fpr),
        generic_structured=empirical_quantile(generic_scores, 1.0 - target_fpr),
        witness_borderline=empirical_quantile(witness_scores, 1.0 - borderline_fpr),
        witness_confirmed=empirical_quantile(witness_scores, 1.0 - target_fpr),
        borderline_fpr=borderline_fpr,
        target_fpr=target_fpr,
        training_samples=len(generic_scores),
        witness_negative_samples=witness_negative_samples,
    )


def classify_with_thresholds(
    z: Mapping[str, float], thresholds: LearnedThresholds
) -> dict[str, object]:
    c = fingerprint_components(z)
    generic_abs_z = float(c["generic_abs_z"])
    witness_z = float(c["dominant_witness_z"])
    witness_name = c["witness_name"]
    if witness_name and witness_z >= thresholds.witness_confirmed:
        prediction = f"witness-confirmed: {witness_name}"
        confidence = "empirical-high"
    elif generic_abs_z >= thresholds.generic_structured:
        prediction = "structured unknown / no exact witness"
        confidence = "empirical-high"
    elif generic_abs_z >= thresholds.generic_borderline or witness_z >= thresholds.witness_borderline:
        prediction = "borderline / needs longer horizon"
        confidence = "empirical-borderline"
    else:
        prediction = "random-like / no known witness"
        confidence = "empirical-null-consistent"
    return {"prediction": prediction, "confidence": confidence, **c}


def bootstrap_rate_interval(
    outcomes: Sequence[bool], *, confidence: float = 0.95, resamples: int = 2000, seed: int = 0
) -> tuple[float, float]:
    if not outcomes:
        raise ValueError("outcomes must not be empty")
    if resamples < 100:
        raise ValueError("resamples must be at least 100")
    rng = random.Random(seed)
    values = [1.0 if x else 0.0 for x in outcomes]
    n = len(values)
    rates = [sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples)]
    alpha = (1.0 - confidence) / 2.0
    return empirical_quantile(rates, alpha), empirical_quantile(rates, 1.0 - alpha)


def _pearson(a: Sequence[float], b: Sequence[float]) -> float:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    da, db = [x - ma for x in a], [x - mb for x in b]
    denom = math.sqrt(sum(x * x for x in da) * sum(y * y for y in db))
    return sum(x * y for x, y in zip(da, db)) / denom if denom else 0.0


def correlation_matrix(
    z_fingerprints: Sequence[Mapping[str, float]], *, include_witness: bool = False
) -> dict[str, dict[str, float]]:
    if not z_fingerprints:
        raise ValueError("z_fingerprints must not be empty")
    keys = sorted(k for k in z_fingerprints[0] if include_witness or not k.startswith("witness_"))
    columns = {k: [float(row[k]) for row in z_fingerprints] for k in keys}
    return {
        left: {right: 1.0 if left == right else _pearson(columns[left], columns[right]) for right in keys}
        for left in keys
    }


def mean_absolute_off_diagonal_correlation(matrix: Mapping[str, Mapping[str, float]]) -> float:
    values = [abs(float(v)) for left, row in matrix.items() for right, v in row.items() if left != right]
    return sum(values) / len(values) if values else 0.0


def classification_stability(predictions: Sequence[str]) -> float:
    if not predictions:
        raise ValueError("predictions must not be empty")
    counts: dict[str, int] = {}
    for prediction in predictions:
        counts[prediction] = counts.get(prediction, 0) + 1
    return max(counts.values()) / len(predictions)
