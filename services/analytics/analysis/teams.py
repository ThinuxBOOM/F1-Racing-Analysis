"""Team aggregates for one session. MODEL ESTIMATE where noted.

Team (car) pace = mean of its drivers' tyre-mix-adjusted driver effects (same
fixed-effects model as driver-vs-car). Gap to best car carries a bootstrap 95%
interval from resampling laps within driver. Teammate gap reuses the same model.
Points and positions are observed facts, not estimates.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from analysis.decomposition import driver_effects, _fit


def team_summary(prepared: pd.DataFrame, results: pd.DataFrame,
                 n_boot: int = 200, seed: int = 21) -> list[dict]:
    clean = prepared[prepared["is_clean"]].dropna(
        subset=["fuel_corr_time_s", "tyre_age", "compound"])
    if clean.empty:
        return []
    drivers = sorted(clean["driver"].unique())
    team_of = clean.groupby("driver")["team"].first().to_dict()
    comps = sorted(clean["compound"].unique())
    ref = "MEDIUM" if "MEDIUM" in comps else comps[0]

    eff = _fit(clean, drivers, comps, ref)
    teams = sorted(set(team_of.values()))
    team_mean = {t: float(np.mean([eff[d] for d in eff if team_of[d] == t])) for t in teams}
    best = min(team_mean.values())

    # bootstrap CI for each team's mean and gap-to-best
    rng = np.random.default_rng(seed)
    groups = {d: clean[clean["driver"] == d] for d in drivers}
    boot_means: dict[str, list[float]] = {t: [] for t in teams}
    for _ in range(n_boot):
        try:
            samp = pd.concat([g.iloc[rng.integers(0, len(g), len(g))] for g in groups.values()])
        except Exception:
            break
        try:
            e = _fit(samp, drivers, comps, ref)
        except Exception:
            continue
        for t in teams:
            boot_means[t].append(float(np.mean([e[d] for d in e if team_of[d] == t])))
    ci: dict[str, list[float]] = {}
    for t in teams:
        b = np.array(boot_means[t])
        if len(b) >= 20:
            lo, hi = float(np.percentile(b - b.mean() + team_mean[t], 2.5)), float(
                np.percentile(b - b.mean() + team_mean[t], 97.5))
            # gap CI = team CI shifted by best (conservative: best treated as fixed)
            ci[t] = [round(lo - best, 3), round(hi - best, 3)]
        else:
            ci[t] = [None, None]

    res = results.set_index("driver") if not results.empty else pd.DataFrame()
    out = []
    for t in teams:
        members = [d for d in drivers if team_of[d] == t]
        pts, finishes, n_clean = 0, [], 0
        for d in members:
            n_clean += int((clean["driver"] == d).sum())
            if d in res.index:
                r = res.loc[d]
                # res may have duplicate index handling; take first if Series of Series
                try:
                    p = r["points"] if not isinstance(r, pd.DataFrame) else r["points"].iloc[0]
                    f = r["finish_pos"] if not isinstance(r, pd.DataFrame) else r["finish_pos"].iloc[0]
                except Exception:
                    p, f = 0, None
                pts += 0 if pd.isna(p) else float(p)
                finishes.append(None if pd.isna(f) else int(f))
        out.append(dict(
            team=t,
            drivers=sorted(members),
            points=pts,
            finish_positions=sorted([f for f in finishes if f is not None]),
            n_clean=n_clean,
            car_pace_s=round(team_mean[t], 3),
            gap_to_best_car_s=round(team_mean[t] - best, 3),
            gap_ci95_s=ci[t],
            n_drivers=len(members),
        ))
    out.sort(key=lambda x: x["gap_to_best_car_s"])
    return out


ASSUMPTIONS = [
    "Car pace is the mean of its drivers' tyre-mix-adjusted effects; shared driver strength is credited to the car.",
    "Fuel burn is an assumed constant (0.035 s/lap).",
    "One session only; interval reflects lap-to-lap noise, not race-to-race variation.",
]
