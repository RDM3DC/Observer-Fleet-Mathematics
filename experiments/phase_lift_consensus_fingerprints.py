#!/usr/bin/env python3
"""Mission 008 add-on: p=5 / p=7 Phase-Lift consensus fingerprints.

This experiment locks a residual-only schema and generates first small-clock
consensus fingerprints for synthetic H(z)+BAO+CMB residual bundles.

Why p=5 and p=7 first?
    They are small maximal clocks, so the complete observer cycle is easy to
    inspect by hand before scaling back to MOC-101.

Default clocks:
    p=5: s_k = 1*s_(k-1) + 3*s_(k-2) mod 5, period 24
    p=7: s_k = 1*s_(k-1) + 4*s_(k-2) mod 7, period 48

Run:
    python experiments/phase_lift_consensus_fingerprints.py --outdir results/phase_lift_consensus
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np

try:
    from observer_fleet.fleet_clock_engine import FleetClockEngine
except Exception:  # pragma: no cover
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Tick:
        index: int
        state: Tuple[int, int]
        phase: float
        centered: float
        parity: int

    @dataclass(frozen=True)
    class FleetClockEngine:
        modulus: int
        a: int
        b: int
        seed: Tuple[int, int] = (1, 1)

        @property
        def theoretical_max_period(self):
            return self.modulus * self.modulus - 1

        def step(self, state):
            cur, prev = state
            return ((self.a * cur + self.b * prev) % self.modulus, cur % self.modulus)

        def period(self, limit=None):
            start = (self.seed[0] % self.modulus, self.seed[1] % self.modulus)
            state = start
            for k in range(1, (limit or self.theoretical_max_period + 5) + 1):
                state = self.step(state)
                if state == start:
                    return k
            return -1

        def ticks(self, count=None):
            total = self.theoretical_max_period if count is None else count
            state = (self.seed[0] % self.modulus, self.seed[1] % self.modulus)
            denom = max(1, self.modulus - 1)
            for i in range(total):
                cur, prev = state
                yield Tick(i, state, i / self.theoretical_max_period, 2.0 * (cur / denom) - 1.0, (cur + prev) % 2)
                state = self.step(state)


def memory_word(values: Iterable[float], chunks: int = 12) -> str:
    arr = np.asarray(list(values), dtype=float)
    if len(arr) < 3:
        return "S"
    arr = (arr - np.mean(arr)) / (np.std(arr) + 1e-12)
    delta = np.diff(arr)
    symbols: List[str] = []
    for chunk in np.array_split(delta, min(chunks, max(1, len(delta)))):
        if len(chunk) == 0:
            continue
        mean = float(np.mean(chunk))
        mx = float(np.max(np.abs(chunk)))
        if mx > 3.0:
            symbols.append("J")
        elif abs(mean) < 0.025:
            symbols.append("S")
        elif mean > 0:
            symbols.append("R+")
        else:
            symbols.append("R-")
    compact: List[str] = []
    for s in symbols:
        if not compact or compact[-1] != s:
            compact.append(s)
    return " ".join(compact) if compact else "S"


def synthetic_residual_bundle(seed: int = 57) -> Dict[str, object]:
    rng = np.random.default_rng(seed)

    z = np.linspace(0.0, 2.4, 96)
    hz_res = 0.18 * np.sin(7.0 * z) * np.exp(-((z - 1.05) ** 2) / (2 * 0.38**2))
    hz_res += 0.055 * np.sin(18.0 * z) * np.exp(-((z - 1.20) ** 2) / (2 * 0.10**2))
    hz_res += rng.normal(0.0, 0.035, len(z))

    r = np.linspace(70.0, 220.0, 180)
    bao_res = 0.045 * np.exp(-((r - 147.0) ** 2) / (2 * 8.5**2))
    bao_res += 0.010 * np.sin(r / 5.7) * np.exp(-((r - 147.0) ** 2) / (2 * 22.0**2))
    bao_res += rng.normal(0.0, 0.004, len(r))

    ell = np.arange(2, 902)
    cmb_res = 3.0e-7 * np.exp(-((ell - 420.0) ** 2) / (2 * 140.0**2)) * np.sin(ell / 8.0)
    cmb_res += 1.2e-7 * np.exp(-((ell - 710.0) ** 2) / (2 * 90.0**2)) * np.cos(ell / 13.0)
    cmb_res += rng.normal(0.0, 8.0e-8, len(ell))

    return {
        "metadata": {
            "name": "synthetic_residual_bundle_p5_p7_v1",
            "source": "generated",
            "description": "Residual-only H(z)+BAO+CMB bundle for small-clock Phase-Lift consensus.",
            "created_by": "Mission 008 Phase-Lift consensus runner",
        },
        "clock_set": [
            {"name": "MOC-5-a1-b3", "modulus": 5, "a": 1, "b": 3, "seed": [1, 1]},
            {"name": "MOC-7-a1-b4", "modulus": 7, "a": 1, "b": 4, "seed": [1, 1]},
        ],
        "layers": {
            "hz": {
                "name": "H_expansion_residual",
                "x_unit": "redshift z",
                "residual_unit": "normalized H residual",
                "model_name": "synthetic Lambda-CDM baseline",
                "points": [{"x": float(x), "residual": float(y), "sigma": 0.035} for x, y in zip(z, hz_res)],
            },
            "bao": {
                "name": "BAO_fossil_memory_residual",
                "x_unit": "Mpc",
                "residual_unit": "correlation residual",
                "model_name": "smooth correlation background",
                "points": [{"x": float(x), "residual": float(y), "sigma": 0.004} for x, y in zip(r, bao_res)],
            },
            "cmb": {
                "name": "CMB_background_hum_residual",
                "x_unit": "multipole ell",
                "residual_unit": "normalized C_ell residual",
                "model_name": "smooth mock angular spectrum",
                "points": [{"x": float(x), "residual": float(y), "sigma": 8.0e-8} for x, y in zip(ell, cmb_res)],
            },
        },
    }


def read_layer(layer: Dict[str, object]) -> Tuple[np.ndarray, np.ndarray]:
    points = layer["points"]
    x = np.array([float(p["x"]) for p in points], dtype=float)
    r = np.array([float(p["residual"]) for p in points], dtype=float)
    return x, r


def normalize(arr: np.ndarray) -> np.ndarray:
    return (arr - np.mean(arr)) / (np.std(arr) + 1e-12)


def phase_lift_path(x: np.ndarray, residual: np.ndarray) -> np.ndarray:
    """Turn residuals into a simple unwrapped phase path.

    This v1 lift treats the residual trajectory as a complex path
    ``x_normalized + i residual_normalized`` and unwraps its angle.
    """

    xn = normalize(x)
    rn = normalize(residual)
    return np.unwrap(np.angle(xn + 1j * rn))


def tick_window(x: np.ndarray, values: np.ndarray, phase: float, width_fraction: float) -> np.ndarray:
    x0, x1 = float(np.min(x)), float(np.max(x))
    center = x0 + phase * (x1 - x0)
    width = width_fraction * (x1 - x0)
    mask = np.abs(x - center) <= width / 2.0
    if np.sum(mask) < 4:
        idx = np.argsort(np.abs(x - center))[: min(9, len(x))]
        return values[idx]
    return values[mask]


def layer_clock_consensus(layer_name: str, layer: Dict[str, object], clock: FleetClockEngine) -> Dict[str, object]:
    x, residual = read_layer(layer)
    lifted = phase_lift_path(x, residual)
    rn = normalize(residual)

    words = []
    energies = []
    parity_words = {0: [], 1: []}
    for tick in clock.ticks(clock.period()):
        window_res = tick_window(x, rn, tick.phase, width_fraction=0.18)
        window_phase = tick_window(x, lifted, tick.phase, width_fraction=0.18)
        combined = window_res + 0.20 * tick.centered * normalize(window_phase)
        word = memory_word(combined, chunks=8)
        words.append(word)
        parity_words[tick.parity].append(word)
        energies.append(float(np.sqrt(np.mean(combined**2))))

    counts = Counter(words)
    consensus_word, consensus_count = counts.most_common(1)[0]
    parity_consensus = {}
    for parity, pwords in parity_words.items():
        pc = Counter(pwords)
        if pc:
            word, count = pc.most_common(1)[0]
            parity_consensus[str(parity)] = {"word": word, "fraction": count / len(pwords)}

    return {
        "layer": layer_name,
        "layer_name": layer.get("name", layer_name),
        "global_residual_word": memory_word(rn, chunks=18),
        "global_phase_lift_word": memory_word(lifted, chunks=18),
        "observer_consensus_word": consensus_word,
        "observer_consensus_fraction": consensus_count / len(words),
        "parity_consensus": parity_consensus,
        "observer_energy_mean": float(np.mean(energies)),
        "observer_energy_std": float(np.std(energies)),
        "stability_score": float((consensus_count / len(words)) / (1.0 + np.std(energies))),
        "observer_words_sample": words[:12],
    }


def clock_fingerprint(bundle: Dict[str, object], clock_cfg: Dict[str, object]) -> Dict[str, object]:
    clock = FleetClockEngine(
        modulus=int(clock_cfg["modulus"]),
        a=int(clock_cfg["a"]),
        b=int(clock_cfg["b"]),
        seed=tuple(clock_cfg.get("seed", [1, 1])),
    )
    layers = [layer_clock_consensus(name, layer, clock) for name, layer in bundle["layers"].items()]
    cosmic_word = " | ".join(layer["global_phase_lift_word"] for layer in layers)
    stability = float(np.mean([layer["stability_score"] for layer in layers]))
    return {
        "fingerprint_type": "PhaseLiftConsensusFingerprint.v1",
        "clock": {
            "name": clock_cfg["name"],
            "modulus": clock.modulus,
            "a": clock.a,
            "b": clock.b,
            "seed": list(clock.seed),
            "period": clock.period(),
            "theoretical_max_period": clock.theoretical_max_period,
            "maximal": clock.period() == clock.theoretical_max_period,
        },
        "layers": layers,
        "cosmic_phase_lift_word": cosmic_word,
        "overall_stability_score": stability,
    }


def compare_clock_fingerprints(fingerprints: List[Dict[str, object]]) -> Dict[str, object]:
    if len(fingerprints) < 2:
        return {"clock_consensus": 1.0, "notes": "single clock"}
    layer_names = [layer["layer"] for layer in fingerprints[0]["layers"]]
    agreements = []
    details = {}
    for layer_name in layer_names:
        words = []
        for fp in fingerprints:
            layer = next(layer for layer in fp["layers"] if layer["layer"] == layer_name)
            words.append(layer["global_phase_lift_word"])
        base = words[0]
        same = sum(1 for word in words if word == base) / len(words)
        agreements.append(same)
        details[layer_name] = {"words": words, "same_fraction": same}
    return {
        "clock_consensus": float(np.mean(agreements)),
        "layer_details": details,
        "notes": "compares global phase-lift words across p=5/p=7 clocks",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default=None)
    parser.add_argument("--outdir", default="results/phase_lift_consensus")
    parser.add_argument("--seed", type=int, default=57)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if args.input:
        bundle = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        bundle = synthetic_residual_bundle(args.seed)

    fingerprints = [clock_fingerprint(bundle, cfg) for cfg in bundle["clock_set"]]
    comparison = compare_clock_fingerprints(fingerprints)
    output = {
        "source_name": bundle["metadata"]["name"],
        "fingerprints": fingerprints,
        "p5_p7_comparison": comparison,
        "status": "first small-clock Phase-Lift consensus fingerprint run",
    }

    (outdir / "cosmic_residual_bundle.synthetic.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    (outdir / "phase_lift_consensus_fingerprints.v1.json").write_text(json.dumps(output, indent=2), encoding="utf-8")

    lines = [
        "# Phase-Lift Consensus Fingerprints v1",
        "",
        f"Source: `{bundle['metadata']['name']}`",
        "",
        f"p=5/p=7 clock consensus: `{comparison['clock_consensus']:.6f}`",
        "",
    ]
    for fp in fingerprints:
        clock = fp["clock"]
        lines += [
            f"## {clock['name']}",
            "",
            f"- period: `{clock['period']}`",
            f"- maximal: `{clock['maximal']}`",
            f"- cosmic phase-lift word: `{fp['cosmic_phase_lift_word']}`",
            f"- overall stability: `{fp['overall_stability_score']:.6f}`",
            "",
        ]
        for layer in fp["layers"]:
            lines += [
                f"### {layer['layer']}",
                f"- global residual word: `{layer['global_residual_word']}`",
                f"- global phase-lift word: `{layer['global_phase_lift_word']}`",
                f"- observer consensus word: `{layer['observer_consensus_word']}`",
                f"- consensus fraction: `{layer['observer_consensus_fraction']:.6f}`",
                f"- stability score: `{layer['stability_score']:.6f}`",
                "",
            ]
    (outdir / "phase_lift_consensus_summary.md").write_text("\n".join(lines), encoding="utf-8")

    print("PhaseLiftConsensusFingerprint.v1")
    print("p5_p7_clock_consensus:", comparison["clock_consensus"])
    for fp in fingerprints:
        print(fp["clock"]["name"], "period", fp["clock"]["period"], "word", fp["cosmic_phase_lift_word"])
    print(f"Wrote results to: {outdir.resolve()}")


if __name__ == "__main__":
    main()
