"""Fleet Clock Engine.

Mission 006 turns maximal observer clocks into reusable observer-state
generators for Fleet missions.

The default example is MOC-101:

    s_k = 4*s_(k-1) + 3*s_(k-2) mod 101

with period 101^2 - 1 = 10200.

This module intentionally keeps the standard finite-field result separate
from the framework interpretation:

    primitive second-order recurrence
    -> full-cycle observer-state generator
    -> Fleet clock engine
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Sequence, Tuple


State = Tuple[int, int]


@dataclass(frozen=True)
class FleetClockTick:
    """One observer-clock tick.

    Attributes
    ----------
    index:
        Zero-based tick index.
    state:
        Pair ``(s_k, s_(k-1))``.
    phase:
        Normalized phase in ``[0, 1)`` based on the tick index.
    centered:
        Centered scalar in roughly ``[-1, 1]`` from the current state.
    parity:
        State parity bit useful for branch/memory tests.
    """

    index: int
    state: State
    phase: float
    centered: float
    parity: int


@dataclass(frozen=True)
class FleetClockEngine:
    """Second-order modular clock used as a Fleet observer engine."""

    modulus: int = 101
    a: int = 4
    b: int = 3
    seed: State = (1, 1)

    @property
    def theoretical_max_period(self) -> int:
        """Maximum possible period outside the trapped zero state."""

        return self.modulus * self.modulus - 1

    def step(self, state: State) -> State:
        """Advance one recurrence state."""

        cur, prev = state
        return ((self.a * cur + self.b * prev) % self.modulus, cur % self.modulus)

    def period(self, limit: int | None = None) -> int:
        """Return the period of the seeded recurrence, or ``-1`` if not found."""

        start = (self.seed[0] % self.modulus, self.seed[1] % self.modulus)
        state = start
        max_steps = limit or (self.theoretical_max_period + 5)
        for k in range(1, max_steps + 1):
            state = self.step(state)
            if state == start:
                return k
        return -1

    def is_maximal(self) -> bool:
        """Whether this clock reaches the full nonzero state period."""

        return self.period(self.theoretical_max_period + 5) == self.theoretical_max_period

    def states(self, count: int | None = None) -> Iterator[State]:
        """Yield recurrence states.

        If ``count`` is omitted, yields one full theoretical cycle.
        """

        total = self.theoretical_max_period if count is None else count
        state = (self.seed[0] % self.modulus, self.seed[1] % self.modulus)
        for _ in range(total):
            yield state
            state = self.step(state)

    def ticks(self, count: int | None = None) -> Iterator[FleetClockTick]:
        """Yield normalized observer ticks for Fleet missions."""

        total = self.theoretical_max_period if count is None else count
        denom = max(1, self.modulus - 1)
        for i, state in enumerate(self.states(total)):
            cur, prev = state
            yield FleetClockTick(
                index=i,
                state=state,
                phase=(i % self.theoretical_max_period) / self.theoretical_max_period,
                centered=2.0 * (cur / denom) - 1.0,
                parity=(cur + prev) % 2,
            )

    def sample(self, count: int) -> List[FleetClockTick]:
        """Return the first ``count`` ticks as a list."""

        return list(self.ticks(count))

    def observer_weights(self, count: int, amplitude: float = 1.0) -> List[float]:
        """Return centered observer weights from the clock state."""

        return [amplitude * tick.centered for tick in self.ticks(count)]

    def phase_offsets(self, count: int, turns: float = 1.0) -> List[float]:
        """Return phase offsets in radians from clock phase."""

        tau = 6.283185307179586
        return [tau * turns * tick.phase for tick in self.ticks(count)]

    def memory_word(self, count: int = 64) -> str:
        """Compress the first ``count`` clock movements into a memory word."""

        vals = [tick.centered for tick in self.ticks(count)]
        if len(vals) < 2:
            return "S"
        symbols: List[str] = []
        for prev, cur in zip(vals, vals[1:]):
            delta = cur - prev
            if abs(delta) < 1e-12:
                symbols.append("S")
            elif delta > 0:
                symbols.append("R+")
            else:
                symbols.append("R-")
        compact: List[str] = []
        for symbol in symbols:
            if not compact or compact[-1] != symbol:
                compact.append(symbol)
        return " ".join(compact)


def default_moc_101() -> FleetClockEngine:
    """Return the canonical MOC-101 engine."""

    return FleetClockEngine(modulus=101, a=4, b=3, seed=(1, 1))


def make_clock(modulus: int, a: int, b: int, seed: State = (1, 1)) -> FleetClockEngine:
    """Construct a Fleet clock engine."""

    return FleetClockEngine(modulus=modulus, a=a, b=b, seed=seed)


def clock_summary(clock: FleetClockEngine) -> dict:
    """Serializable summary for reports and experiments."""

    period = clock.period()
    return {
        "modulus": clock.modulus,
        "a": clock.a,
        "b": clock.b,
        "seed": list(clock.seed),
        "period": period,
        "theoretical_max_period": clock.theoretical_max_period,
        "maximal": period == clock.theoretical_max_period,
        "sample_memory_word": clock.memory_word(64),
    }
