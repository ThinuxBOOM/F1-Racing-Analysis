"""Per-circuit fuel-burn estimation. MODEL ESTIMATE.

Public timing has no fuel load, so Phase 1-2 fixed fuel at 0.035 s/lap.
Here we estimate it per circuit from the data and report whether the data
can actually identify it.

Identification: within a stint, (total_laps - lap_number) and tyre_age move
together, so fuel and degradation are collinear. Across stints, tyre age
resets at pit stops while fuel load keeps falling, which breaks the
collinearity. The regression below exploits exactly that:

  lap_time = driver + compound + compound_specific_slope * tyre_age
             + fuel * (total_laps - lap_number) + noise      (OLS, clean laps)

Returns fuel in s/lap with standard error and 95% CI. If fewer than 2 stints
per driver on average, or SE is large, the estimate is flagged unreliable
and callers should fall back to the 0.035 constant.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

FALLBACK_FUEL = 0.035
PLAUSIBLE = (0.005, 0.09)


def estimate_fuel(prepared: pd.DataFrame, total_laps: int) -> dict:
    clean = prepared[prepared["is_clean"]].dropna(
        subset=["lap_time_s", "tyre_age", "compound", "driver", "lap_number"]).copy()
    if len(clean) < 60:
        return dict(fuel_s_per_lap=FALLBACK_FUEL, se=np.nan, ci95=[np.nan, np.nan],
                    n_clean=int(len(clean)), reliable=False,
                    note="Too few clean laps to estimate fuel; using 0.035 fallback.")
    drivers = sorted(clean["driver"].unique())
    comps = sorted(clean["compound"].unique())
    ref = "MEDIUM" if "MEDIUM" in comps else comps[0]
    d_idx = {d: i for i, d in enumerate(drivers)}
    n_d, n_c = len(drivers), len(comps)
    # columns: drivers (n_d) + compound dummies (n_c-1) + compound slopes (n_c) + fuel (1)
    n_col = n_d + (n_c - 1) + n_c + 1
    X = np.zeros((len(clean), n_col))
    drv = clean["driver"].to_numpy()
    for k, d in enumerate(drv):
        X[k, d_idx[d]] = 1.0
    age = clean["tyre_age"].to_numpy(float)
    c = clean["compound"].to_numpy()
    laps = clean["lap_number"].to_numpy(float)
    fuel_col = n_col - 1
    X[:, fuel_col] = float(total_laps) - laps
    col = n_d
    comp_dummy_idx: dict[str, int] = {}
    for comp in comps:
        mask = (c == comp).astype(float)
        if comp != ref:
            X[:, col] = mask
            comp_dummy_idx[comp] = col
            col += 1
    comp_slope_idx: dict[str, int] = {}
    for comp in comps:
        mask = (c == comp).astype(float)
        X[:, col] = mask * age
        comp_slope_idx[comp] = col
        col += 1
    y = clean["lap_time_s"].to_numpy(float)
    beta, res, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    n, p = len(y), X.shape[1]
    resid = y - X @ beta
    dof = max(n - p, 1)
    sigma2 = float((resid @ resid) / dof)
    try:
        cov = sigma2 * np.linalg.inv(X.T @ X)
        se = float(np.sqrt(max(cov[fuel_col, fuel_col], 0)))
    except Exception:
        se = np.nan
    fuel = float(beta[fuel_col])
    ci = [fuel - 1.96 * se, fuel + 1.96 * se] if se == se else [np.nan, np.nan]
    # reliability: needs multi-stint data + plausible value + tight SE
    n_stints = clean.groupby(["driver", "stint_number"]).ngroups if "stint_number" in clean else 0
    avg_stints = n_stints / max(len(drivers), 1)
    reliable = bool(avg_stints >= 1.6 and se == se and se < 0.02
                    and PLAUSIBLE[0] <= fuel <= PLAUSIBLE[1] and len(clean) >= 150)
    note = ("Estimated from multi-stint fuel vs tyre-age separation."
            if reliable else
            "Weakly identified (single-stint dominated or noisy); prefer 0.035 fallback for conclusions.")
    return dict(fuel_s_per_lap=round(fuel, 4), se=None if se != se else round(se, 4),
                ci95=[None if v != v else round(v, 4) for v in ci],
                n_clean=int(len(clean)), n_stints=int(n_stints), reliable=bool(reliable),
                fallback=FALLBACK_FUEL, note=note)
