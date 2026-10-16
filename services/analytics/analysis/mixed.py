"""Cross-season mixed-effects driver/car model. MODEL ESTIMATE.

Extends the single-race fixed-effects decomposition (analysis/decomposition.py)
across rounds so conclusions rest on multi-race support:

  y (fuel-corrected clean lap) = driver + team_season + circuit
      + compound + compound_specific_slope * tyre_age + noise

driver and team_season are collinear when drivers never change teams (as in
the mock season and often in reality for one season). They are separated with
a ridge penalty on driver and team terms only (lambda=10), which shrinks the
split toward equal attribution when the data cannot tell them apart. Circuit,
compound and degradation terms are unpenalised fixed effects.

Uncertainty comes from bootstrapping ROUNDS (not laps), so intervals reflect
race-to-race variation — the dominant noise source for season claims. Single
lap resampling would understate it.

Output labels every number a MODEL ESTIMATE and states the equal-car
assumption plus the weak-identifiability warning when no driver moves teams.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

RIDGE_LAMBDA = 10.0


def _build(frames: dict[int, pd.DataFrame]):
    """Concatenate rounds. Returns (y, info dicts, design builder)."""
    parts = []
    for rnd, df in frames.items():
        c = df[df["is_clean"]].dropna(
            subset=["fuel_corr_time_s", "tyre_age", "compound", "driver", "team"]).copy()
        if len(c) == 0:
            continue
        c["round"] = rnd
        parts.append(c)
    if not parts:
        return None
    full = pd.concat(parts, ignore_index=True)
    drivers = sorted(full["driver"].unique())
    teams = sorted(full["team"].unique())
    circuits = sorted(full["round"].unique())  # round proxies circuit in one season
    comps = sorted(full["compound"].unique())
    ref_c = "MEDIUM" if "MEDIUM" in comps else comps[0]
    ref_team = teams[0]
    ref_driver = drivers[0]
    ref_round = circuits[0]
    return full, drivers, teams, circuits, comps, ref_c, ref_team, ref_driver, ref_round


def _design_matrix(full: pd.DataFrame, drivers, teams, circuits, comps,
                   ref_c, ref_team, ref_driver, ref_round, lam: float = RIDGE_LAMBDA):
    # column 0 = global intercept (unpenalised); then drivers, teams, circuits,
    # compound dummies, compound slopes. Reference levels are absorbed into
    # the intercept so all other coefficients are deviations in s/lap.
    d_idx = {d: 1 + i for i, d in enumerate(drivers)}
    n_d = len(drivers)
    t_list = [t for t in teams if t != ref_team]
    t_idx = {t: 1 + n_d + i for i, t in enumerate(t_list)}
    col = 1 + n_d + len(t_list)
    r_list = [r for r in circuits if r != ref_round]
    r_idx = {r: col + i for i, r in enumerate(r_list)}
    col += len(r_list)
    c_list = [c for c in comps if c != ref_c]
    c_idx = {c: col + i for i, c in enumerate(c_list)}
    col += len(c_list)
    # slopes for every compound
    s_idx = {c: col + i for i, c in enumerate(comps)}
    col += len(comps)
    n_col = col
    n = len(full)
    X = np.zeros((n, n_col))
    X[:, 0] = 1.0
    drv = full["driver"].to_numpy()
    team = full["team"].to_numpy()
    rnd = full["round"].to_numpy()
    comp = full["compound"].to_numpy()
    age = full["tyre_age"].to_numpy(float)
    for k in range(n):
        X[k, d_idx[drv[k]]] = 1.0
        if team[k] != ref_team:
            X[k, t_idx[team[k]]] = 1.0
        if rnd[k] != ref_round:
            X[k, r_idx[rnd[k]]] = 1.0
        if comp[k] != ref_c:
            X[k, c_idx[comp[k]]] = 1.0
        X[k, s_idx[comp[k]]] = age[k]
    y = full["fuel_corr_time_s"].to_numpy(float)
    # ridge on driver + team blocks only (not intercept/circuit/compound)
    pen = np.zeros(n_col)
    for d, i in d_idx.items():
        pen[i] = lam
    for t, i in t_idx.items():
        pen[i] = lam
    Xa = np.vstack([X, np.diag(np.sqrt(np.where(pen > 0, pen, 0.0)))])
    ya = np.concatenate([y, np.zeros(n_col)])
    # zero-penalty columns have a zero row -> harmless; drop all-zero rows
    keep = np.abs(Xa).sum(axis=1) > 0
    Xa, ya = Xa[keep], ya[keep]
    return X, y, Xa, ya, dict(d_idx=d_idx, t_idx=t_idx, r_idx=r_idx, c_idx=c_idx,
                              s_idx=s_idx, n_col=n_col, n_d=n_d,
                              t_list=t_list, r_list=r_list, c_list=c_list)


def fit_mixed(frames: dict[int, pd.DataFrame], lam: float = RIDGE_LAMBDA) -> dict:
    b = _build(frames)
    if b is None:
        return dict(error="no clean laps in any round")
    full, drivers, teams, circuits, comps, ref_c, ref_team, ref_driver, ref_round = b
    X, y, Xa, ya, idx = _design_matrix(full, drivers, teams, circuits, comps,
                                       ref_c, ref_team, ref_driver, ref_round, lam)
    beta, *_ = np.linalg.lstsq(Xa, ya, rcond=None)
    return _unpack(beta, full, drivers, teams, circuits, comps, idx,
                   ref_team, ref_driver, lam, n_obs=len(full))


def _unpack(beta, full, drivers, teams, circuits, comps, idx,
            ref_team, ref_driver, lam, n_obs):
    d_idx, t_idx = idx["d_idx"], idx["t_idx"]
    n_d = idx["n_d"]
    # driver raw coefficients include reference level; centre them for readability
    raw_d = np.array([beta[d_idx[d]] for d in drivers])
    # team effects: ref team = 0, others = beta
    team_eff = {t: (0.0 if t == ref_team else float(beta[t_idx[t]])) for t in teams}
    # attribute: car's pace = team effect + mean driver effect of its members
    # (same convention as single-race model: shared strength -> car)
    members: dict[str, list[str]] = {t: [] for t in teams}
    n_laps: dict[str, int] = {}
    for d in drivers:
        t = full[full["driver"] == d]["team"].mode().iloc[0]
        members[t].append(d)
        n_laps[d] = int((full["driver"] == d).sum())
    driver_rating = {}
    for d in drivers:
        t = full[full["driver"] == d]["team"].mode().iloc[0]
        # deviation from team mean of raw driver coeffs
        mates = members[t]
        m = float(np.mean([raw_d[drivers.index(x)] for x in mates]))
        driver_rating[d] = float(raw_d[drivers.index(d)] - m)
    car_rating = {}
    for t in teams:
        m = float(np.mean([raw_d[drivers.index(x)] for x in members[t]])) if members[t] else 0.0
        car_rating[t] = float(team_eff[t] + m)
    # centre car ratings on best = 0 gap scale handled by caller
    return dict(drivers=drivers, teams=teams, driver_rating=driver_rating,
                car_rating=car_rating, team_members=members, n_laps=n_laps,
                n_obs=int(n_obs), n_rounds=int(full["round"].nunique()),
                lam=float(lam), ref_team=ref_team)


def mixed_with_intervals(frames: dict[int, pd.DataFrame], n_boot: int = 200,
                         seed: int = 41, lam: float = RIDGE_LAMBDA) -> dict:
    base = fit_mixed(frames, lam)
    if "error" in base:
        return base
    rng = np.random.default_rng(seed)
    rounds = sorted(frames.keys())
    boot_d: dict[str, list[float]] = {d: [] for d in base["drivers"]}
    boot_c: dict[str, list[float]] = {t: [] for t in base["teams"]}
    for _ in range(n_boot):
        pick = [rounds[int(rng.integers(0, len(rounds)))] for _ in rounds]
        sub = {r: frames[r] for r in pick}
        # merge frames with same round key duplicated: concat with round jitter key
        merged: dict[int, pd.DataFrame] = {}
        for i, r in enumerate(pick):
            merged[1000 + i] = frames[r].copy()
            merged[1000 + i]["_bround"] = r
        # rebuild using _bround as circuit id
        parts = []
        for k, df in merged.items():
            c = df[df["is_clean"]].dropna(
                subset=["fuel_corr_time_s", "tyre_age", "compound", "driver", "team"]).copy()
            if len(c):
                c["round"] = c["_bround"] if "_bround" in c else k
                parts.append(c)
        if not parts:
            continue
        full = pd.concat(parts, ignore_index=True)
        drivers, teams = base["drivers"], base["teams"]
        circuits = sorted(full["round"].unique())
        comps = sorted(full["compound"].unique())
        ref_c = "MEDIUM" if "MEDIUM" in comps else comps[0]
        try:
            X, y, Xa, ya, idx = _design_matrix(full, drivers, teams, circuits, comps,
                                               ref_c, base["ref_team"], drivers[0], circuits[0], lam)
            beta, *_ = np.linalg.lstsq(Xa, ya, rcond=None)
            u = _unpack(beta, full, drivers, teams, circuits, comps, idx,
                        base["ref_team"], drivers[0], lam, len(full))
            for d in drivers:
                boot_d[d].append(u["driver_rating"][d])
            for t in teams:
                boot_c[t].append(u["car_rating"][t])
        except Exception:
            continue
    def summ(base_v: dict[str, float], boots: dict[str, list[float]]):
        out = {}
        for k, v in base_v.items():
            b = np.array(boots[k]) if len(boots[k]) >= 20 else np.array([v])
            lo, hi = float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))
            out[k] = dict(estimate_s=round(float(v), 3), ci95_s=[round(lo, 3), round(hi, 3)],
                          ci_width_s=round(hi - lo, 3))
        return out
    # driver moves check: do any drivers appear on >1 team?
    moves = 0
    for d in base["drivers"]:
        ts = set()
        for df in frames.values():
            m = df[df["driver"] == d]["team"].unique().tolist()
            ts.update(m)
        if len(ts) > 1:
            moves += 1
    return dict(
        label="MODEL ESTIMATE, not measured fact. Lower = faster.",
        n_obs=base["n_obs"], n_rounds=base["n_rounds"], lam=lam,
        driver_moves_between_teams=int(moves),
        identifiability=("weak: no driver changes teams, driver/car split leans on ridge prior"
                         if moves == 0 else f"{moves} driver(s) changed teams; split better identified"),
        drivers=summ(base["driver_rating"], boot_d),
        cars=summ(base["car_rating"], boot_c),
        team_members=base["team_members"], n_laps=base["n_laps"],
        assumptions=[
            "Teammates share an identical car within a round; team-season mean credited to car.",
            "Ridge penalty (lambda=10) on driver and team terms stabilises the unidentifiable split.",
            "Intervals come from resampling ROUNDS, reflecting race-to-race variation.",
            "Fuel correction uses per-round fuel estimate where reliable, else 0.035 fallback.",
        ])
