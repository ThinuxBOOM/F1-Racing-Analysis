"""Tyre-compound analysis for one session. MODEL ESTIMATE where noted.

For each compound present on clean laps:
  * n_clean, n_drivers, median tyre age
  * median fuel-corrected time (observed, not comparable across compounds
    because faster cars may favour one compound)
  * adjusted offset vs MEDIUM from the same fixed-effects model as
    driver-vs-car (driver + compound + compound-specific degradation).
    This is the comparable figure.
  * degradation slope: OLS of fuel-corrected time on tyre age within the
    compound (clean laps only) + standard error + reliability flag.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

import metrics as m


def _ols_slope(x: np.ndarray, y: np.ndarray):
    n = len(x)
    if n < 5:
        return np.nan, np.nan, np.nan, n
    X = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = n - 2
    if dof <= 0:
        return float(beta[1]), np.nan, float(np.sqrt((resid @ resid) / n)), n
    sigma2 = (resid @ resid) / dof
    try:
        cov = sigma2 * np.linalg.inv(X.T @ X)
        se = float(np.sqrt(max(cov[1, 1], 0)))
    except Exception:
        se = np.nan
    sd = float(np.sqrt(sigma2))
    return float(beta[1]), se, sd, n


def compound_offsets(prepared: pd.DataFrame) -> dict[str, float]:
    """Adjusted compound offset vs reference from fixed-effects fit.

    Returns dict compound -> offset in s/lap (MEDIUM or first compound = 0).
    Lower (more negative) = faster.
    """
    from analysis.decomposition import _design
    clean = prepared[prepared["is_clean"]].dropna(
        subset=["fuel_corr_time_s", "tyre_age", "compound"])
    drivers = sorted(clean["driver"].unique())
    comps = sorted(clean["compound"].unique())
    if not drivers or not comps:
        return {}
    ref = "MEDIUM" if "MEDIUM" in comps else comps[0]
    X = _design(clean, drivers, comps, ref)
    y = clean["fuel_corr_time_s"].to_numpy(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    # beta layout: [driver effects (D)] then per non-ref comp: dummy, slope;
    # ref comp contributes only a slope at its position. Walk in _design order.
    out: dict[str, float] = {ref: 0.0}
    idx = len(drivers)
    for comp in comps:
        if comp != ref:
            out[comp] = float(beta[idx])
            idx += 2  # dummy + slope
        else:
            idx += 1  # slope only
    return out


def tyre_report(prepared: pd.DataFrame) -> list[dict]:
    clean = prepared[prepared["is_clean"]]
    if clean.empty:
        return []
    offsets = compound_offsets(prepared)
    ref = "MEDIUM" if "MEDIUM" in clean["compound"].unique() else sorted(
        clean["compound"].unique())[0]
    rows = []
    for comp, g in clean.groupby("compound"):
        g = g.dropna(subset=["fuel_corr_time_s", "tyre_age"])
        n = len(g)
        med_t = float(g["fuel_corr_time_s"].median()) if n else None
        med_age = float(g["tyre_age"].median()) if n else None
        deg, se, sd, _ = _ols_slope(g["tyre_age"].to_numpy(float),
                                    g["fuel_corr_time_s"].to_numpy(float)) if n else (np.nan,) * 4
        rows.append(dict(
            compound=str(comp),
            n_clean=int(n),
            n_drivers=int(g["driver"].nunique()),
            median_fuel_corrected_s=None if med_t is None or np.isnan(med_t) else round(med_t, 3),
            median_tyre_age=None if med_age is None or np.isnan(med_age) else round(med_age, 1),
            adjusted_offset_vs_medium_s=round(float(offsets.get(str(comp), np.nan)), 3)
            if str(comp) in offsets and not np.isnan(offsets[str(comp)]) else None,
            is_reference=str(comp) == ref,
            deg_s_per_lap=None if np.isnan(deg) else round(float(deg), 4),
            deg_se=None if deg_se_is_nan(se) else round(float(se), 4),
            reliable=bool(n >= 8 and not np.isnan(se)),
        ))
    # sort by adjusted pace (fastest first), Nones last
    rows.sort(key=lambda r: (r["adjusted_offset_vs_medium_s"] is None,
                             r["adjusted_offset_vs_medium_s"] or 0))
    return rows


def deg_se_is_nan(v) -> bool:
    try:
        return bool(np.isnan(v))
    except Exception:
        return True
