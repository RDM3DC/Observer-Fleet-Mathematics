#!/usr/bin/env python3
"""
Mission 004: Framework Math Bridge

A conservative extension layer:
standard math result + observer clock + memory word + residual + stability.

Core clock: MOC-101
    s_k = 4*s_(k-1) + 3*s_(k-2) mod 101
    exact period = 10200 = 101^2 - 1

Run:
    python framework_math_bridge.py --verify-clock
"""

from __future__ import annotations
import argparse, cmath, json, math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple
import numpy as np


@dataclass
class FleetResult:
    value: Any
    memory_word: str
    residual: float
    stability: float
    observer_notes: List[str]
    metadata: Dict[str, Any]

    def to_dict(self):
        def c(x):
            if isinstance(x, np.ndarray): return x.tolist()
            if isinstance(x, (np.float32, np.float64)): return float(x)
            if isinstance(x, (np.int32, np.int64)): return int(x)
            if isinstance(x, complex): return {"real": x.real, "imag": x.imag}
            if isinstance(x, (list, tuple)): return [c(v) for v in x]
            if isinstance(x, dict): return {str(k): c(v) for k, v in x.items()}
            return x
        return c(asdict(self))


@dataclass
class ObserverClock:
    """Maximal Observer Clock: s_k = a*s_(k-1)+b*s_(k-2) mod modulus."""
    modulus: int = 101
    a: int = 4
    b: int = 3
    s0: int = 1
    s1: int = 1

    def step_state(self, state: Tuple[int, int]) -> Tuple[int, int]:
        cur, prev = state
        return (self.a * cur + self.b * prev) % self.modulus, cur

    def states(self, count: int):
        state = (self.s1 % self.modulus, self.s0 % self.modulus)
        out = []
        for _ in range(count):
            out.append(state)
            state = self.step_state(state)
        return out

    def scalars(self, count: int, centered: bool = True):
        vals = np.array([s[0] for s in self.states(count)], dtype=float)
        if not centered: return vals
        return 2.0 * (vals / (self.modulus - 1.0)) - 1.0

    def exact_period(self, max_steps: int | None = None) -> int:
        start = (self.s1 % self.modulus, self.s0 % self.modulus)
        state = start
        limit = max_steps or (self.modulus * self.modulus + 5)
        for k in range(1, limit + 1):
            state = self.step_state(state)
            if state == start:
                return k
        return -1

    def theoretical_max(self):
        return self.modulus * self.modulus - 1

    def verify_maximal(self):
        return self.exact_period(self.theoretical_max() + 5) == self.theoretical_max()


def memory_word_from_values(values, eps=1e-8):
    arr = np.array(values, dtype=float)
    if len(arr) < 2: return "S"
    diff = np.diff(arr)
    scale = np.std(arr) + eps
    symbols = []
    for chunk in np.array_split(diff, min(16, max(1, len(diff)))):
        if len(chunk) == 0: continue
        mean = float(np.mean(chunk))
        mx = float(np.max(np.abs(chunk)))
        if mx > 2.5 * scale: symbols.append("J")
        elif abs(mean) < 0.03 * scale: symbols.append("S")
        elif mean > 0: symbols.append("R+")
        elif mean < 0: symbols.append("R-")
        else: symbols.append("M")
    compact = []
    for s in symbols:
        if not compact or compact[-1] != s: compact.append(s)
    return " ".join(compact) if compact else "S"


def stability_from_spread(values, eps=1e-9):
    arr = np.array(values, dtype=float)
    spread = float(np.std(arr))
    level = float(np.mean(np.abs(arr))) + eps
    return float(1.0 / (1.0 + spread / level))


# ============================================================
# Standard math + framework layer
# ============================================================

def fleet_add(a: float, b: float, clock=None, observers=32):
    clock = clock or ObserverClock()
    value = a + b
    ticks = clock.scalars(observers)
    observed = [(a + 1e-9*t) + (b - 1e-9*t) for t in ticks]
    residual = float(max(abs(x - value) for x in observed))
    return FleetResult(
        value=value,
        memory_word=memory_word_from_values(observed),
        residual=residual,
        stability=1.0 if residual < 1e-8 else 1.0 / (1.0 + residual),
        observer_notes=["ordinary addition preserved", "observer perturbations cancel"],
        metadata={"operation": "add", "a": a, "b": b, "observers": observers},
    )


def fleet_quadratic_roots(a: float, b: float, c: float):
    if a == 0:
        if b == 0: raise ValueError("not quadratic or linear")
        roots = [-c / b]
    else:
        disc = b*b - 4*a*c
        sd = cmath.sqrt(disc)
        roots = [(-b + sd) / (2*a), (-b - sd) / (2*a)]
    residuals = [abs(a*r*r + b*r + c) for r in roots]
    residual = float(max(residuals))
    spread = [r.real for r in roots] + [r.imag for r in roots]
    return FleetResult(
        value=roots,
        memory_word="BR+ BR-" if len(roots) == 2 else "BR0",
        residual=residual,
        stability=float(1.0 / (1.0 + residual + np.std(spread))),
        observer_notes=["ordinary quadratic formula preserved", "branch split is retained as memory"],
        metadata={"operation": "quadratic_roots", "coefficients": [a, b, c], "discriminant": b*b - 4*a*c},
    )


def fleet_derivative(f: Callable[[float], float], x: float, h=1e-4, clock=None, observers=32):
    clock = clock or ObserverClock()
    estimates, hs = [], []
    for tick in clock.scalars(observers):
        hi = h * (1.0 + 0.35 * tick)
        if abs(hi) < 1e-12: hi = h
        hs.append(hi)
        estimates.append((f(x + hi) - f(x - hi)) / (2.0 * hi))
    return FleetResult(
        value=float(np.median(estimates)),
        memory_word=memory_word_from_values(estimates),
        residual=float(np.std(estimates)),
        stability=stability_from_spread(estimates),
        observer_notes=["central-difference derivative preserved", "MOC-101 varies step size"],
        metadata={"operation": "derivative", "x": x, "base_h": h, "median_h": float(np.median(hs))},
    )


def fleet_integral(f: Callable[[float], float], a: float, b: float, n=800, clock=None, observers=16):
    clock = clock or ObserverClock()
    estimates = []
    for tick in clock.scalars(observers):
        ni = max(20, int(n * (1.0 + 0.15 * tick)))
        xs = np.linspace(a, b, ni)
        ys = np.array([f(float(x)) for x in xs], dtype=float)
        estimates.append(float(np.trapezoid(ys, xs)))
    return FleetResult(
        value=float(np.median(estimates)),
        memory_word=memory_word_from_values(estimates),
        residual=float(np.std(estimates)),
        stability=stability_from_spread(estimates),
        observer_notes=["trapezoidal integration preserved", "sampling density is observer-varied"],
        metadata={"operation": "integral", "a": a, "b": b, "base_n": n},
    )


def fleet_eigen(matrix, clock=None, observers=24):
    clock = clock or ObserverClock()
    A = np.array(matrix, dtype=float)
    eig = np.linalg.eigvals(A)
    spectra = []
    for i, tick in enumerate(clock.scalars(observers)):
        P = np.zeros_like(A)
        r = i % A.shape[0]
        c = (i // A.shape[0]) % A.shape[1]
        P[r, c] = 1e-7 * tick
        spectra.append(np.sort_complex(np.linalg.eigvals(A + P)))
    spectra = np.array(spectra)
    residual = float(np.mean(np.std(np.abs(spectra), axis=0)))
    phases = np.angle(eig)
    return FleetResult(
        value=eig.tolist(),
        memory_word=memory_word_from_values(phases if len(phases) > 1 else [0.0, float(phases[0])]),
        residual=residual,
        stability=float(1.0 / (1.0 + residual * 1e7)),
        observer_notes=["ordinary eigenvalues preserved", "tiny clock perturbations test spectral stability"],
        metadata={"operation": "eigen", "shape": list(A.shape), "trace": float(np.trace(A)), "determinant": float(np.linalg.det(A))},
    )


def fleet_recurrence_period(modulus: int, coeffs: Tuple[int, int], seed_state=(1, 1)):
    a, b = coeffs
    cur, prev = seed_state[0] % modulus, seed_state[1] % modulus
    start = (cur, prev)
    seen, vals = set(), []
    period = -1
    for step in range(modulus * modulus + 5):
        if (cur, prev) in seen: break
        seen.add((cur, prev)); vals.append(cur)
        nxt = (a * cur + b * prev) % modulus
        prev, cur = cur, nxt
        if (cur, prev) == start:
            period = step + 1
            break
    theoretical = modulus * modulus - 1
    maximal = period == theoretical
    return FleetResult(
        value=period,
        memory_word="FULL-CYCLE" if maximal else memory_word_from_values(vals[:256]),
        residual=0.0 if period > 0 else 1.0,
        stability=1.0 if maximal else (float(period / theoretical) if period > 0 else 0.0),
        observer_notes=["recurrence period computed", "maximality checked against m^2 - 1"],
        metadata={"operation": "recurrence_period", "modulus": modulus, "coefficients": [a, b], "seed_state": list(seed_state), "theoretical_max": theoretical, "visited_states": len(seen), "maximal": maximal},
    )


def fleet_shortest_path(graph: Dict[str, Dict[str, float]], start: str, goal: str, clock=None, observers=24):
    clock = clock or ObserverClock()
    def dijkstra(weights):
        unvisited = set(weights.keys())
        dist = {n: math.inf for n in weights}
        prev = {n: None for n in weights}
        dist[start] = 0.0
        while unvisited:
            node = min(unvisited, key=lambda n: dist[n])
            unvisited.remove(node)
            if node == goal or math.isinf(dist[node]): break
            for nbr, w in weights[node].items():
                alt = dist[node] + float(w)
                if alt < dist.get(nbr, math.inf):
                    dist[nbr] = alt; prev[nbr] = node
        path, node = [], goal
        while node is not None:
            path.append(node); node = prev.get(node)
        path.reverse()
        return dist[goal], path
    base_dist, base_path = dijkstra(graph)
    edges = [(u, v) for u in graph for v in graph[u]]
    paths, dists = [], []
    for i, tick in enumerate(clock.scalars(observers)):
        G = {u: dict(vs) for u, vs in graph.items()}
        if edges:
            u, v = edges[i % len(edges)]
            G[u][v] = max(1e-9, G[u][v] * (1.0 + 0.05 * tick))
        d, p = dijkstra(G); dists.append(d); paths.append(p)
    same = sum(1 for p in paths if p == base_path) / max(1, len(paths))
    return FleetResult(
        value={"distance": base_dist, "path": base_path},
        memory_word="PATH-STABLE" if same > 0.8 else "PATH-SPLIT",
        residual=float(np.std(dists)),
        stability=float(0.5 * same + 0.5 * stability_from_spread(dists)),
        observer_notes=["ordinary shortest path preserved", "edge resistance is observer-varied"],
        metadata={"operation": "shortest_path", "start": start, "goal": goal, "same_path_fraction": same},
    )


def fleet_curve_fingerprint(points):
    P = np.array(points, dtype=float)
    if P.ndim != 2 or len(P) < 3: raise ValueError("points must be NxD, N>=3")
    dP = np.diff(P, axis=0)
    seg = np.linalg.norm(dP, axis=1)
    length = float(np.sum(seg))
    tangent = dP / (seg[:, None] + 1e-9)
    turn = np.linalg.norm(np.diff(tangent, axis=0), axis=1)
    residual = float(np.std(turn)) if len(turn) else 0.0
    return FleetResult(
        value={"length": length, "mean_turn": float(np.mean(turn)) if len(turn) else 0.0},
        memory_word=memory_word_from_values(turn),
        residual=residual,
        stability=float(1.0 / (1.0 + residual)),
        observer_notes=["ordinary curve length preserved", "turning pattern becomes a memory word"],
        metadata={"operation": "curve_fingerprint", "points": len(P), "dimension": int(P.shape[1]), "scar_fraction": float(np.mean(turn > np.percentile(turn, 85))) if len(turn) else 0.0},
    )


def run_demo(outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    clock = ObserverClock()
    results = {
        "clock_moc_101": fleet_recurrence_period(101, (4, 3), (1, 1)),
        "add": fleet_add(3, 5, clock),
        "quadratic": fleet_quadratic_roots(1, 0, -1),
        "derivative_sin_at_1": fleet_derivative(math.sin, 1.0, clock=clock),
        "integral_sin_0_pi": fleet_integral(math.sin, 0.0, math.pi, clock=clock),
        "eigen_rotation": fleet_eigen([[0, -1], [1, 0]], clock=clock),
        "shortest_path": fleet_shortest_path({"A": {"B": 1.0, "C": 2.2}, "B": {"C": 0.7, "D": 2.0}, "C": {"D": 0.8}, "D": {}}, "A", "D", clock=clock),
        "curve": fleet_curve_fingerprint([[math.cos(t), math.sin(t)] for t in np.linspace(0, 2 * math.pi, 160)]),
    }
    serial = {k: v.to_dict() for k, v in results.items()}
    (outdir / "mission_004_framework_math_bridge_results.json").write_text(json.dumps(serial, indent=2), encoding="utf-8")
    lines = ["# Mission 004: Framework Math Bridge Results", "", "Standard math result + Fleet/Phase-Memory layer.", ""]
    for name, r in results.items():
        d = r.to_dict()
        lines += [f"## {name}", "", f"- value: `{d['value']}`", f"- memory_word: `{r.memory_word}`", f"- residual: `{r.residual}`", f"- stability: `{r.stability}`", ""]
    (outdir / "mission_004_summary.md").write_text("\n".join(lines), encoding="utf-8")
    return serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="fleet_egatl_outputs/mission_004")
    parser.add_argument("--verify-clock", action="store_true")
    args = parser.parse_args()
    clock = ObserverClock()
    if args.verify_clock:
        print("MOC-101 exact period:", clock.exact_period())
        print("MOC-101 theoretical max:", clock.theoretical_max())
        print("MOC-101 verified maximal:", clock.verify_maximal())
    results = run_demo(Path(args.outdir))
    for name, r in results.items():
        print(f"\n{name}")
        print("value:", r["value"])
        print("memory_word:", r["memory_word"])
        print("stability:", r["stability"])
    print(f"\nWrote Mission 004 outputs to: {Path(args.outdir).resolve()}")


if __name__ == "__main__":
    main()
