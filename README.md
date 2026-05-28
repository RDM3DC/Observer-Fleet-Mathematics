# Observer Fleet Mathematics

**Send ships into infinity. Classify what returns.**

Observer Fleet Mathematics is an experimental framework for studying mathematical landscapes using memory-bearing observer fleets.

Instead of asking only:

> What is this object?

we ask:

> What do different observers return after traveling through it?

A landscape may be a digit stream, number sequence, symbolic system, geometric object, graph, field, or other mathematical structure. An observer ship travels through the landscape, updates memory, and returns a signal. A fleet of such ships produces a fingerprint.

## Core idea

An observer ship is defined as:

```text
O = (S, s0, phi, U, rho)
```

where:

```text
S   = memory-state space
s0  = initial memory
phi = observation map
U   = memory update rule
rho = return/report map
```

The observer evolves by:

```text
s_{t+1} = U(s_t, phi(X, tau_t))
```

After N steps, the observer returns:

```text
R_O,N(X) = rho(s_N)
```

A fleet is:

```text
F = {O1, O2, ..., Ok}
```

The fleet fingerprint is:

```text
Phi_F,N(X) = (R1, R2, ..., Rk)
```

## Motto

**pi has no end, but every observer has a horizon.**

Observer Fleet Mathematics studies what returns from that horizon.

## Honest scope

This project does **not** claim that pi contains a hidden message.

The first missions showed the opposite: pi, e, and sqrt(2) behaved random-like to the current fleet at short horizons.

The stronger claim is methodological:

> Mathematical landscapes can be compared by calibrated observer-return fingerprints.

The fleet separates constructed streams such as Champernowne digits, prime digits, Thue-Morse, repeating cycles, and square digits from random controls, while keeping random-like constants random-like.

## Two layers of the fleet

### Explorer ships

Explorer ships do not know the exact generator. They search for broad structure:

- digit-frequency imbalance
- compression
- modular recurrence
- prime-digit gap anomalies
- Fourier/wave coherence
- ARP adaptive memory
- Phase-Lift step coherence

### Witness ships

Witness ships test a named hypothesis:

> Does this landscape match this proposed generator?

Generic ships explore. Witness ships testify.

## Quick start

```bash
python -m pip install -e .
python examples/blind_navigation_demo.py
```

Expected behavior:

```text
Mystery_A -> witness-confirmed: fibonacci_digits
Mystery_B -> random-like / no known witness
Mystery_C -> witness-confirmed: prime_digits
Mystery_D -> random-like / no known witness
Mystery_E -> structured unknown / no exact witness
```

## Install

```bash
git clone https://github.com/RDM3DC/Observer-Fleet-Mathematics.git
cd Observer-Fleet-Mathematics
python -m pip install -e .
```

## Project status

Experimental mathematics prototype.

The code is intended for exploration, hypothesis testing, and reproducible demonstrations. It is not a proof of hidden structure in any specific constant.
