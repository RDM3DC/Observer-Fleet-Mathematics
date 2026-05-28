"""Observer ships.

Generic ships explore.
Witness ships testify.
"""

from __future__ import annotations

import math
import zlib
from collections import Counter
from typing import Callable


def entropy_bits_per_digit(s: str) -> float:
    c = Counter(s)
    n = len(s)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def zlib_compression_ratio(s: str) -> float:
    raw = s.encode()
    return len(zlib.compress(raw, 9)) / max(1, len(raw))


def repeat_score(s: str) -> float:
    if len(s) < 3:
        return 0.0

    bigrams = Counter(s[i : i + 2] for i in range(len(s) - 1))
    trigrams = Counter(s[i : i + 3] for i in range(len(s) - 2))

    b = sum(v - 1 for v in bigrams.values() if v > 1)
    t = sum(v - 1 for v in trigrams.values() if v > 1)

    return (b + 2 * t) / len(s)


def chi_square_uniform(s: str) -> float:
    c = Counter(s)
    n = len(s)
    exp = n / 10
    return sum((c.get(str(d), 0) - exp) ** 2 / exp for d in range(10))


def digit_frequency_ship(s: str, window: int = 100, step: int = 10) -> float:
    vals = [
        chi_square_uniform(s[i : i + window])
        for i in range(0, len(s) - window + 1, step)
    ]
    if not vals:
        return chi_square_uniform(s)
    return sum(vals) / len(vals) + 0.2 * max(vals)


def compression_ship(s: str) -> float:
    """Higher means more compressible."""
    return 1.0 - zlib_compression_ratio(s)


def modular_cycle_ship(s: str, max_lag: int = 40) -> float:
    vals: list[float] = []
    for lag in range(1, max_lag + 1):
        matches = sum(1 for i in range(len(s) - lag) if s[i] == s[i + lag])
        rate = matches / max(1, len(s) - lag)
        vals.append(abs(rate - 0.1))
    return max(vals) + sum(vals) / len(vals)


def prime_gap_ship(s: str) -> float:
    prime_set = set("2357")
    positions = [i for i, ch in enumerate(s) if ch in prime_set]
    if len(positions) < 3:
        return 0.0

    gaps = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
    mean_gap = sum(gaps) / len(gaps)
    var_gap = sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)

    # For random decimal digits, prime digit probability is 0.4.
    return abs(mean_gap - 2.5) + abs(var_gap - 3.75) / 3.75


def fourier_wave_ship(s: str, max_freq: int = 50) -> float:
    xs = [int(ch) - 4.5 for ch in s]
    n = len(xs)
    total_power = sum(x * x for x in xs) or 1.0
    top = 0.0
    low_power = 0.0

    for k in range(1, max_freq + 1):
        re = 0.0
        im = 0.0
        for t, x in enumerate(xs):
            ang = 2 * math.pi * k * t / n
            re += x * math.cos(ang)
            im -= x * math.sin(ang)
        p = (re * re + im * im) / n
        low_power += p
        top = max(top, p)

    return top / total_power + 0.1 * low_power / total_power


def arp_memory_ship(
    s: str,
    window: int = 100,
    step: int = 10,
    alpha: float = 0.18,
    mu: float = 0.015,
) -> float:
    """ARP-style memory: fading old signal + strengthening from new surprise."""
    mem = 0.0
    trace: list[float] = []
    repeats: list[float] = []
    counts: Counter[str] = Counter()
    wchars: list[str] = []

    for i, d in enumerate(s):
        wchars.append(d)
        counts[d] += 1

        if len(wchars) > window:
            old = wchars.pop(0)
            counts[old] -= 1
            if counts[old] <= 0:
                del counts[old]

        freq = counts[d] / len(wchars)
        surprise = abs(freq - 0.1)
        mem = (1 - mu) * mem + alpha * surprise
        trace.append(mem)

        if i >= window and i % step == 0:
            repeats.append(repeat_score("".join(wchars)))

    mean = sum(trace) / len(trace)
    std = (sum((x - mean) ** 2 for x in trace) / len(trace)) ** 0.5
    return max(trace) + 3 * std + (sum(repeats) / len(repeats) if repeats else 0.0)


def phase_lift_ship(s: str) -> float:
    """Track digit-to-phase step coherence and winding imbalance."""
    angles = [2 * math.pi * int(ch) / 10 for ch in s]
    steps: list[float] = []

    for i in range(len(angles) - 1):
        d = angles[i + 1] - angles[i]
        while d <= -math.pi:
            d += 2 * math.pi
        while d > math.pi:
            d -= 2 * math.pi
        steps.append(d)

    if not steps:
        return 0.0

    re = sum(math.cos(x) for x in steps) / len(steps)
    im = sum(math.sin(x) for x in steps) / len(steps)
    coherence = math.sqrt(re * re + im * im)
    winding_imbalance = abs(sum(steps)) / (2 * math.pi * len(steps))
    return coherence + winding_imbalance


def hamming_match_rate(a: str, b: str) -> float:
    n = min(len(a), len(b))
    return sum(1 for i in range(n) if a[i] == b[i]) / max(1, n)


def prefix_match_rate(a: str, b: str) -> float:
    n = min(len(a), len(b))
    k = 0
    for i in range(n):
        if a[i] == b[i]:
            k += 1
        else:
            break
    return k / max(1, n)


def witness_score(s: str, generator: Callable[[int], str]) -> float:
    """Hypothesis-test ship.

    Hamming match is robust to light noise. Prefix match rewards exact identity.
    """
    target = generator(len(s))
    return hamming_match_rate(s, target) + 0.25 * prefix_match_rate(s, target)


GENERIC_SHIPS: dict[str, Callable[[str], float]] = {
    "digit_frequency_ship": digit_frequency_ship,
    "compression_ship": compression_ship,
    "modular_cycle_ship": modular_cycle_ship,
    "prime_gap_ship": prime_gap_ship,
    "fourier_wave_ship": fourier_wave_ship,
    "arp_memory_ship": arp_memory_ship,
    "phase_lift_ship": phase_lift_ship,
}


def build_witness_ships(
    generator_library: dict[str, Callable[[int], str]],
) -> dict[str, Callable[[str], float]]:
    ships: dict[str, Callable[[str], float]] = {}
    for name, fn in generator_library.items():
        ships[f"witness_{name}"] = lambda s, fn=fn: witness_score(s, fn)
    return ships
