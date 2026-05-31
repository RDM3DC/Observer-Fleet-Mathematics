#!/usr/bin/env python3
"""Mission 008: Cosmic Beat Reader.

Reads a nested cosmic-beat input dataset:

    H(z) expansion layer
    BAO/r correlation layer
    CMB-like angular spectrum layer

and returns a first-pass CosmicBeatFingerprint.

The default run generates synthetic data. Later runs can pass JSON matching
``schemas/cosmic_beat_reader.schema.json``.

Run synthetic:
    python experiments/cosmic_beat_reader.py --outdir results/cosmic_beat_reader

Run from JSON:
    python experiments/cosmic_beat_reader.py --input path/to/cosmic_input.json --outdir results/cosmic_beat_reader
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np

try:
    from observer_fleet.fleet_clock_engine import FleetClockEngine, default_moc_101
except Exception:  # pragma: no cover - lets script run directly from repo root or copied file
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
        modulus: int = 101
        a: int = 4
        b: int = 3
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

        def ticks(self, count):
            state = (self.seed[0] % self.modulus, self.seed[1] % self.modulus)
            denom = max(1, self.modulus - 1)
            for i in range(count):
                cur, prev = state
                yield Tick(i, state, i / self.theoretical_max_period, 2.0 * (cur / denom) - 1.0, (cur + prev) % 2)
                state = self.step(state)

    def default_moc_101():
        return FleetClockEngine()


def make_synthetic_input(seed: int = 8) -> Dict[str, object]:
    """Create a synthetic H(z)+BAO+mock-CMB dataset with known nested beat scars."""

    rng = np.random.default_rng(seed)
    h0 = 67.4
    omega_m = 0.315
    omega_l = 1.0 - omega_m

    # H(z): Lambda-CDM-like baseline plus a tiny phase-memory scar.
    z = np.linspace(0.0, 2.4, 80)
    model_h = h0 * np.sqrt(omega_m * (1 + z) ** 3 + omega_l)
    h_scar = 1.25 * np.exp(-((z - 1.08) ** 2) / (2 * 0.12**2)) * np.sin(11 * z)
    h_obs = model_h + h_scar + rng.normal(0.0, 0.75, len(z))

    # BAO: smooth background plus a bump near 147 Mpc.
    r = np.linspace(70.0, 220.0, 180)
    model_xi = 0.015 * np.exp(-r / 130.0)
    bao_bump = 0.034 * np.exp(-((r - 147.0) ** 2) / (2 * 8.5**2))
    xi = model_xi + bao_bump + rng.normal(0.0, 0.0035, len(r))

    # CMB-like angular spectrum: damped broad oscillations plus residual ripple.
    ell = np.arange(2, 1202)
    model_cl = (1.0 / (ell * (ell + 1))) * (1.0 + 0.12 * np.sin(ell / 48.0)) * np.exp(-ell / 1600.0)
    cmb_ripple = 0.00000045 * np.exp(-((ell - 420) ** 2) / (2 * 110**2)) * np.sin(ell / 9.0)
    cl = model_cl + cmb_ripple + rng.normal(0.0, 0.00000012, len(ell))

    return {
        "metadata": {
            "name": "synthetic_cosmic_memory_beat_v1",
            "source": "generated",
            "description": "Synthetic H(z), BAO, and mock CMB-like spectrum for Mission 008.",
            "units": {
                "hz_x": "redshift z",
                "hz_y": "km/s/Mpc",
                "bao_x": "Mpc",
                "bao_y": "correlation amplitude",
                "cmb_x": "multipole ell",
                "cmb_y": "normalized C_ell",
            },
        },
        "clock": {"modulus": 101, "a": 4, "b": 3, "seed": [1, 1], "sample_count": 256},
        "hz": [{"z": float(x), "H": float(y), "sigma": 0.75, "model_H": float(m)} for x, y, m in zip(z, h_obs, model_h)],
        "bao": [{"r": float(x), "xi": float(y), "sigma": 0.0035, "model_xi": float(m)} for x, y, m in zip(r, xi, model_xi)],
        "cmb": [{"ell": float(x), "cl": float(y), "sigma": 0.00000012, "model_cl": float(m)} for x, y, m in zip(ell, cl, model_cl)],
    }


def load_input(path: Path | None, seed: int) -> Dict[str, object]:
    if path is None:
        return make_synthetic_input(seed)
    return json.loads(path.read_text(encoding="utf-8"))


def residual_series(rows: List[Dict[str, float]], x_key: str, y_key: str, model_key: str) -> Tuple[np.ndarray, np.ndarray]:
    x = np.array([float(row[x_key]) for row in rows], dtype=float)
    y = np.array([float(row[y_key]) for row in rows], dtype=float)
    if all(model_key in row for row in rows):
        model = np.array([float(row[model_key]) for row in rows], dtype=float)
    else:
        # Conservative fallback: polynomial smooth background.
        deg = min(3, max(1, len(x) // 25))
        model = np.polyval(np.polyfit(x, y, deg), x)
    return x, y - model


def memory_word(values: Iterable[float], chunks: int = 24) -> str:
    arr = np.asarray(list(values), dtype=float)
    if len(arr) < 3:
        return "S"
    d = np.diff(arr)
    scale = np.std(arr) + 1e-12
    symbols: List[str] = []
    for chunk in np.array_split(d, min(chunks, max(1, len(d)))):
        if len(chunk) == 0:
            continue
        mean = float(np.mean(chunk))
        mx = float(np.max(np.abs(chunk)))
        if mx > 3.0 * scale:
            symbols.append("J")
        elif abs(mean) < 0.025 * scale:
            symbols.append("S")
        elif mean > 0:
            symbols.append("R+")
        else:
            symbols.append("R-")
    compact: List[str] = []
    for symbol in symbols:
        if not compact or compact[-1] != symbol:
            compact.append(symbol)
    return " ".join(compact) if compact else "S"


def normalize(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=float)
    return (arr - np.mean(arr)) / (np.std(arr) + 1e-12)


def sample_window(x: np.ndarray, y: np.ndarray, phase: float, width_fraction: float) -> np.ndarray:
    """MOC-selected moving window over a residual series."""

    if len(x) == 0:
        return np.array([], dtype=float)
    x0, x1 = float(np.min(x)), float(np.max(x))
    center = x0 + phase * (x1 - x0)
    width = max(1e-12, width_fraction * (x1 - x0))
    mask = np.abs(x - center) <= width / 2.0
    if np.sum(mask) < 3:
        nearest = np.argsort(np.abs(x - center))[: min(7, len(x))]
        return y[nearest]
    return y[mask]


def layer_fingerprint(name: str, x: np.ndarray, residual: np.ndarray, ticks, width_fraction: float) -> Dict[str, object]:
    norm_res = normalize(residual)
    observer_words: List[str] = []
    energies: List[float] = []
    signs: List[float] = []
    for tick in ticks:
        # Use the MOC phase to select where to read and the centered scalar as a small observer tilt.
        window = sample_window(x, norm_res, tick.phase, width_fraction)
        tilted = window * (1.0 + 0.05 * tick.centered)
        observer_words.append(memory_word(tilted, chunks=8))
        energies.append(float(np.sqrt(np.mean(tilted**2))) if len(tilted) else 0.0)
        signs.append(float(np.mean(np.sign(tilted))) if len(tilted) else 0.0)

    # Consensus is intentionally simple for v1: modal memory word plus stability stats.
    counts: Dict[str, int] = {}
    for word in observer_words:
        counts[word] = counts.get(word, 0) + 1
    consensus_word = max(counts.items(), key=lambda kv: kv[1])[0]
    consensus_fraction = counts[consensus_word] / max(1, len(observer_words))

    return {
        "layer": name,
        "global_memory_word": memory_word(norm_res, chunks=24),
        "observer_consensus_word": consensus_word,
        "observer_consensus_fraction": consensus_fraction,
        "residual_energy": float(np.sqrt(np.mean(norm_res**2))),
        "observer_energy_mean": float(np.mean(energies)),
        "observer_energy_std": float(np.std(energies)),
        "observer_sign_mean": float(np.mean(signs)),
        "stability_score": float(1.0 / (1.0 + np.std(energies)) * (0.5 + 0.5 * consensus_fraction)),
        "observer_words_sample": observer_words[:12],
    }


def cross_layer_alignment(layers: List[Dict[str, object]]) -> float:
    words = [str(layer["global_memory_word"]).split() for layer in layers]
    if len(words) < 2:
        return 1.0
    vocab = sorted(set(token for word in words for token in word))
    if not vocab:
        return 0.0
    vecs = []
    for word in words:
        vec = np.array([word.count(token) for token in vocab], dtype=float)
        vecs.append(vec / (np.linalg.norm(vec) + 1e-12))
    sims = []
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            sims.append(float(np.dot(vecs[i], vecs[j])))
    return float(np.mean(sims))


def build_fingerprint(data: Dict[str, object]) -> Dict[str, object]:
    clock_cfg = data.get("clock", {})
    clock = FleetClockEngine(
        modulus=int(clock_cfg.get("modulus", 101)),
        a=int(clock_cfg.get("a", 4)),
        b=int(clock_cfg.get("b", 3)),
        seed=tuple(clock_cfg.get("seed", [1, 1])),
    )
    sample_count = int(clock_cfg.get("sample_count", 256))
    ticks = list(clock.ticks(sample_count))

    hz_x, hz_res = residual_series(data["hz"], "z", "H", "model_H")
    bao_x, bao_res = residual_series(data["bao"], "r", "xi", "model_xi")
    cmb_x, cmb_res = residual_series(data["cmb"], "ell", "cl", "model_cl")

    layers = [
        layer_fingerprint("H_expansion", hz_x, hz_res, ticks, width_fraction=0.24),
        layer_fingerprint("BAO_fossil_memory", bao_x, bao_res, ticks, width_fraction=0.18),
        layer_fingerprint("CMB_background_hum", cmb_x, cmb_res, ticks, width_fraction=0.12),
    ]
    alignment = cross_layer_alignment(layers)
    stability = float(np.mean([layer["stability_score"] for layer in layers]))

    return {
        "fingerprint_type": "CosmicBeatFingerprint.v1",
        "source_name": data.get("metadata", {}).get("name", "unknown"),
        "clock": {
            "modulus": clock.modulus,
            "a": clock.a,
            "b": clock.b,
            "seed": list(clock.seed),
            "period": clock.period(),
            "theoretical_max_period": clock.theoretical_max_period,
            "sample_count": sample_count,
        },
        "layers": layers,
        "cross_layer_alignment": alignment,
        "overall_stability_score": stability,
        "cosmic_memory_word": " | ".join(str(layer["global_memory_word"]) for layer in layers),
        "interpretation": {
            "H_expansion": "present expansion beat residual",
            "BAO_fossil_memory": "fossil acoustic scar residual",
            "CMB_background_hum": "thermal background hum residual",
            "Phi_MOC": "deterministic observer-state scan",
        },
        "status": "synthetic-ready v1; public-data adapters are next",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default=None)
    parser.add_argument("--outdir", default="results/cosmic_beat_reader")
    parser.add_argument("--seed", type=int, default=8)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    data = load_input(Path(args.input) if args.input else None, args.seed)
    fingerprint = build_fingerprint(data)

    (outdir / "cosmic_beat_input.synthetic.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (outdir / "cosmic_beat_fingerprint.v1.json").write_text(json.dumps(fingerprint, indent=2), encoding="utf-8")

    lines = [
        "# Cosmic Beat Reader v1",
        "",
        f"Source: `{fingerprint['source_name']}`",
        "",
        f"Cosmic memory word: `{fingerprint['cosmic_memory_word']}`",
        "",
        f"Cross-layer alignment: `{fingerprint['cross_layer_alignment']:.6f}`",
        f"Overall stability score: `{fingerprint['overall_stability_score']:.6f}`",
        "",
        "## Layers",
        "",
    ]
    for layer in fingerprint["layers"]:
        lines += [
            f"### {layer['layer']}",
            "",
            f"- global word: `{layer['global_memory_word']}`",
            f"- observer consensus word: `{layer['observer_consensus_word']}`",
            f"- consensus fraction: `{layer['observer_consensus_fraction']:.6f}`",
            f"- stability score: `{layer['stability_score']:.6f}`",
            f"- residual energy: `{layer['residual_energy']:.6f}`",
            "",
        ]
    (outdir / "cosmic_beat_reader_summary.md").write_text("\n".join(lines), encoding="utf-8")

    print("CosmicBeatFingerprint.v1")
    print("cosmic_memory_word:", fingerprint["cosmic_memory_word"])
    print("cross_layer_alignment:", fingerprint["cross_layer_alignment"])
    print("overall_stability_score:", fingerprint["overall_stability_score"])
    print(f"Wrote results to: {outdir.resolve()}")


if __name__ == "__main__":
    main()
