# Fleet Validation Benchmark

This benchmark replaces hand-selected classification cutoffs with thresholds learned from independent data splits.

## Design

For every horizon, the benchmark uses separate seeds for:

1. random-control calibration,
2. random-only generic-threshold training,
3. structured-decoy witness-threshold training,
4. held-out random testing,
5. held-out structured testing, and
6. known-witness testing with exact and lightly mutated sequences.

`fast` mode is intended for development. `full` mode evaluates horizons of 300, 600, and 1,200 digits using 250 calibration controls, 250 threshold controls, and 500 held-out random controls at each horizon. That is 3,000 independent random controls across the three split roles and horizons.

Run:

```bash
python -m pip install -e ".[dev]"
python benchmarks/fleet_validation.py --mode fast
python benchmarks/fleet_validation.py --mode full
```

## Full benchmark result

Seed: `7919`

| Horizon | Strict random FPR | Alert incl. borderline | Structured correct | False witness on unknown | Witness recall | Exact witness ID | Mean abs. ship correlation |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 300 | 0.016 | 0.056 | 0.958 | 0.000 | 1.000 | 1.000 | 0.483 |
| 600 | 0.000 | 0.014 | 1.000 | 0.000 | 1.000 | 1.000 | 0.482 |
| 1200 | 0.004 | 0.014 | 1.000 | 0.000 | 1.000 | 1.000 | 0.467 |

Strict false positives include only high-confidence `structured unknown` or `witness-confirmed` decisions. Borderline alerts are reported separately.

The initial benchmark version exposed false witness confirmations on structured binary automatic sequences. Witness thresholds were therefore retrained against separate structured decoys. The held-out structured families remain distinct from those decoy families, and the final benchmark recorded zero false witness confirmations on the held-out set.

## Interpretation

These results validate the implementation on this benchmark suite; they do not establish a universal theorem or prove hidden structure in any constant. The benchmark should expand over time with adversarial generators, alternate random sources, more horizons, preregistered test sets, and comparison against standard sequence-classification baselines.
