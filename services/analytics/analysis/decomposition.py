"""Driver vs car decomposition for a pair of drivers in one race session. MODEL ESTIMATE.

Model: fuel-corrected clean lap time = driver effect + compound effect + compound-specific
degradation * tyre age + noise (OLS, fixed effects, laps resampled within driver for CIs).

For drivers A and B on different teams:
  adjusted gap = eff_A - eff_B
  car part     = mean(team A drivers' eff) - mean(team B drivers' eff)
  driver part  = (eff_A - team_A mean) - (eff_B - team_B mean)
  circumstance = raw gap (median of lap times excluding pit/neutralised laps) - adjusted gap
                 i.e. tyre mix, tyre age, fuel and strategy differences the model removes.

Key assumption (stated in the UI): within a team the car is identical for both drivers, and the
team's mean driver effect is treated as the car. If both drivers of a team are unusually fast or
slow, that shared part is credited to the car. This is not separable with one season of one
team's data; cross-team driver moves (Phase 4 mixed model) are required.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

ASSUMPTIONS = [
    "Teammates drive an identical car; the team's mean driver effect is credited to the car.",
    "Fuel burn is an assumed constant (0.035 s/lap), not measured.",
    "Traffic, engine modes and setup choices are not observed and fall into the residual term.",
    "One race session only; the interval reflects lap-to-lap noise, not race-to-race variation.",
]


def _design(df: pd.DataFrame, drivers: list[str], comps: list[str], ref: str):
    X = np.zeros((len(df), len(drivers) + 2 * (len(comps) - 1) + 1))
    d_idx = {d: i for i, d in enumerate(drivers)}
    for k, d in enumerate(df["driver"]):
        X[k, d_idx[d]] = 1.0
    col = len(drivers)
    age = df["tyre_age"].to_numpy(float)
    c = df["compound"].to_numpy()
    for comp in comps:
        mask = (c == comp).astype(float)
        X[:, -1] += 0.0
        if comp != ref:
            X[:, col] = mask; col += 1
        X[:, col] = mask * age; col += 1
    return X[:, :col]


def _fit(df, drivers, comps, ref):
    X = _design(df, drivers, comps, ref)
    beta, *_ = np.linalg.lstsq(X, df["fuel_corr_time_s"].to_numpy(float), rcond=None)
    return dict(zip(drivers, beta[:len(drivers)]))


def driver_effects(prepared: pd.DataFrame) -> dict[str, float]:
    """Tyre-mix-adjusted pace per driver (s/lap, fuel-corrected). Lower = faster.
    Raw medians are NOT comparable across drivers on different compounds/tyre ages."""
    clean = prepared[prepared["is_clean"]].dropna(subset=["fuel_corr_time_s", "tyre_age", "compound"])
    drivers = sorted(clean["driver"].unique())
    if not drivers:
        return {}
    comps = sorted(clean["compound"].unique())
    ref = "MEDIUM" if "MEDIUM" in comps else comps[0]
    return _fit(clean, drivers, comps, ref)


def _components(eff, team_of, a, b):
    mean = lambda t: np.mean([eff[d] for d in eff if team_of[d] == t])
    ta, tb = team_of[a], team_of[b]
    adj = eff[a] - eff[b]
    car = mean(ta) - mean(tb)
    drv = (eff[a] - mean(ta)) - (eff[b] - mean(tb))
    return adj, car, drv


def decompose(prepared: pd.DataFrame, a: str, b: str, n_boot: int = 300, seed: int = 11) -> dict:
    clean = prepared[prepared["is_clean"]].dropna(subset=["fuel_corr_time_s", "tyre_age", "compound"]).copy()
    drivers = sorted(clean["driver"].unique())
    if a not in drivers or b not in drivers:
        return dict(error="one or both drivers have no clean laps")
    team_of = clean.groupby("driver")["team"].first().to_dict()
    comps = sorted(clean["compound"].unique())
    ref = "MEDIUM" if "MEDIUM" in comps else comps[0]

    neutral = prepared[prepared["exclude_reason"].isna() | (prepared["exclude_reason"] == "slow")]
    raw = lambda d: float(np.median(neutral[neutral["driver"] == d]["lap_time_s"]))
    raw_gap = raw(a) - raw(b)

    eff = _fit(clean, drivers, comps, ref)
    adj, car, drv = _components(eff, team_of, a, b)

    rng = np.random.default_rng(seed)
    groups = {d: clean[clean["driver"] == d] for d in drivers}
    boots = []
    for _ in range(n_boot):
        samp = pd.concat([g.iloc[rng.integers(0, len(g), len(g))] for g in groups.values()])
        e = _fit(samp, drivers, comps, ref)
        x, y, z = _components(e, team_of, a, b)
        boots.append((x, y, z, raw_gap - x))
    boots = np.array(boots)
    ci = lambda i: [round(float(np.percentile(boots[:, i], 2.5)), 3), round(float(np.percentile(boots[:, i], 97.5)), 3)]
    est = lambda v: round(float(v), 3)
    same_team = team_of[a] == team_of[b]
    return dict(
        driver_a=a, driver_b=b, same_team=same_team,
        label="MODEL ESTIMATE, not measured fact. Negative = A faster.",
        total_raw_gap_s=est(raw_gap),
        components=dict(
            car=dict(estimate_s=est(car), ci95_s=ci(1)),
            driver=dict(estimate_s=est(drv), ci95_s=ci(2)),
            strategy_tyres_traffic=dict(estimate_s=est(raw_gap - adj), ci95_s=ci(3))),
        adjusted_gap_s=dict(estimate_s=est(adj), ci95_s=ci(0)),
        n_laps=dict(a=int((clean.driver == a).sum()), b=int((clean.driver == b).sum())),
        assumptions=ASSUMPTIONS)
