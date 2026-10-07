"""Core pace metrics: lap cleaning, fuel correction, degradation, teammate deltas.

Design rules:
  * Never treat a raw lap-time gap as a driver gap. Everything is cleaned and corrected first.
  * Every comparison returns a bootstrap confidence interval and sample size.
  * Public data has no fuel load, so fuel burn is a configurable constant (s/lap),
    not a measurement. The value is stored with results as model_version.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

MODEL_VERSION = "v0.1-fuel0.035"
FUEL_EFFECT_S_PER_LAP = 0.035       # approx. time gained per lap as fuel burns
SLOW_LAP_THRESHOLD = 1.07           # laps >7% slower than driver's median are excluded
CLEAN_TRACK_STATUS = {"1"}          # FastF1: 1 = all clear


def flag_clean_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """Add is_clean and exclude_reason columns.

    Expected columns: lap_number, lap_time_s, pit_in, pit_out, track_status, deleted,
    driver (grouping key).
    """
    df = laps.copy()
    df["exclude_reason"] = None

    def mark(mask: pd.Series, reason: str) -> None:
        todo = mask & df["exclude_reason"].isna()
        df.loc[todo, "exclude_reason"] = reason

    mark(df["lap_time_s"].isna(), "no_time")
    mark(df["lap_number"] == 1, "lap1")
    mark(df["pit_in"] | df["pit_out"], "in_out")
    mark(~df["track_status"].astype(str).isin(CLEAN_TRACK_STATUS), "sc_vsc_yellow")
    mark(df["deleted"].fillna(False), "deleted")

    med = df.groupby("driver")["lap_time_s"].transform("median")
    mark(df["lap_time_s"] > med * SLOW_LAP_THRESHOLD, "slow")

    df["is_clean"] = df["exclude_reason"].isna()
    return df


def fuel_correct(laps: pd.DataFrame, total_laps: int,
                 fuel_s_per_lap: float = FUEL_EFFECT_S_PER_LAP) -> pd.Series:
    """Remove fuel-burn effect: express each lap as if run on the final lap's fuel load."""
    return laps["lap_time_s"] - fuel_s_per_lap * (total_laps - laps["lap_number"])


def stint_degradation(stint: pd.DataFrame) -> dict:
    """OLS slope of fuel-corrected time vs tyre age for one stint (clean laps only).

    Returns slope (s/lap), its standard error, and residual SD (consistency).
    """
    s = stint[stint["is_clean"]].dropna(subset=["fuel_corr_time_s", "tyre_age"])
    n = len(s)
    if n < 5:
        return dict(n_clean=n, deg=np.nan, deg_se=np.nan, sd=np.nan, mean=np.nan)
    x = s["tyre_age"].to_numpy(float)
    y = s["fuel_corr_time_s"].to_numpy(float)
    X = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = n - 2
    sigma2 = (resid @ resid) / dof
    cov = sigma2 * np.linalg.inv(X.T @ X)
    return dict(n_clean=n, deg=beta[1], deg_se=float(np.sqrt(cov[1, 1])),
                sd=float(np.sqrt(sigma2)), mean=float(y.mean()))


def teammate_delta(a: pd.Series, b: pd.Series, n_boot: int = 4000, seed: int = 7) -> dict:
    """Median(A) - median(B) with a bootstrap 95% CI. Negative = A faster."""
    a = a.dropna().to_numpy(float)
    b = b.dropna().to_numpy(float)
    if len(a) < 5 or len(b) < 5:
        return dict(delta=np.nan, ci_low=np.nan, ci_high=np.nan, n_a=len(a), n_b=len(b))
    rng = np.random.default_rng(seed)
    boots = np.array([
        np.median(rng.choice(a, len(a))) - np.median(rng.choice(b, len(b)))
        for _ in range(n_boot)
    ])
    return dict(delta=float(np.median(a) - np.median(b)),
                ci_low=float(np.percentile(boots, 2.5)),
                ci_high=float(np.percentile(boots, 97.5)),
                n_a=len(a), n_b=len(b))


def verdict(delta: dict) -> str:
    """Plain-language reading of a teammate delta - never a 'better driver' label."""
    if np.isnan(delta["delta"]):
        return "Insufficient clean laps to compare."
    lo, hi = delta["ci_low"], delta["ci_high"]
    if lo <= 0 <= hi:
        return "No statistically clear pace difference (CI spans zero)."
    who = "A" if delta["delta"] < 0 else "B"
    return (f"Driver {who} shows a clear underlying pace advantage of "
            f"{abs(delta['delta']):.3f}s/lap (95% CI {lo:+.3f} to {hi:+.3f}). "
            "Check tyre age, traffic and strategy before attributing this to the driver.")
