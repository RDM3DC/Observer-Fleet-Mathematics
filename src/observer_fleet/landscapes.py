"""Mathematical landscape generators for Observer Fleet Mathematics."""

from __future__ import annotations

import math
import random
from typing import Callable

import mpmath as mp


def decimal_digits_of(value: object, n: int) -> str:
    """Return n decimal digits after the decimal point."""
    mp.mp.dps = max(n + 50, 80)
    s = str(value)
    if "." not in s:
        raise ValueError("value does not have a decimal point representation")
    return s.split(".", 1)[1][:n]


def pi_digits(n: int = 2500) -> str:
    mp.mp.dps = n + 50
    return decimal_digits_of(mp.pi, n)


def e_digits(n: int = 2500) -> str:
    mp.mp.dps = n + 50
    return decimal_digits_of(mp.e, n)


def sqrt2_digits(n: int = 2500) -> str:
    mp.mp.dps = n + 50
    return decimal_digits_of(mp.sqrt(2), n)


def random_digits(n: int = 2500, seed: int = 0) -> str:
    rng = random.Random(seed)
    return "".join(str(rng.randrange(10)) for _ in range(n))


def mutate_digits(s: str, rate: float = 0.02, seed: int = 0) -> str:
    rng = random.Random(seed)
    out: list[str] = []
    for ch in s:
        if rng.random() < rate:
            choices = [str(d) for d in range(10) if str(d) != ch]
            out.append(rng.choice(choices))
        else:
            out.append(ch)
    return "".join(out)


def champernowne_digits(n: int = 2500) -> str:
    s, k = "", 1
    while len(s) < n:
        s += str(k)
        k += 1
    return s[:n]


def is_prime(k: int) -> bool:
    if k < 2:
        return False
    if k == 2:
        return True
    if k % 2 == 0:
        return False
    r = int(math.sqrt(k))
    for j in range(3, r + 1, 2):
        if k % j == 0:
            return False
    return True


def prime_digits(n: int = 2500) -> str:
    s, k = "", 2
    while len(s) < n:
        if is_prime(k):
            s += str(k)
        k += 1
    return s[:n]


def repeating_cycle(n: int = 2500, cycle: str = "0123456789") -> str:
    if not cycle:
        raise ValueError("cycle must be non-empty")
    return (cycle * ((n // len(cycle)) + 1))[:n]


def thue_morse_digits(n: int = 2500) -> str:
    return "".join(str(bin(i).count("1") % 2) for i in range(n))


def square_digits(n: int = 2500) -> str:
    s, k = "", 1
    while len(s) < n:
        s += str(k * k)
        k += 1
    return s[:n]


def fibonacci_digits(n: int = 2500) -> str:
    s = ""
    a, b = 1, 1
    while len(s) < n:
        s += str(a)
        a, b = b, a + b
    return s[:n]


GENERATOR_LIBRARY: dict[str, Callable[[int], str]] = {
    "repeating_0123456789": lambda n: repeating_cycle(n, "0123456789"),
    "champernowne": champernowne_digits,
    "prime_digits": prime_digits,
    "thue_morse": thue_morse_digits,
    "square_digits": square_digits,
    "fibonacci_digits": fibonacci_digits,
}
