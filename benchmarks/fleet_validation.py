#!/usr/bin/env python3
"""Held-out statistical benchmark for Observer Fleet Mathematics.

Fast mode is suitable for local development. Full mode evaluates three horizons
with 250 calibration controls, 250 threshold controls, and 500 held-out random
controls per horizon (3,000 independent random controls total).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random

from observer_fleet.fleet import ObserverFleet, calibrate_against_random, z_fingerprint
from observer_fleet.landscapes import GENERATOR_LIBRARY, mutate_digits, random_digits, repeating_cycle
from observer_fleet.ships import GENERIC_SHIPS, build_witness_ships
from observer_fleet.validation import (
    bootstrap_rate_interval,
    classify_with_thresholds,
    correlation_matrix,
    learn_thresholds,
    mean_absolute_off_diagonal_correlation,
)


@dataclass(frozen=True)
class Mode:
    horizons: tuple[int, ...]
    calibration: int
    threshold: int
    test: int
    structured: int
    witness_repetitions: int
    witness_decoys: int


MODES = {
    "fast": Mode((300, 600), 40, 40, 80, 8, 2, 40),
    "full": Mode((300, 600, 1200), 250, 250, 500, 24, 6, 250),
}


def paperfolding(n: int, low: str = "1", high: str = "8") -> str:
    out = []
    for i in range(1, n + 1):
        k = i
        while k % 2 == 0:
            k //= 2
        out.append(high if k % 4 == 1 else low)
    return "".join(out)


def block_ramp(n: int, base: int = 3, offset: int = 0) -> str:
    out, k = [], 1 + offset
    while len(out) < n:
        out.extend(str((k // base) % 10) for _ in range(1 + k % 7))
        k += 1
    return "".join(out[:n])


def quadratic_residue(n: int, modulus: int = 1009, shift: int = 0) -> str:
    return "".join(str(((i + shift) * (i + shift)) % modulus % 10) for i in range(n))


def period_doubling(n: int, low: str = "2", high: str = "8") -> str:
    word = "0"
    while len(word) < n:
        word = "".join("01" if ch == "0" else "00" for ch in word)
    return "".join(low if ch == "0" else high for ch in word[:n])


def rudin_shapiro(n: int, low: str = "3", high: str = "7") -> str:
    return "".join(high if bin(i).count("11") % 2 else low for i in range(n))


def cubic_digits(n: int, offset: int = 0) -> str:
    text, k = "", 1 + offset
    while len(text) < n:
        text += str(k**3)
        k += 1
    return text[:n]


def decoys(n: int, count: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    out = []
    for i in range(count):
        family = i % 4
        if family == 0:
            digits = list("0123456789")
            rng.shuffle(digits)
            out.append(repeating_cycle(n, "".join(digits)))
        elif family == 1:
            out.append(period_doubling(n, *rng.sample(list("0123456789"), 2)))
        elif family == 2:
            out.append(rudin_shapiro(n, *rng.sample(list("0123456789"), 2)))
        else:
            out.append(cubic_digits(n, rng.randrange(50)))
    return out


def held_out(n: int, count: int, seed: int) -> dict[str, str]:
    rng = random.Random(seed)
    out = {}
    for i in range(count):
        family = i % 3
        if family == 0:
            low, high = rng.sample(list("0123456789"), 2)
            out[f"paperfolding_{i}"] = paperfolding(n, low, high)
        elif family == 1:
            out[f"block_ramp_{i}"] = block_ramp(n, rng.choice((3, 5, 7)), rng.randrange(12))
        else:
            out[f"quadratic_residue_{i}"] = quadratic_residue(n, rng.choice((1009, 1013, 1019)), rng.randrange(1000))
    return out


def known_witnesses(n: int, repetitions: int, seed: int) -> dict[str, tuple[str, str]]:
    rng = random.Random(seed)
    out = {}
    rates = (0.0, 0.01, 0.03)
    for name, generator in GENERATOR_LIBRARY.items():
        base = generator(n)
        for rep in range(repetitions):
            rate = rates[rep % len(rates)]
            sample = base if rate == 0 else mutate_digits(base, rate=rate, seed=rng.randrange(10**9))
            out[f"{name}_noise{rate:.2f}_r{rep}"] = (name, sample)
    return out


def bucket(prediction: str) -> str:
    if prediction.startswith("witness-confirmed"):
        return "witness-confirmed"
    if prediction.startswith("structured unknown"):
        return "structured-unknown"
    if prediction.startswith("borderline"):
        return "borderline"
    return "random-like"


def rate(values: list[bool], seed: int) -> dict[str, object]:
    low, high = bootstrap_rate_interval(values, resamples=1000, seed=seed)
    return {"count": len(values), "rate": sum(values) / len(values), "bootstrap_95_ci": [low, high]}


def run_horizon(task: tuple[int, Mode, int, int]) -> tuple[dict, list[dict]]:
    n, mode, seed, case_seed = task
    fleet = ObserverFleet.from_functions(GENERIC_SHIPS, build_witness_ships(GENERATOR_LIBRARY))
    calibration = [random_digits(n, seed=seed + i) for i in range(mode.calibration)]
    training = [random_digits(n, seed=seed + 100_000 + i) for i in range(mode.threshold)]
    random_test = [random_digits(n, seed=seed + 200_000 + i) for i in range(mode.test)]
    baseline = calibrate_against_random(calibration, fleet)
    thresholds = learn_thresholds(
        training,
        fleet,
        baseline,
        witness_negative_landscapes=decoys(n, mode.witness_decoys, case_seed + 250_000),
        target_fpr=0.01,
        borderline_fpr=0.05,
    )
    records, z_rows = [], []
    random_strict, random_alert = [], []
    structured_correct, false_witness = [], []
    witness_recall, witness_exact = [], []

    def classify(name: str, family: str, expected: str, landscape: str) -> tuple[str, dict]:
        z = z_fingerprint(landscape, fleet, baseline)
        result = classify_with_thresholds(z, thresholds)
        b = bucket(str(result["prediction"]))
        z_rows.append(z)
        records.append({"name": name, "family": family, "expected": expected, "prediction": result["prediction"], "bucket": b})
        return b, result

    for i, landscape in enumerate(random_test):
        b, _ = classify(f"random_{i}", "random", "random-like", landscape)
        random_strict.append(b in {"structured-unknown", "witness-confirmed"})
        random_alert.append(b != "random-like")

    for name, landscape in held_out(n, mode.structured, case_seed + 300_000).items():
        b, _ = classify(name, "held-out-structured", "structured-unknown", landscape)
        structured_correct.append(b == "structured-unknown")
        false_witness.append(b == "witness-confirmed")

    for name, (expected, landscape) in known_witnesses(n, mode.witness_repetitions, case_seed + 400_000).items():
        b, result = classify(name, "known-witness", expected, landscape)
        witness_recall.append(b == "witness-confirmed")
        witness_exact.append(b == "witness-confirmed" and result.get("witness_name") == expected)

    matrix = correlation_matrix(z_rows)
    return {
        "horizon": n,
        "splits": {
            "calibration_controls": mode.calibration,
            "threshold_controls": mode.threshold,
            "random_test_controls": mode.test,
            "witness_decoys": mode.witness_decoys,
            "held_out_structured": len(structured_correct),
            "known_witness": len(witness_recall),
        },
        "thresholds": thresholds.to_dict(),
        "metrics": {
            "random_strict_false_positive": rate(random_strict, seed + 1),
            "random_alert_including_borderline": rate(random_alert, seed + 2),
            "structured_correct": rate(structured_correct, seed + 3),
            "structured_false_witness": rate(false_witness, seed + 4),
            "witness_recall": rate(witness_recall, seed + 5),
            "witness_exact": rate(witness_exact, seed + 6),
        },
        "generic_ship_correlation": matrix,
        "mean_absolute_off_diagonal_correlation": mean_absolute_off_diagonal_correlation(matrix),
    }, records


def markdown(report: dict) -> str:
    lines = [
        "# Observer Fleet Validation Report", "",
        f"Generated: `{report['generated_at']}`", f"Mode: `{report['mode']}`", f"Seed: `{report['seed']}`", "",
        "Calibration, threshold training, structured witness-decoy training, and final testing use disjoint seeds.", "",
        "| Horizon | Strict random FPR | Alert incl. borderline | Structured correct | False witness | Witness recall | Exact witness | Mean abs. correlation |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["horizons"]:
        m = item["metrics"]
        lines.append(
            f"| {item['horizon']} | {m['random_strict_false_positive']['rate']:.3f} | "
            f"{m['random_alert_including_borderline']['rate']:.3f} | {m['structured_correct']['rate']:.3f} | "
            f"{m['structured_false_witness']['rate']:.3f} | {m['witness_recall']['rate']:.3f} | "
            f"{m['witness_exact']['rate']:.3f} | {item['mean_absolute_off_diagonal_correlation']:.3f} |"
        )
    lines += ["", "Strict false positives exclude borderline alerts. Held-out structured families are absent from the witness library and decoy families.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=MODES, default="fast")
    parser.add_argument("--seed", type=int, default=7919)
    parser.add_argument("--jobs", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark_results"))
    args = parser.parse_args()
    mode = MODES[args.mode]
    tasks = [(h, mode, args.seed + i * 1_000_000, args.seed) for i, h in enumerate(mode.horizons)]
    jobs = max(1, min(args.jobs or (os.cpu_count() or 1), len(tasks)))
    if jobs == 1:
        completed = [run_horizon(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            completed = list(pool.map(run_horizon, tasks))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "seed": args.seed,
        "configuration": asdict(mode),
        "horizons": [item[0] for item in completed],
        "records": {str(h): records for h, (_, records) in zip(mode.horizons, completed)},
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.output_dir / f"fleet_validation_{args.mode}"
    stem.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    text = markdown(report)
    stem.with_suffix(".md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
