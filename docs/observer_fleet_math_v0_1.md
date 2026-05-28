# Observer Fleet Mathematics v0.1

## Core definition

A landscape is an infinite or finite mathematical object `X` that can be observed along a trajectory.

An observer ship is a tuple:

```text
O = (S, s0, phi, U, rho)
```

where:

- `S` is the memory-state space.
- `s0` is the initial memory.
- `phi` is the observation map.
- `U` is the memory-update rule.
- `rho` is the return map.

Given a trajectory `tau` through `X`, the observer evolves by:

```text
s_{t+1} = U(s_t, phi(X, tau_t))
```

After `N` steps, the observer returns:

```text
R_O,N(X) = rho(s_N)
```

An observer fleet is a finite set:

```text
F = {O_1, O_2, ..., O_k}
```

The fleet fingerprint of `X` is:

```text
Phi_F,N(X) = (R_O1,N(X), R_O2,N(X), ..., R_Ok,N(X))
```

With random controls `B_N`, define the calibrated z-fingerprint:

```text
Z_F,N(X)_i = (R_Oi,N(X) - mean_B(R_Oi,N)) / std_B(R_Oi,N)
```

Classification is observer-relative:

```text
C_F,N(X) = classify(Z_F,N(X))
```

## Motto

pi has no end, but every observer has a horizon.

Observer Fleet Mathematics studies what returns from that horizon.

## Honest scope

This does not prove hidden messages in pi.

It creates a repeatable way to compare mathematical objects by memory-bearing observer returns.
