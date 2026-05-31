# Mission 006: MOC Density Theorem + Fleet Clock Engine

Mission 006 makes the clock front operational.

The key move is to separate the standard finite-field theorem from the framework interpretation:

```text
standard math:
primitive second-order recurrences over F_p

framework interpretation:
maximal observer clocks that traverse every nonzero phase-memory state
```

## MOC Density Theorem

For an odd prime `p`, consider the recurrence:

```text
s_k = a*s_(k-1) + b*s_(k-2) mod p
```

with state:

```text
(s_k, s_(k-1))
```

The all-zero state is trapped, so the maximum possible nonzero period is:

```text
p^2 - 1
```

The recurrence is maximal exactly when its characteristic polynomial

```text
x^2 - a*x - b
```

is primitive over `F_p`.

The number of degree-2 primitive polynomials over `F_p` is:

```text
phi(p^2 - 1) / 2
```

So the number of second-order maximal observer clocks is:

```text
MOC_count(p) = phi(p^2 - 1) / 2
```

## Canonical example: MOC-101

```text
s_k = 4*s_(k-1) + 3*s_(k-2) mod 101
```

Verified:

```text
period = 10200
theoretical max = 101^2 - 1 = 10200
maximal = true
```

## Fleet Clock Engine

The code surface is:

```python
from observer_fleet.fleet_clock_engine import default_moc_101

clock = default_moc_101()
clock.period()
clock.is_maximal()
clock.sample(16)
clock.observer_weights(16)
clock.phase_offsets(16)
clock.memory_word(64)
```

The Fleet Clock Engine turns a recurrence state into observer metadata:

```text
index
state = (s_k, s_(k-1))
phase in [0, 1)
centered scalar in [-1, 1]
parity bit
```

## Framework meaning

MOC clocks provide a deterministic full-cycle observer-state generator.

This gives the Fleet a clean heartbeat:

```text
MOC clocks
→ observer paths
→ Phase-Lifted evaluations
→ memory words
→ stability/separation tests
```

## Research status

The density theorem is standard finite-field mathematics reframed for the Observer Fleet project.

The framework contribution is the operational interpretation:

```text
primitive recurrence = full-cycle observer clock
```

and its use as the default scanning engine for Fleet-EGATL missions.
