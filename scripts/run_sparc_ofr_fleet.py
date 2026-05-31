#!/usr/bin/env python3
"""
SPARC OFR-Gravity Fleet Runner

Runs real SPARC galaxy rotation-curve data through the OFR-Gravity witness fleet.

Data source:
https://astroweb.case.edu/SPARC/MassModels_Lelli2016c.mrt

Core equations:

Vbar^2 = |Vgas|Vgas + ups_disk Vdisk^2 + ups_bulge Vbul^2

R_g(r) = Vobs(r)^2/r - Vbar(r)^2/r

M_F(r) = r Vobs(r)^2/G - r Vbar(r)^2/G

Witnesses:
- baryon-only
- OFR direct residual
- pISO halo
- NFW halo
- Burkert halo
- MOND-like control
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import ssl
import urllib.request

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


G = 4.30091e-6  # kpc (km/s)^2 / Msun

# GitHub mirror used when primary URL is unreachable
_MIRROR_BASE = (
    "https://raw.githubusercontent.com/"
    "TerraSignum/emergent-gr-anisotropic-source-dm-de-repro/"
    "b9a4a0e1fd6440731afcc5f625ab406249237cd9/data/sparc/"
)
_MIRROR_ROTMOD = _MIRROR_BASE + "Rotmod_LTG/{galaxy}_rotmod.dat"


# -----------------------------
# Data loading
# -----------------------------

def _fetch(url: str, timeout: int = 90) -> bytes:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 OFR-Gravity-SPARC"},
    )
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
        return r.read()


def download_sparc_table(out_path: Path) -> Path:
    url = "https://astroweb.case.edu/SPARC/MassModels_Lelli2016c.mrt"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = _fetch(url)
        out_path.write_bytes(data)
        print(f"Downloaded from primary: {url}")
    except Exception as primary_err:
        print(f"Primary URL failed ({primary_err}); trying GitHub mirror ...")
        mirror_mrt = _MIRROR_BASE + "SPARC_Lelli2016c.mrt"
        data = _fetch(mirror_mrt)
        out_path.write_bytes(data)
        print(f"Downloaded from mirror: {mirror_mrt}")

    return out_path


def _build_combined_table(galaxy: str, out_path: Path) -> Path:
    """
    Fallback when neither MRT source has rotation curves for this galaxy.
    Downloads the per-galaxy *_rotmod.dat from the GitHub mirror and
    constructs a 10-column table that parse_sparc_mrt can read.
    """
    rotmod_url = _MIRROR_ROTMOD.format(galaxy=galaxy)
    raw = _fetch(rotmod_url).decode("utf-8", errors="replace")

    distance = None
    rows = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            if "Distance" in s:
                try:
                    distance = float(s.split("=")[1].split()[0])
                except (IndexError, ValueError):
                    pass
            continue
        cols = s.split()
        if len(cols) >= 8:
            rows.append(cols[:8])

    if distance is None or not rows:
        raise RuntimeError(
            f"Could not parse rotmod for {galaxy} from {rotmod_url}"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for cols in rows:
            f.write(f"{galaxy} {distance} " + " ".join(cols) + "\n")

    print(f"Built per-galaxy table: {out_path} ({len(rows)} rows)")
    return out_path


def parse_sparc_mrt(path: str | Path) -> pd.DataFrame:
    """
    Parses a combined SPARC rotation-curve table.

    Expected data rows (10 whitespace-separated columns):

        Galaxy  D_Mpc  Rad_kpc  Vobs  eVobs  Vgas  Vdisk  Vbul  SBdisk  SBbul
    """
    path = Path(path)
    rows = []

    for raw_line in path.read_text(errors="replace").splitlines():
        parts = raw_line.strip().split()

        if len(parts) != 10:
            continue

        try:
            rows.append({
                "Galaxy": parts[0],
                "D_Mpc": float(parts[1]),
                "Rad_kpc": float(parts[2]),
                "Vobs_kms": float(parts[3]),
                "eVobs_kms": float(parts[4]),
                "Vgas_kms": float(parts[5]),
                "Vdisk_kms": float(parts[6]),
                "Vbul_kms": float(parts[7]),
                "SBdisk": float(parts[8]),
                "SBbul": float(parts[9]),
            })
        except ValueError:
            continue

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError(f"No SPARC data rows parsed from {path}")

    return df


def select_galaxy(df: pd.DataFrame, galaxy: str) -> pd.DataFrame:
    names = df["Galaxy"].astype(str).str.strip()
    mask = names.str.lower() == galaxy.lower()

    if not mask.any():
        available = sorted(set(names))
        close = [
            name for name in available
            if galaxy.lower() in name.lower() or name.lower() in galaxy.lower()
        ]

        raise ValueError(
            f"Galaxy {galaxy!r} not found.\n"
            f"Close candidates: {close[:20]}\n"
            f"First available names: {available[:30]}"
        )

    return df[mask].copy().sort_values("Rad_kpc")


# -----------------------------
# Core math
# -----------------------------

def rmse(a, b) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return float(np.sqrt(np.mean((a - b) ** 2)))


def baryon_velocity(
    df: pd.DataFrame,
    ups_disk: float = 0.5,
    ups_bulge: float = 0.7,
) -> np.ndarray:
    """
    SPARC convention:

    Vbar^2 = |Vgas|Vgas + ups_disk Vdisk^2 + ups_bulge Vbul^2
    """
    vgas = df["Vgas_kms"].to_numpy(float)
    vdisk = df["Vdisk_kms"].to_numpy(float)
    vbul = df["Vbul_kms"].to_numpy(float)

    vbar2 = (
        np.abs(vgas) * vgas
        + ups_disk * vdisk ** 2
        + ups_bulge * vbul ** 2
    )

    return np.sqrt(np.maximum(0, vbar2))


def residual_coherence(residual: np.ndarray) -> float:
    s = np.sign(residual)
    s[s == 0] = 1

    if len(s) <= 1:
        return 0.0

    return float(np.mean(s[:-1] == s[1:]))


def outer_bias(radius: np.ndarray, residual: np.ndarray, split_frac: float = 0.45) -> float:
    split = np.quantile(radius, split_frac)
    inner = residual[radius < split]
    outer = residual[radius >= split]

    return float(np.mean(outer) - np.mean(inner))


# -----------------------------
# Halo witnesses
# -----------------------------

def piso_velocity(r, rho0, rc):
    """
    Pseudo-isothermal halo.

    V^2 = 4piG rho0 rc^2 [1 - rc/r atan(r/rc)]
    """
    r = np.asarray(r, dtype=float)

    return np.sqrt(
        np.maximum(
            0,
            4 * np.pi * G * rho0 * rc ** 2
            * (1 - (rc / r) * np.arctan(r / rc)),
        )
    )


def nfw_mass(r, rho_s, r_s):
    r = np.asarray(r, dtype=float)
    x = np.maximum(r / r_s, 1e-12)

    return 4 * np.pi * rho_s * r_s ** 3 * (
        np.log(1 + x) - x / (1 + x)
    )


def nfw_velocity(r, rho_s, r_s):
    return np.sqrt(np.maximum(0, G * nfw_mass(r, rho_s, r_s) / r))


def burkert_mass(r, rho0, r0):
    r = np.asarray(r, dtype=float)
    x = np.maximum(r / r0, 1e-12)

    bracket = np.log((1 + x) ** 2 * (1 + x * x)) - 2 * np.arctan(x)

    return np.pi * rho0 * r0 ** 3 * bracket


def burkert_velocity(r, rho0, r0):
    return np.sqrt(np.maximum(0, G * burkert_mass(r, rho0, r0) / r))


def mond_like_velocity(vbar, r, a0):
    """
    Simple MOND-like interpolation control.

    This is not a full MOND paper-grade fit.
    It is a witness/control model.
    """
    vbar = np.asarray(vbar, dtype=float)
    r = np.asarray(r, dtype=float)

    gN = vbar * vbar / r
    g = 0.5 * (gN + np.sqrt(gN * gN + 4 * gN * a0))

    return np.sqrt(g * r)


# -----------------------------
# Fit witnesses
# -----------------------------

def fit_grid_halo(
    r,
    vobs,
    vbar,
    model_name,
    velocity_fn,
    density_grid,
    scale_grid,
    density_key,
):
    best = None

    for density in density_grid:
        for scale in scale_grid:
            vh = velocity_fn(r, density, scale)
            pred = np.sqrt(np.maximum(0, vbar * vbar + vh * vh))
            e = rmse(vobs, pred)

            if best is None or e < best["rmse"]:
                best = {
                    "model": model_name,
                    "rmse": e,
                    density_key: float(density),
                    "scale_radius_kpc": float(scale),
                    "v_model": pred,
                    "v_halo": vh,
                }

    return best


def fit_piso(r, vobs, vbar):
    return fit_grid_halo(
        r,
        vobs,
        vbar,
        "pISO",
        piso_velocity,
        np.logspace(5.5, 10.5, 110),
        np.linspace(0.1, 50.0, 150),
        "rho0",
    )


def fit_nfw(r, vobs, vbar):
    return fit_grid_halo(
        r,
        vobs,
        vbar,
        "NFW",
        nfw_velocity,
        np.logspace(5.5, 10.8, 120),
        np.linspace(0.2, 80.0, 160),
        "rho_s",
    )


def fit_burkert(r, vobs, vbar):
    return fit_grid_halo(
        r,
        vobs,
        vbar,
        "Burkert",
        burkert_velocity,
        np.logspace(5.5, 10.8, 120),
        np.linspace(0.1, 80.0, 160),
        "rho0",
    )


def fit_mond(r, vobs, vbar):
    best = None

    for a0 in np.linspace(1, 10000, 420):
        pred = mond_like_velocity(vbar, r, a0)
        e = rmse(vobs, pred)

        if best is None or e < best["rmse"]:
            best = {
                "model": "MOND_like",
                "rmse": e,
                "a0_toy_units": float(a0),
                "v_model": pred,
            }

    return best


# -----------------------------
# Run one galaxy
# -----------------------------

def run_galaxy(
    galaxy_df: pd.DataFrame,
    output: Path,
    galaxy: str,
    ups_disk: float,
    ups_bulge: float,
) -> dict:
    output.mkdir(parents=True, exist_ok=True)

    r = galaxy_df["Rad_kpc"].to_numpy(float)
    vobs = galaxy_df["Vobs_kms"].to_numpy(float)
    evobs = galaxy_df["eVobs_kms"].to_numpy(float)

    vbar = baryon_velocity(galaxy_df, ups_disk, ups_bulge)

    mdyn = r * vobs * vobs / G
    mvis = r * vbar * vbar / G
    mf = mdyn - mvis

    rg = vobs * vobs / r - vbar * vbar / r
    discrepancy = vobs * vobs / np.maximum(vbar * vbar, 1e-12)

    v_ofr = np.sqrt(np.maximum(0, G * (mvis + np.maximum(0, mf)) / r))

    fits = [
        {
            "model": "baryon_only",
            "rmse": rmse(vobs, vbar),
            "v_model": vbar,
        },
        {
            "model": "OFR_direct_residual",
            "rmse": rmse(vobs, v_ofr),
            "v_model": v_ofr,
        },
        fit_piso(r, vobs, vbar),
        fit_nfw(r, vobs, vbar),
        fit_burkert(r, vobs, vbar),
        fit_mond(r, vobs, vbar),
    ]

    galaxy_slug = galaxy.replace(" ", "_")

    # Save SPARC rows
    galaxy_df.to_csv(output / f"{galaxy_slug}_sparc_rows.csv", index=False)

    # Save residual table
    residuals = galaxy_df.copy()
    residuals["Vbar_kms"] = vbar
    residuals["M_dyn_Msun"] = mdyn
    residuals["M_visible_Msun"] = mvis
    residuals["M_F_residual_Msun"] = mf
    residuals["M_F_residual_clamped_Msun"] = np.maximum(0, mf)
    residuals["R_g_kms2_per_kpc"] = rg
    residuals["mass_discrepancy_D"] = discrepancy

    for fit in fits:
        safe_name = fit["model"].replace("-", "_")
        residuals[f"V_{safe_name}_kms"] = fit["v_model"]

    residuals.to_csv(output / f"{galaxy_slug}_ofr_fleet_residuals.csv", index=False)

    # Model comparison table
    model_rows = []

    for fit in fits:
        row = {
            "model": fit["model"],
            "rmse_km_s": fit["rmse"],
        }

        for key in ["rho0", "rho_s", "scale_radius_kpc", "a0_toy_units"]:
            if key in fit:
                row[key] = fit[key]

        model_rows.append(row)

    model_df = pd.DataFrame(model_rows).sort_values("rmse_km_s")
    model_df.to_csv(output / f"{galaxy_slug}_model_witness_comparison.csv", index=False)

    non_ofr = model_df[model_df["model"] != "OFR_direct_residual"]

    summary = {
        "galaxy": galaxy,
        "rows_used": int(len(galaxy_df)),
        "radius_min_kpc": float(r.min()),
        "radius_max_kpc": float(r.max()),
        "ups_disk": ups_disk,
        "ups_bulge": ups_bulge,
        "best_non_OFR_model": non_ofr.iloc[0].to_dict(),
        "model_comparison": model_df.to_dict(orient="records"),
        "residual_positive_fraction": float(np.mean(mf > 0)),
        "residual_coherence_Rg": residual_coherence(rg),
        "outer_bias_Rg": outer_bias(r, rg),
        "mean_mass_discrepancy_D": float(np.mean(discrepancy)),
        "median_mass_discrepancy_D": float(np.median(discrepancy)),
        "mean_residual_mass_Msun": float(np.mean(np.maximum(0, mf))),
        "outer_mean_residual_mass_Msun": float(
            np.mean(np.maximum(0, mf)[r >= np.quantile(r, 0.45)])
        ),
    }

    summary_path = output / f"{galaxy_slug}_ofr_fleet_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Plots
    plt.figure(figsize=(10, 6))
    plt.errorbar(r, vobs, yerr=evobs, fmt="o", markersize=4, label="observed SPARC")

    for fit in fits:
        plt.plot(r, fit["v_model"], label=fit["model"])

    plt.xlabel("radius, kpc")
    plt.ylabel("velocity, km/s")
    plt.title(f"OFR witness fleet: {galaxy}")
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(output / f"{galaxy_slug}_model_witness_fits.png", dpi=180)
    plt.close()

    plt.figure(figsize=(9, 5))
    plt.bar(model_df["model"], model_df["rmse_km_s"])
    plt.ylabel("RMSE, km/s")
    plt.title(f"Witness RMSE comparison: {galaxy}")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(output / f"{galaxy_slug}_model_witness_rmse.png", dpi=180)
    plt.close()

    plt.figure(figsize=(9, 5))
    plt.plot(r, np.maximum(0, mf) / 1e10, marker="o", label="OFR residual mass")
    plt.xlabel("radius, kpc")
    plt.ylabel("residual mass, 1e10 Msun")
    plt.title(f"OFR residual mass profile: {galaxy}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output / f"{galaxy_slug}_ofr_residual_mass.png", dpi=180)
    plt.close()

    plt.figure(figsize=(9, 5))
    plt.plot(r, rg, marker="o", label="R_g")
    plt.axhline(0, linewidth=1)
    plt.xlabel("radius, kpc")
    plt.ylabel("residual acceleration, km^2/s^2/kpc")
    plt.title(f"OFR residual field: {galaxy}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output / f"{galaxy_slug}_ofr_residual_field.png", dpi=180)
    plt.close()

    print(json.dumps(summary, indent=2))

    return summary


# -----------------------------
# CLI
# -----------------------------

def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--galaxy", default="DDO154")
    parser.add_argument("--table", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--ups-disk", type=float, default=0.5)
    parser.add_argument("--ups-bulge", type=float, default=0.7)

    args = parser.parse_args()

    output = Path(args.output or f"runs/{args.galaxy}")
    output.mkdir(parents=True, exist_ok=True)

    if args.table:
        table_path = Path(args.table)
    else:
        table_path = Path("data/MassModels_Lelli2016c.mrt")

        if not table_path.exists():
            print("Downloading SPARC table...")
            download_sparc_table(table_path)

    df = parse_sparc_mrt(table_path)

    # If galaxy not found in combined file, fetch from per-galaxy mirror
    names = df["Galaxy"].astype(str).str.strip().str.lower()
    if not (names == args.galaxy.lower()).any():
        print(
            f"Galaxy {args.galaxy!r} not in {table_path}; "
            "fetching per-galaxy rotmod from mirror ..."
        )
        per_galaxy_path = Path(f"data/sparc/{args.galaxy}_rotmod_combined.mrt")
        _build_combined_table(args.galaxy, per_galaxy_path)
        df2 = parse_sparc_mrt(per_galaxy_path)
        df = pd.concat([df, df2], ignore_index=True)

    galaxy_df = select_galaxy(df, args.galaxy)

    run_galaxy(
        galaxy_df=galaxy_df,
        output=output,
        galaxy=args.galaxy,
        ups_disk=args.ups_disk,
        ups_bulge=args.ups_bulge,
    )


if __name__ == "__main__":
    main()
