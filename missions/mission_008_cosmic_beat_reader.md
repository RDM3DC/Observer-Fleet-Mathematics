# Mission 008: Cosmic Beat Reader

Mission 008 locks the first concrete input schema and fingerprint output for reading the nested cosmic beat.

## Input layers

The reader accepts one JSON object with three required data layers:

```text
H(z) expansion layer
BAO fossil-memory layer
mock/public CMB angular-spectrum layer
```

Schema file:

```text
schemas/cosmic_beat_reader.schema.json
```

## Input shape

```json
{
  "metadata": {
    "name": "synthetic_cosmic_memory_beat_v1",
    "source": "generated or public dataset name",
    "units": {
      "hz_x": "redshift z",
      "hz_y": "km/s/Mpc",
      "bao_x": "Mpc",
      "bao_y": "correlation amplitude",
      "cmb_x": "multipole ell",
      "cmb_y": "C_ell or normalized C_ell"
    }
  },
  "clock": {
    "modulus": 101,
    "a": 4,
    "b": 3,
    "seed": [1, 1],
    "sample_count": 256
  },
  "hz": [
    {"z": 0.1, "H": 70.0, "sigma": 1.0, "model_H": 69.5}
  ],
  "bao": [
    {"r": 147.0, "xi": 0.04, "sigma": 0.003, "model_xi": 0.01}
  ],
  "cmb": [
    {"ell": 220, "cl": 0.0001, "sigma": 0.000001, "model_cl": 0.000099}
  ]
}
```

## Output shape

The reader returns:

```text
CosmicBeatFingerprint.v1
```

Main fields:

```text
source_name
clock
layers
cross_layer_alignment
overall_stability_score
cosmic_memory_word
interpretation
status
```

Each layer contains:

```text
layer
global_memory_word
observer_consensus_word
observer_consensus_fraction
residual_energy
observer_energy_mean
observer_energy_std
observer_sign_mean
stability_score
observer_words_sample
```

## Reader algorithm

```text
1. Load H(z), BAO, and CMB-like layers.
2. Compute residuals against supplied model columns.
3. Generate Phi_MOC observer ticks.
4. For each tick, choose a phase/window over each layer.
5. Write local observer memory words.
6. Compress each layer into a global memory word.
7. Compare layer words for cross-layer alignment.
8. Emit CosmicBeatFingerprint.v1.
```

## Run synthetic data

```bash
python experiments/cosmic_beat_reader.py --outdir results/cosmic_beat_reader
```

Outputs:

```text
cosmic_beat_input.synthetic.json
cosmic_beat_fingerprint.v1.json
cosmic_beat_reader_summary.md
```

## Mission status

This locks the first concrete schema and output. The next step is public-data adapters:

```text
H(z) chronometer / BAO tables
BAO correlation or distance-ratio data
CMB angular power spectrum table
```

Until then, the synthetic mode provides a repeatable testbed for the Cosmic Beat Reader pipeline.
