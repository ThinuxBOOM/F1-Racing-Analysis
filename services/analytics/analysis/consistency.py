"""Consistency score (0-100), field-relative.

Method (also shown on the Methodology page):
  1. For each driver, take clean laps in each stint, fuel-corrected.
  2. Remove the stint's own tyre trend (OLS on tyre age); the residual spread is the lap-time noise
     that is NOT explained by degradation. Spread is a robust scale (1.4826 x MAD) so undetected
     traffic laps do not dominate. Pool across stints with weights (n - 2).
  3. Do the same for each sector time (detrended on lap number within stint) and average.
  4. Convert each driver's pooled SD to a z-score against the field, flip the sign (lower
     variability is better), and map through the normal CDF to 0-100. 50 = field average.
  5. Final score = weighted mean of the lap and sector components (0.7 / 0.3).
The score is relative to the drivers in the same session. It is not comparable across sessions.
Traffic that the clean-lap filter cannot detect inflates variance; the score cannot separate it.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from math import erf, sqrt


def _resid_sd(x: np.ndarray, y: np.ndarray):
    n = len(x)
    if n < 5:
        return None
    X = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    # Robust scale (MAD). Undetectable traffic gives heavy-tailed laps that would otherwise
    # dominate a plain SD and make the score measure luck in traffic.
    scale = 1.4826 * float(np.median(np.abs(r - np.median(r))))
    return scale ** 2 * (n - 2), n - 2


def _pooled(parts):
    parts = [p for p in parts if p]
    if not parts:
        return np.nan
    ss = sum(p[0] for p in parts); dof = sum(p[1] for p in parts)
    return float(np.sqrt(ss / dof))


def _cdf(z): return 0.5 * (1 + erf(z / sqrt(2)))


def consistency(prepared: pd.DataFrame) -> list[dict]:
    clean = prepared[prepared["is_clean"]]
    lap_sd, sec_sd, n_used = {}, {}, {}
    for drv, g in clean.groupby("driver"):
        lap_parts, sec_parts = [], []
        for _, s in g.groupby("stint_number"):
            s = s.dropna(subset=["fuel_corr_time_s", "tyre_age"])
            lap_parts.append(_resid_sd(s["tyre_age"].to_numpy(float), s["fuel_corr_time_s"].to_numpy(float)))
            for col in ("s1_s", "s2_s", "s3_s"):
                ss = s.dropna(subset=[col])
                sec_parts.append(_resid_sd(ss["lap_number"].to_numpy(float), ss[col].to_numpy(float)))
        lap_sd[drv] = _pooled(lap_parts)
        sec_sd[drv] = _pooled(sec_parts)
        n_used[drv] = int(len(g))
    df = pd.DataFrame({"lap_sd": lap_sd, "sector_sd": sec_sd, "n_clean": n_used}).dropna()
    if len(df) < 3:
        return []

    def score(col):
        z = (df[col] - df[col].mean()) / (df[col].std(ddof=0) or 1.0)
        return z.map(lambda v: 100 * _cdf(-v))

    df["lap_score"], df["sector_score"] = score("lap_sd"), score("sector_sd")
    df["score"] = 0.7 * df["lap_score"] + 0.3 * df["sector_score"]
    out = []
    for drv, r in df.sort_values("score", ascending=False).iterrows():
        out.append(dict(driver=drv, score=round(float(r["score"]), 1), lap_sd_s=round(float(r["lap_sd"]), 3),
                        sector_sd_s=round(float(r["sector_sd"]), 3), n_clean=int(r["n_clean"]),
                        lap_score=round(float(r["lap_score"]), 1), sector_score=round(float(r["sector_score"]), 1)))
    return out


RELIABILITY_NOTE = ("Single-session score. In simulations on synthetic data the score for the same driver "
                    "moved by about 16 points (1 SD) between races with identical true consistency, so treat "
                    "differences under ~25 points as noise and prefer a multi-race average. Real-world noise "
                    "is likely larger.")
