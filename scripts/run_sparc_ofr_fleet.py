"""
run_sparc_ofr_fleet.py  –  OFR-Gravity SPARC Real-Data Analysis
================================================================
Fits baryon-only, OFR direct residual, pISO, NFW, Burkert, and MOND
models to SPARC rotation curves.

Data source: Lelli et al. 2016, AJ 152, 157
  (individual *_rotmod.dat files from the SPARC database)

Columns in *_rotmod.dat (header lines start with #):
  Rad(kpc)  Vobs(km/s)  errV(km/s)  Vgas(km/s)  Vdisk(km/s)  Vbul(km/s)
  SBdisk(L/pc^2)  SBbul(L/pc^2)
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.optimize import minimize_scalar, minimize


# ── Physical constants ──────────────────────────────────────────────────────
G_kpc = 4.302e-6           # kpc (km/s)^2 / M_sun   (Newton's constant)
G_A0 = 1.2e-10             # m s^-2  (MOND acceleration scale)
# Convert G_A0 to (km/s)^2 kpc^-1 :  1 (km/s)^2/kpc = 3.241e-14 m/s^2
A0_KPC = G_A0 / 3.241e-14  # ≈ 3703 (km/s)^2 kpc^-1

# Default fiducial mass-to-light ratios (3.6 µm band, Schombert & McGaugh 2014)
UPSILON_DISK_FID = 0.50    # M_sun / L_sun at 3.6 µm, stellar disk
UPSILON_BUL_FID  = 0.70    # M_sun / L_sun at 3.6 µm, bulge


# ── Data loading ────────────────────────────────────────────────────────────
@dataclass
class GalaxyData:
    name: str
    distance_mpc: float
    R: np.ndarray       # kpc
    Vobs: np.ndarray    # km/s
    errV: np.ndarray    # km/s
    Vgas: np.ndarray    # km/s  (signed – can be negative for ring kinematics)
    Vdisk: np.ndarray   # km/s  (ϒ=1 units)
    Vbul: np.ndarray    # km/s  (ϒ=1 units)
    SBdisk: np.ndarray  # L_sun/pc^2
    SBbul: np.ndarray   # L_sun/pc^2


def load_rotmod(filepath: str, galaxy_name: str) -> GalaxyData:
    """Parse a SPARC *_rotmod.dat file."""
    distance = None
    rows = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                if "Distance" in line:
                    # e.g.  "# Distance = 4.04 Mpc"
                    parts = line.split("=")
                    if len(parts) >= 2:
                        distance = float(parts[1].split()[0])
                continue
            vals = line.split()
            if len(vals) >= 8:
                rows.append([float(v) for v in vals[:8]])

    if distance is None:
        raise ValueError(f"Could not parse distance from {filepath}")
    if not rows:
        raise ValueError(f"No data rows found in {filepath}")

    arr = np.array(rows)
    return GalaxyData(
        name=galaxy_name,
        distance_mpc=distance,
        R=arr[:, 0],
        Vobs=arr[:, 1],
        errV=arr[:, 2],
        Vgas=arr[:, 3],
        Vdisk=arr[:, 4],
        Vbul=arr[:, 5],
        SBdisk=arr[:, 6],
        SBbul=arr[:, 7],
    )


# ── Baryonic velocity ────────────────────────────────────────────────────────
def vbar(gd: GalaxyData,
         upsilon_disk: float = UPSILON_DISK_FID,
         upsilon_bul: float = UPSILON_BUL_FID) -> np.ndarray:
    """
    Total baryonic circular velocity (km/s).
    SPARC convention: gas contribution is signed (Vgas * |Vgas|) to allow
    negative gas rings; disk/bulge always additive.
    """
    vbar_sq = (np.sign(gd.Vgas) * gd.Vgas**2
               + upsilon_disk * gd.Vdisk**2
               + upsilon_bul  * gd.Vbul**2)
    # Clamp numerical noise: V_bar^2 must be ≥ 0
    vbar_sq = np.maximum(vbar_sq, 0.0)
    return np.sqrt(vbar_sq)


# ── Dark-matter halo profiles ────────────────────────────────────────────────
def vdm_pISO(R: np.ndarray, rho0: float, rc: float) -> np.ndarray:
    """Pseudo-isothermal halo circular speed (km/s)."""
    v2 = 4.0 * math.pi * G_kpc * rho0 * rc**2 * (1.0 - (rc / R) * np.arctan(R / rc))
    return np.sqrt(np.maximum(v2, 0.0))


def vdm_NFW(R: np.ndarray, rho_s: float, r_s: float) -> np.ndarray:
    """NFW halo circular speed (km/s)."""
    x = R / r_s
    # V^2 = 4πG ρ_s r_s^3 / r * [ln(1+x) - x/(1+x)]
    v2 = (4.0 * math.pi * G_kpc * rho_s * r_s**3 / R
          * (np.log(1.0 + x) - x / (1.0 + x)))
    return np.sqrt(np.maximum(v2, 0.0))


def vdm_Burkert(R: np.ndarray, rho0: float, r_s: float) -> np.ndarray:
    """
    Burkert (1995) halo circular speed (km/s).
    M(<r) = π ρ0 r_s^3 [2 ln(1+r/r_s) + ln(1+(r/r_s)^2) - 2 arctan(r/r_s)]
    """
    x = R / r_s
    mass = (math.pi * rho0 * r_s**3
            * (2.0 * np.log(1.0 + x)
               + np.log(1.0 + x**2)
               - 2.0 * np.arctan(x)))
    v2 = G_kpc * mass / R
    return np.sqrt(np.maximum(v2, 0.0))


def vtot(Vbar: np.ndarray, Vdm: np.ndarray) -> np.ndarray:
    """Quadrature sum of baryon and dark-matter velocities."""
    return np.sqrt(Vbar**2 + Vdm**2)


# ── MOND (McGaugh et al. 2016 Radial Acceleration Relation) ─────────────────
def vmond(gd: GalaxyData,
          upsilon_disk: float = UPSILON_DISK_FID,
          upsilon_bul: float = UPSILON_BUL_FID) -> np.ndarray:
    """
    MOND prediction using the empirical RAR interpolation function
      g_obs = g_bar / (1 – exp(–√(g_bar / g†)))
    where g† = 1.2×10^{-10} m s^{-2} ≈ 3703 (km/s)^2 kpc^{-1}.
    """
    Vb = vbar(gd, upsilon_disk, upsilon_bul)
    g_bar = Vb**2 / np.maximum(gd.R, 1e-6)   # (km/s)^2 / kpc
    xi = np.sqrt(np.maximum(g_bar / A0_KPC, 1e-30))
    nu = 1.0 / (1.0 - np.exp(-xi))
    g_obs = g_bar * nu
    v2 = g_obs * gd.R
    return np.sqrt(np.maximum(v2, 0.0))


# ── RMSE ────────────────────────────────────────────────────────────────────
def rmse(Vmodel: np.ndarray, Vobs: np.ndarray,
         weights: np.ndarray | None = None) -> float:
    """Root-mean-square error (error-weighted if weights given)."""
    resid = Vmodel - Vobs
    if weights is not None:
        return float(np.sqrt(np.average(resid**2, weights=weights)))
    return float(np.sqrt(np.mean(resid**2)))


def chi2_red(Vmodel: np.ndarray, gd: GalaxyData, n_free: int) -> float:
    resid = Vmodel - gd.Vobs
    n = len(resid)
    dof = max(n - n_free, 1)
    return float(np.sum((resid / gd.errV) ** 2) / dof)


# ── Model fitters ────────────────────────────────────────────────────────────
def fit_baryon_only(gd: GalaxyData) -> dict:
    """Baryon-only with fiducial ϒ (0 free params beyond data)."""
    Vb = vbar(gd)
    r = rmse(Vb, gd.Vobs)
    c2 = chi2_red(Vb, gd, n_free=0)
    return {"label": "Baryon-only (ϒ=0.5, 0.7)", "Vmod": Vb,
            "rmse": r, "chi2r": c2, "n_free": 0, "params": {}}


def fit_ofr_direct(gd: GalaxyData) -> dict:
    """
    OFR direct residual: baryonic model with a single global mass-to-light
    ratio ϒ_disk (the only free parameter).  Represents the best a purely
    baryonic hypothesis can do when allowed to tune its normalization.
    """
    def objective(log_up):
        u = math.exp(log_up)
        Vb = vbar(gd, upsilon_disk=u, upsilon_bul=u * 1.4)
        return rmse(Vb, gd.Vobs)

    res = minimize_scalar(objective, bounds=(-3, 3), method="bounded")
    up_opt = math.exp(res.x)
    up_bul = up_opt * 1.4
    Vb = vbar(gd, upsilon_disk=up_opt, upsilon_bul=up_bul)
    r = rmse(Vb, gd.Vobs)
    c2 = chi2_red(Vb, gd, n_free=1)
    return {"label": "OFR direct (ϒ_opt, 1 free param)", "Vmod": Vb,
            "rmse": r, "chi2r": c2, "n_free": 1,
            "params": {"ϒ_disk": round(up_opt, 3), "ϒ_bul": round(up_bul, 3)}}


def _fit_halo(gd: GalaxyData, halo_fn: Callable,
              label: str, p0: list[float]) -> dict:
    """Generic halo + baryon fitter (3 free params: ϒ + 2 halo)."""
    Vb_fid = vbar(gd)

    def objective(params):
        log_up, log_p1, log_p2 = params
        up = math.exp(log_up)
        p1 = math.exp(log_p1)
        p2 = math.exp(log_p2)
        Vb  = vbar(gd, upsilon_disk=up, upsilon_bul=up * 1.4)
        Vdm = halo_fn(gd.R, p1, p2)
        Vm  = vtot(Vb, Vdm)
        return rmse(Vm, gd.Vobs)

    x0 = [math.log(v) for v in p0]
    bounds = [(-3, 3), (-5, 20), (-3, 10)]
    res = minimize(objective, x0, method="L-BFGS-B", bounds=bounds,
                   options={"ftol": 1e-12, "maxiter": 5000})
    up, p1, p2 = (math.exp(v) for v in res.x)
    Vb  = vbar(gd, upsilon_disk=up, upsilon_bul=up * 1.4)
    Vdm = halo_fn(gd.R, p1, p2)
    Vm  = vtot(Vb, Vdm)
    r   = rmse(Vm, gd.Vobs)
    c2  = chi2_red(Vm, gd, n_free=3)
    return {"label": label, "Vmod": Vm, "rmse": r, "chi2r": c2, "n_free": 3,
            "params": {"ϒ_disk": round(up, 3),
                       "p1": round(p1, 4), "p2": round(p2, 4)}}


def fit_pISO(gd: GalaxyData) -> dict:
    return _fit_halo(gd, vdm_pISO, "pISO halo",
                     [0.5, 1e7, 2.0])   # ϒ, rho0 [M_sun/kpc^3], rc [kpc]


def fit_NFW(gd: GalaxyData) -> dict:
    return _fit_halo(gd, vdm_NFW, "NFW halo",
                     [0.5, 1e7, 5.0])


def fit_Burkert(gd: GalaxyData) -> dict:
    return _fit_halo(gd, vdm_Burkert, "Burkert halo",
                     [0.5, 1e7, 3.0])


def fit_MOND(gd: GalaxyData) -> dict:
    """MOND with fiducial ϒ (0 free params) using McGaugh+2016 RAR."""
    Vm = vmond(gd)
    r  = rmse(Vm, gd.Vobs)
    c2 = chi2_red(Vm, gd, n_free=0)
    return {"label": "MOND (RAR, g†=1.2e-10, ϒ=0.5)", "Vmod": Vm,
            "rmse": r, "chi2r": c2, "n_free": 0, "params": {}}


# ── Derived statistics ───────────────────────────────────────────────────────
def mass_discrepancy_stats(gd: GalaxyData,
                           upsilon_disk: float = UPSILON_DISK_FID,
                           upsilon_bul: float = UPSILON_BUL_FID) -> dict:
    """D = Vobs^2 / Vbar^2 (mass discrepancy)."""
    Vb = vbar(gd, upsilon_disk, upsilon_bul)
    # Avoid division by zero for very small baryonic velocities
    Vb_safe = np.maximum(Vb, 0.1)
    D = gd.Vobs**2 / Vb_safe**2
    return {"D_mean": float(np.mean(D)),
            "D_median": float(np.median(D)),
            "D_min": float(np.min(D)),
            "D_max": float(np.max(D))}


def residual_positive_fraction(gd: GalaxyData,
                                upsilon_disk: float = UPSILON_DISK_FID,
                                upsilon_bul: float = UPSILON_BUL_FID) -> float:
    """Fraction of points where Vobs > Vbar (residual > 0)."""
    Vb = vbar(gd, upsilon_disk, upsilon_bul)
    return float(np.mean(gd.Vobs > Vb))


def residual_survives_ml_uncertainty(gd: GalaxyData,
                                      delta_upsilon: float = 0.2) -> dict:
    """
    Does the Vobs > Vbar residual survive reasonable ϒ uncertainty?
    Tests ϒ_disk in range [0.5-δ, 0.5+δ].
    Returns whether the positive-residual fraction stays high even at
    the maximum baryonic ϒ.
    """
    up_max = UPSILON_DISK_FID + delta_upsilon
    Vb_max = vbar(gd, up_max, up_max * 1.4)
    frac_max = float(np.mean(gd.Vobs > Vb_max))
    # Does Vobs exceed Vbar_max at most points?
    survives = frac_max > 0.7
    return {"upsilon_max_tested": round(up_max, 2),
            "pos_fraction_at_max_ϒ": round(frac_max, 3),
            "residual_survives": survives}


# ── Pretty printing ──────────────────────────────────────────────────────────
LINE = "─" * 72

def print_galaxy_report(gd: GalaxyData, fits: list[dict],
                         output_dir: str | None = None) -> None:
    lines: list[str] = []

    def p(*args):
        s = " ".join(str(a) for a in args)
        lines.append(s)
        print(s)

    p(LINE)
    p(f"  GALAXY: {gd.name}")
    p(LINE)
    p(f"  Distance        : {gd.distance_mpc:.2f} Mpc")
    p(f"  Data rows used  : {len(gd.R)}")
    p(f"  Radius range    : {gd.R.min():.2f} – {gd.R.max():.2f} kpc")
    p()

    # RMSE table
    p("  ┌──────────────────────────────────────────┬──────────┬──────────┐")
    p("  │  Model                                   │ RMSE     │  χ²_red  │")
    p("  ├──────────────────────────────────────────┼──────────┼──────────┤")
    for fit in fits:
        p(f"  │  {fit['label']:<40s} │ {fit['rmse']:>8.3f} │ {fit['chi2r']:>8.3f} │")
    p("  └──────────────────────────────────────────┴──────────┴──────────┘")
    p()

    # Best non-OFR model
    non_ofr = [f for f in fits if "OFR" not in f["label"] and "Baryon" not in f["label"]]
    if non_ofr:
        best = min(non_ofr, key=lambda f: f["rmse"])
        p(f"  Best non-OFR model  : {best['label']}  (RMSE = {best['rmse']:.3f} km/s)")
    p()

    # Residual stats with fiducial ϒ
    Vb_fid = vbar(gd)
    residuals = gd.Vobs - Vb_fid
    pos_frac  = residual_positive_fraction(gd)
    D_stats   = mass_discrepancy_stats(gd)
    ml_test   = residual_survives_ml_uncertainty(gd)

    p(f"  Residual positive fraction (Vobs > Vbar)  : {pos_frac:.3f}")
    p()
    p(f"  Mass discrepancy  D = Vobs² / Vbar²")
    p(f"    Mean            : {D_stats['D_mean']:.3f}")
    p(f"    Median          : {D_stats['D_median']:.3f}")
    p(f"    Range           : {D_stats['D_min']:.3f} – {D_stats['D_max']:.3f}")
    p()
    p(f"  ϒ uncertainty test  (ϒ_disk up to {ml_test['upsilon_max_tested']})")
    p(f"    Positive-residual fraction at max ϒ  : {ml_test['pos_fraction_at_max_ϒ']:.3f}")
    p(f"    Residual survives?                   : {ml_test['residual_survives']}")
    p()

    # Fitted params for halo models
    p("  Best-fit parameters:")
    for fit in fits:
        if fit["params"]:
            pstr = "  ".join(f"{k}={v}" for k, v in fit["params"].items())
            p(f"    {fit['label']}: {pstr}")
    p()

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, f"{gd.name}_report.txt")
        with open(out_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        # Also save CSV of model velocities
        csv_path = os.path.join(output_dir, f"{gd.name}_models.csv")
        headers = ["R_kpc", "Vobs", "errV", "Vbar_fid"] + [fit["label"][:20].replace(" ", "_")
                                                               for fit in fits]
        csv_lines = [",".join(headers)]
        for i in range(len(gd.R)):
            row = [f"{gd.R[i]:.4f}", f"{gd.Vobs[i]:.4f}", f"{gd.errV[i]:.4f}",
                   f"{Vb_fid[i]:.4f}"]
            row += [f"{fit['Vmod'][i]:.4f}" for fit in fits]
            csv_lines.append(",".join(row))
        with open(csv_path, "w") as f:
            f.write("\n".join(csv_lines) + "\n")
        print(f"  [saved] {out_path}")
        print(f"  [saved] {csv_path}")


# ── Main ─────────────────────────────────────────────────────────────────────
def run_galaxy(dat_path: str, galaxy_name: str, output_dir: str | None) -> None:
    print(f"\nLoading {galaxy_name} from {dat_path}")
    gd = load_rotmod(dat_path, galaxy_name)

    fits = [
        fit_baryon_only(gd),
        fit_ofr_direct(gd),
        fit_pISO(gd),
        fit_NFW(gd),
        fit_Burkert(gd),
        fit_MOND(gd),
    ]
    print_galaxy_report(gd, fits, output_dir)


def main():
    parser = argparse.ArgumentParser(description="OFR-Gravity SPARC Fleet Runner")
    parser.add_argument("--galaxy", required=True,
                        help="Galaxy name (e.g. DDO154)")
    parser.add_argument("--data-dir", default="/tmp",
                        help="Directory containing *_rotmod.dat files")
    parser.add_argument("--output", default=None,
                        help="Output directory for reports/CSVs")
    args = parser.parse_args()

    dat_path = os.path.join(args.data_dir, f"{args.galaxy}_rotmod.dat")
    if not os.path.exists(dat_path):
        print(f"ERROR: {dat_path} not found.")
        print("Available *_rotmod.dat files in data-dir:")
        for fn in sorted(os.listdir(args.data_dir)):
            if fn.endswith("_rotmod.dat"):
                print(f"  {fn[:-11]}")
        sys.exit(1)

    run_galaxy(dat_path, args.galaxy, args.output)


if __name__ == "__main__":
    main()
