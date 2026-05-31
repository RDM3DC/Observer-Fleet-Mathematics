#!/usr/bin/env python3
"""Mission 007: Cosmic Memory Beat.

This experiment does not claim that the universe has one literal pulse.
It builds a reproducible table of physical heartbeat analogues and maps them
into the Observer Fleet framework:

    Hubble expansion rhythm
    BAO fossil acoustic memory
    CMB thermal background hum
    Planck tick
    MOC observer heartbeat

Run:
    python experiments/cosmic_memory_beat.py --outdir results/cosmic_memory_beat
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List


SECONDS_PER_YEAR = 365.25 * 24 * 3600
MPC_KM = 3.0856775814913673e19

# Reproducible baseline constants / approximations.
# H0 is Planck-like; users can override it.
DEFAULT_H0_KM_S_MPC = 67.4
DEFAULT_AGE_GYR = 13.8
DEFAULT_BAO_MPC = 147.0
DEFAULT_CMB_T = 2.725
PLANCK_TIME_S = 5.391247e-44
K_B = 1.380649e-23
H_PLANCK = 6.62607015e-34
BLACKBODY_NU_PEAK_X = 2.821439


def hubble_s_inverse(h0_km_s_mpc: float) -> float:
    """Convert H0 from km/s/Mpc to s^-1."""

    return h0_km_s_mpc / MPC_KM


def cosmic_heartbeat_candidates(
    h0_km_s_mpc: float = DEFAULT_H0_KM_S_MPC,
    age_gyr: float = DEFAULT_AGE_GYR,
    bao_mpc: float = DEFAULT_BAO_MPC,
    cmb_temperature_k: float = DEFAULT_CMB_T,
    moc_modulus: int = 101,
) -> List[Dict[str, object]]:
    """Return candidate cosmic heartbeat layers."""

    h0_s = hubble_s_inverse(h0_km_s_mpc)
    hubble_time_s = 1.0 / h0_s
    hubble_time_gyr = hubble_time_s / SECONDS_PER_YEAR / 1e9

    age_s = age_gyr * 1e9 * SECONDS_PER_YEAR

    bao_light_cross_years = bao_mpc * 3.26156e6
    bao_light_cross_gyr = bao_light_cross_years / 1e9

    cmb_kt_h_hz = K_B * cmb_temperature_k / H_PLANCK
    cmb_peak_hz = BLACKBODY_NU_PEAK_X * cmb_kt_h_hz
    cmb_peak_ghz = cmb_peak_hz / 1e9
    cmb_peak_period_s = 1.0 / cmb_peak_hz

    universe_age_planck_ticks = age_s / PLANCK_TIME_S
    moc_period = moc_modulus * moc_modulus - 1

    return [
        {
            "candidate": "Expansion heartbeat",
            "physical_object": "Hubble expansion rate H(t), evaluated today as H0",
            "scale": f"{h0_s:.6e} s^-1",
            "period_or_size": f"{hubble_time_gyr:.6f} billion years",
            "framework_meaning": "present large-scale breathing rate of the universe",
            "score": 0.96,
            "seconds": hubble_time_s,
        },
        {
            "candidate": "Fossil acoustic heartbeat",
            "physical_object": "BAO sound horizon",
            "scale": f"{bao_mpc:.6f} Mpc comoving",
            "period_or_size": f"~{bao_light_cross_gyr:.6f} billion light-years light-crossing equivalent",
            "framework_meaning": "early-universe sound wave frozen into galaxy clustering",
            "score": 0.94,
            "seconds": bao_light_cross_years * SECONDS_PER_YEAR,
        },
        {
            "candidate": "Thermal background hum",
            "physical_object": "CMB blackbody field",
            "scale": f"{cmb_temperature_k:.6f} K",
            "period_or_size": f"peak ~{cmb_peak_ghz:.6f} GHz, period ~{cmb_peak_period_s:.6e} s",
            "framework_meaning": "relic radiation hum filling the observable universe",
            "score": 0.88,
            "seconds": cmb_peak_period_s,
        },
        {
            "candidate": "Planck tick",
            "physical_object": "Planck time",
            "scale": f"{PLANCK_TIME_S:.6e} s",
            "period_or_size": f"age of universe ~{universe_age_planck_ticks:.6e} Planck ticks",
            "framework_meaning": "smallest natural tick scale; not directly observed as a cosmic beat",
            "score": 0.72,
            "seconds": PLANCK_TIME_S,
        },
        {
            "candidate": "Observer Fleet heartbeat",
            "physical_object": f"MOC-{moc_modulus}",
            "scale": f"mod {moc_modulus} second-order recurrence",
            "period_or_size": f"{moc_period} observer states",
            "framework_meaning": "deterministic full-cycle observer-state engine for scanning cosmic data",
            "score": 0.90,
            "seconds": None,
        },
    ]


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, rows: List[Dict[str, object]]) -> None:
    top = max(rows, key=lambda row: float(row["score"]))
    report = [
        "# Mission 007: Cosmic Memory Beat",
        "",
        "This is not a claim that the universe has one literal pulse.",
        "It is a reproducible framework mapping of physical heartbeat analogues.",
        "",
        "## Best candidate",
        "",
        f"Top layer: **{top['candidate']}**",
        "",
        "The strongest framework answer is:",
        "",
        "```text",
        "Cosmic Memory Beat = Hubble expansion rhythm + BAO fossil acoustic memory + CMB background hum",
        "```",
        "",
        "## Candidate formula",
        "",
        "```text",
        "U_beat = (H(t), r_BAO, T_CMB, Phi_MOC)",
        "```",
        "",
        "Where:",
        "",
        "```text",
        "H(t)    = expansion clock",
        "r_BAO   = fossil acoustic memory ruler",
        "T_CMB   = thermal background hum",
        "Phi_MOC = observer-clock phase used by the Fleet",
        "```",
        "",
        "## Candidate layers",
        "",
    ]
    for row in rows:
        report += [
            f"### {row['candidate']}",
            "",
            f"- physical object: {row['physical_object']}",
            f"- scale: `{row['scale']}`",
            f"- period/size: `{row['period_or_size']}`",
            f"- framework meaning: {row['framework_meaning']}",
            f"- score: `{row['score']}`",
            "",
        ]
    report += [
        "## Research status",
        "",
        "The physical pieces are standard cosmology. The framework contribution is the interpretation:",
        "",
        "```text",
        "expansion rhythm -> fossil acoustic memory -> observer-clock scan",
        "```",
        "",
        "The next step is to scan public cosmology datasets with MOC observer states and test whether BAO/CMB/large-scale-structure residuals produce stable Fleet memory words.",
    ]
    path.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="results/cosmic_memory_beat")
    parser.add_argument("--h0", type=float, default=DEFAULT_H0_KM_S_MPC)
    parser.add_argument("--age-gyr", type=float, default=DEFAULT_AGE_GYR)
    parser.add_argument("--bao-mpc", type=float, default=DEFAULT_BAO_MPC)
    parser.add_argument("--cmb-k", type=float, default=DEFAULT_CMB_T)
    parser.add_argument("--moc-modulus", type=int, default=101)
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rows = cosmic_heartbeat_candidates(
        h0_km_s_mpc=args.h0,
        age_gyr=args.age_gyr,
        bao_mpc=args.bao_mpc,
        cmb_temperature_k=args.cmb_k,
        moc_modulus=args.moc_modulus,
    )

    write_csv(outdir / "cosmic_memory_beat_candidates.csv", rows)
    (outdir / "cosmic_memory_beat_candidates.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    write_report(outdir / "cosmic_memory_beat_report.md", rows)

    print("Cosmic Memory Beat candidates")
    for row in rows:
        print(f"- {row['candidate']}: {row['period_or_size']} | score={row['score']}")
    print(f"\nWrote results to: {outdir.resolve()}")


if __name__ == "__main__":
    main()
